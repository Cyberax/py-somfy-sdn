import asyncio
from abc import ABC, abstractmethod
from asyncio import events, StreamReader, StreamWriter, Future, InvalidStateError
from types import TracebackType
from typing import List, Optional, Type, Callable, Tuple, override

from somfy.recognizer import MessageRecognizer
from somfy.messages import SomfyMessage, SomfyMessageId, NodeType, MASTER_ADDRESS, BROADCAST_ADDR, SomfyAddress, \
    SomfyPayload

# The SDN integration docs define the timeout as 280ms, but we want to really be sure
COMMUNICATION_TIMEOUT_SEC = 1.0
# The time the MASTER node needs to wait after the last bus activity (see page 9)
BUS_QUIET_TIME_SEC = 0.025  # 25 milliseconds


class BackoffPolicy(object):
    def __init__(self):
        self.max_wait = 100
        self.initial_wait = 1
        self.cur_retry = 0

    def success(self):
        self.cur_retry = 0

    def get_wait_time_sec_after_a_failure(self) -> float:
        if self.cur_retry <= 0:
            self.cur_retry += 1
            return 0
        res = min(self.max_wait, 2 ** (self.cur_retry - 1))
        self.cur_retry += 1
        return res


class ConnectionFactory(ABC):
    @abstractmethod
    async def connect(self) -> (StreamReader, StreamWriter):
        pass


class SocketConnectionFactory(ConnectionFactory):
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    @override
    async def connect(self) -> (StreamReader, StreamWriter):
        loop = events.get_running_loop()
        reader = asyncio.StreamReader(loop=loop)
        protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
        transport, _ = await loop.create_connection(protocol_factory=lambda: protocol, host=self.host, port=self.port)
        writer = asyncio.StreamWriter(transport, protocol, reader, loop)
        return reader, writer


class _Channel(object):
    def __init__(self, connection_factory: ConnectionFactory):
        self.last_activity = 0
        self.lock = asyncio.Lock()
        self.connection_factory = connection_factory
        self.writer: Optional[StreamWriter] = None
        self.reader: Optional[StreamReader] = None

    async def start(self):
        async with self.lock:
            if self.writer is None:
                self.reader, self.writer = await self.connection_factory.connect()

    def is_closed(self) -> bool:
        return self.writer is None

    async def close(self):
        writer = self.writer
        if writer is not None:
            # Terminate any pending reads/writes
            writer.close()
        async with self.lock:
            self._do_close()

    def _do_close(self):
        if self.writer is not None:
            self.writer.close()
            self.writer = None
            self.reader = None

    async def read_byte(self) -> int:
        async with self.lock:
            if self.is_closed():
                raise IOError("Channel is closed")

            loop = asyncio.get_running_loop()
            try:
                chunk = await self.reader.readexactly(1)
            except Exception:
                self._do_close()
                raise
            self.last_activity = loop.time()
            return chunk[0]

    async def write_bytes(self, data: List[int]):
        async with self.lock:
            if self.is_closed():
                raise IOError("Channel is closed")

            loop = asyncio.get_running_loop()
            try:
                self.writer.write(bytes(data))
                await self.writer.drain()
            except Exception:
                self._do_close()
                raise
            self.last_activity = loop.time()

    def get_last_activity(self):
        return self.last_activity


# This class runs as a background task of the communicator, making sure that the TCP connection does not
# get blocked once the read buffer overflows. It additionally can attempt to parse the bus traffic and
# look for valid Somfy SDN messages.
class _Drainer(object):
    def __init__(self, channel: _Channel, lock: asyncio.Lock, need_to_talk: asyncio.Event, done_notifier: Future[bool],
                 sniffer_callback: Callable[[SomfyMessage], None] = None):
        self.channel = channel
        self.lock = lock
        self.need_to_talk = need_to_talk
        self.sniffer_callback = sniffer_callback
        self.message_recognizer = MessageRecognizer()
        self.done_notifier = done_notifier

    async def run_loop(self):
        try:
            while True:
                await self.attempt_drain()
        except asyncio.CancelledError:
            # Cancellation is normal, don't log it
            pass
        except BaseException as ex:
            try:
                self.done_notifier.set_exception(ex)
            except InvalidStateError:
                pass
            raise ex

    async def attempt_drain(self):
        async with self.lock:
            # Loop until we are requested to relinquish the channel lock
            while True:
                wait_set = []

                byte_reader = asyncio.ensure_future(self.channel.read_byte())
                wait_set.append(byte_reader)

                # The SDN docs say that we need to wait for at least BUS_QUIET_TIME (25ms) before starting
                # any other activity. So we don't allow the bus lock to be relinquished until this timeout expires.
                bus_quiet_time_so_far = asyncio.get_running_loop().time() - self.channel.get_last_activity()
                timeout = None
                needs_to_relinquish_lock = None
                if bus_quiet_time_so_far < BUS_QUIET_TIME_SEC:
                    timeout = BUS_QUIET_TIME_SEC - bus_quiet_time_so_far
                else:
                    # We only allow the lock to be relinquished if we are not waiting for the bus quiet time
                    # to expire. This quiet time includes our own traffic and the 3-rd party traffic.
                    needs_to_relinquish_lock = asyncio.ensure_future(self.need_to_talk.wait())
                    wait_set.append(needs_to_relinquish_lock)

                try:
                    _, undone = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
                    for u in undone:
                        u.cancel()
                except BaseException:
                    for i in wait_set:
                        i.cancel()
                    raise

                if byte_reader.done():
                    # We got incoming data, so the next statement won't block!
                    data_byte = await byte_reader
                    if self.sniffer_callback is not None:
                        msg = self.message_recognizer.add_data(data_byte)
                        if msg is not None:
                            self.sniffer_callback(msg)

                if needs_to_relinquish_lock is not None and needs_to_relinquish_lock.done():
                    # The main thread wants to do a message exchange, give up the ownership of the lock
                    break


class SomfyExchanger(ABC):
    @abstractmethod
    async def exchange(self, to_send: Optional[SomfyMessage],
                       msg_consumer: Optional[Callable[[SomfyMessage], bool]]) -> bool:
        pass

    @abstractmethod
    async def start(self):
        pass

    @abstractmethod
    async def stop(self):
        pass

    @abstractmethod
    def done_notification(self) -> Future[bool]:
        pass


class SomfyConnector(SomfyExchanger):
    channel: _Channel = None

    def __init__(self, connection_factory: ConnectionFactory, sniffer_callback: Callable[[SomfyMessage], None] = None):
        self.channel = _Channel(connection_factory)
        self.reader_lock = asyncio.Lock()
        self.need_to_talk = asyncio.Event()
        self.writer_lock = asyncio.Lock()
        self.done_notify = asyncio.Future[bool]()
        self.drainer = _Drainer(self.channel, self.reader_lock, self.need_to_talk, self.done_notify, sniffer_callback)
        self.timeout = COMMUNICATION_TIMEOUT_SEC
        self.last_write_time = 0
        self.drainer_task: Optional[asyncio.Task] = None

    async def __aenter__(self) -> "SomfyConnector":
        # We don't need to open the channel here, the drainer will do that for us in background
        await self.start()
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
                        traceback: Optional[TracebackType]):
        await self.stop()
        return None

    @override
    async def start(self):
        await self.channel.start()
        assert self.drainer_task is None
        self.drainer_task = asyncio.create_task(name="SDNBusDrainer", coro=self.drainer.run_loop())

    @override
    async def stop(self):
        await self.channel.close()
        self.drainer_task.cancel()
        await self.drainer_task
        self.drainer_task = None
        try:
            self.done_notify.set_result(True)
        except InvalidStateError:
            pass

    @override
    def done_notification(self) -> Future[bool]:
        return self.done_notify

    # Run the message exchange. `msg_consumer` callback is called for each message, it should return `True` if
    # it wants the exchange to continue. If `msg_consumer` is not specified, the method will not attempt
    # to read the data.
    # Returns False if the timeout expires before `msg_consumer` signals that it's done.
    @override
    async def exchange(self, to_send: Optional[SomfyMessage],
                       msg_consumer: Optional[Callable[[SomfyMessage], bool]]) -> bool:
        async with self.writer_lock:
            # Signal the drainer task that we want to talk with the SDN network and that it needs to stop
            # draining the data.
            self.need_to_talk.set()
            try:
                async with self.reader_lock:
                    async with asyncio.timeout(self.timeout):
                        await self._do_exchange(to_send, msg_consumer)
                        return True
            except asyncio.TimeoutError:
                return False
            except BaseException as ex:
                try:
                    self.done_notify.set_exception(ex)
                except InvalidStateError:
                    pass
                raise ex
            finally:
                self.need_to_talk.clear()

    async def _do_exchange(self, to_send: Optional[SomfyMessage],
                           msg_consumer: Optional[Callable[[SomfyMessage], bool]]):
        if to_send is not None:
            await self.channel.write_bytes(to_send.serialize())

        if not msg_consumer:
            return

        recognizer = MessageRecognizer()
        while True:
            bt = await self.channel.read_byte()
            msg = recognizer.add_data(bt)
            if msg is not None:
                keep_going = msg_consumer(msg)
                if not keep_going:
                    return


class ReconnectingSomfyConnector(SomfyExchanger):
    def __init__(self, connection_factory: ConnectionFactory, sniffer_callback: Callable[[SomfyMessage], None] = None,
                 backoff_policy: BackoffPolicy = BackoffPolicy()):
        self.done_notify = asyncio.Future[bool]()
        self.backoff_policy = backoff_policy
        self.connection_factory = connection_factory
        self.sniffer_callback = sniffer_callback
        self.connector = SomfyConnector(self.connection_factory, self.sniffer_callback)
        self.lock = asyncio.Lock()
        self.connector_task: Optional[asyncio.Task] = None
        self.done_notify = asyncio.Future[bool]()
        self.timeout = COMMUNICATION_TIMEOUT_SEC

    async def __aenter__(self) -> "ReconnectingSomfyConnector":
        # We don't need to open the channel here, the drainer will do that for us in background
        await self.start()
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
                        traceback: Optional[TracebackType]):
        await self.stop()
        return None

    @override
    async def start(self):
        async with self.lock:
            await self.connector.start()
            self.connector_task = asyncio.create_task(name="SomfyReconnect", coro=self._reconnect())

    @override
    async def stop(self):
        self.connector_task.cancel()
        await self.connector_task
        async with self.lock:
            try:
                await self.connector.stop()
                self.done_notify.set_result(True)
            except InvalidStateError:
                pass
            except BaseException as ex:
                try:
                    self.done_notify.set_exception(ex)
                except InvalidStateError:
                    pass
                raise ex

    @override
    def done_notification(self) -> Future[bool]:
        return self.done_notify

    async def _reconnect(self):
        while not asyncio.current_task().cancelling():
            # noinspection PyBroadException
            try:
                await self.connector.done_notification()
            except BaseException:
                pass
            async with self.lock:
                while True:
                    await asyncio.sleep(self.backoff_policy.get_wait_time_sec_after_a_failure())
                    self.connector = SomfyConnector(self.connection_factory, self.sniffer_callback)
                    try:
                        await self.connector.start()
                        self.backoff_policy.success()
                        break
                    except OSError:
                        pass

    @override
    async def exchange(self, to_send: Optional[SomfyMessage],
                       msg_consumer: Optional[Callable[[SomfyMessage], bool]]) -> bool:
        try:
            async with asyncio.timeout(self.timeout):
                async with self.lock:
                    return await self.connector.exchange(to_send, msg_consumer)
        except asyncio.TimeoutError:
            return False


async def fire_and_forget(conn: SomfyExchanger, to_send: SomfyMessage):
    await conn.exchange(to_send, None)


# Attempt to detect Somfy devices on the SDN bus. Always waits for the communication timeout
async def detect_devices(conn: SomfyExchanger,
                         only: NodeType = NodeType.TYPE_ALL) -> List[Tuple[SomfyAddress, NodeType | int]]:
    detect_nodes = SomfyMessage(msgid=SomfyMessageId.GET_NODE_ADDR,
                                from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                                to_node_type=only, to_addr=BROADCAST_ADDR)
    nodes: List[Tuple[SomfyAddress, NodeType | int]] = []

    # Gather the node addresses
    def gather_addr(msg: SomfyMessage) -> bool:
        if (msg.msgid == SomfyMessageId.POST_NODE_ADDR and
                (only == NodeType.TYPE_ALL or msg.from_node_type == only)):
            nodes.append((msg.from_addr, msg.from_node_type))
        return True

    # We expect to end up with the timeout error here, as we try to gather all the replies
    await conn.exchange(detect_nodes, gather_addr)

    return nodes


# Unlike `exchange_one`, this method simply returns None on timeout
async def try_to_exchange_one(conn: SomfyExchanger, addr: SomfyAddress, msgid: SomfyMessageId,
                              expected_reply: SomfyMessageId,
                              payload: Optional[SomfyPayload] = SomfyPayload([])) -> Optional[SomfyMessage]:
    result: Optional[SomfyMessage] = None

    def filter_type(msg: SomfyMessage):
        found_reply = msg.from_addr == addr and msg.msgid == expected_reply
        if found_reply:
            nonlocal result
            result = msg
            return False
        return True

    sent = SomfyMessage(msgid=msgid, from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                        to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=payload)
    await conn.exchange(sent, filter_type)

    return result
