import asyncio
from abc import ABC, abstractmethod
from asyncio import events, StreamReader, StreamWriter
from types import TracebackType
from typing import List, Optional, Type, Callable, Tuple

from somfy.recognizer import MessageRecognizer
from somfy.messages import SomfyMessage, SomfyMessageId, NodeType, MASTER_ADDRESS, BROADCAST_ADDR, SomfyAddress, \
    SomfyPayload

# The SDN integration docs define the timeout as 280ms, but we want to really be sure
COMMUNICATION_TIMEOUT_SEC = 1.0
# The time the MASTER node needs to wait after the last bus activity (see page 9)
BUS_QUIET_TIME_SEC = 0.025  # 25 milliseconds


class Channel(ABC):
    @abstractmethod
    async def __aenter__(self) -> "Channel":
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: Optional[Type[BaseException]],
                        exc_value: Optional[BaseException], traceback: Optional[TracebackType]):
        pass

    @abstractmethod
    async def read_byte(self) -> int:
        pass

    @abstractmethod
    async def write_bytes(self, data: List[int]):
        pass

    @abstractmethod
    async def open(self):
        pass

    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    def get_last_activity(self):
        pass


class SocketChannel(Channel):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.last_activity = 0
        self.reader: Optional[StreamReader] = None
        self.writer: Optional[StreamWriter] = None

    async def __aenter__(self) -> "SocketChannel":
        await self.open()
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
                        traceback: Optional[TracebackType]):
        await self.close()

    async def open(self):
        loop = events.get_running_loop()
        reader = asyncio.StreamReader(loop=loop)
        protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
        transport, _ = await loop.create_connection(protocol_factory=lambda: protocol, host=self.host, port=self.port)
        self.writer = asyncio.StreamWriter(transport, protocol, reader, loop)
        self.reader = reader

    async def close(self):
        if self.writer is not None:
            self.writer.close()
            self.writer = None
            self.reader = None

    async def read_byte(self) -> int:
        loop = asyncio.get_running_loop()
        # chunk = await loop.sock_recv(self.sock, 1)
        chunk = await self.reader.readexactly(1)
        self.last_activity = loop.time()
        return chunk[0]

    async def write_bytes(self, data: List[int]):
        loop = asyncio.get_running_loop()
        # await loop.sock_sendall(self.sock, bytes(data))
        self.writer.write(bytes(data))
        await self.writer.drain()
        self.last_activity = loop.time()

    def get_last_activity(self):
        return self.last_activity


# This class runs as a background task of the communicator, making sure that the TCP connection does not
# get blocked once the read buffer overflows. It additionally can attempt to parse the bus traffic and
# look for valid Somfy SDN messages.
class _Drainer(object):
    def __init__(self, channel: Channel, lock: asyncio.Lock, need_to_talk: asyncio.Event,
                 sniffer_callback: Callable[[SomfyMessage], None] = None):
        self.channel = channel
        self.lock = lock
        self.need_to_talk = need_to_talk
        self.sniffer_callback = sniffer_callback
        self.message_recognizer = MessageRecognizer()

    async def run_loop(self):
        try:
            while True:
                await self.attempt_drain()
        except asyncio.CancelledError:
            pass

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

                _, undone = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
                for u in undone:
                    u.cancel()

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


class SomfyConnector(object):
    channel: Channel = None

    def __init__(self, channel: Channel, sniffer_callback: Callable[[SomfyMessage], None] = None):
        self.channel = channel
        self.reader_lock = asyncio.Lock()
        self.need_to_talk = asyncio.Event()
        self.writer_lock = asyncio.Lock()
        self.drainer = _Drainer(channel, self.reader_lock, self.need_to_talk, sniffer_callback)
        self.timeout = COMMUNICATION_TIMEOUT_SEC
        self.last_write_time = 0

    async def __aenter__(self) -> "SomfyConnector":
        self.drainer_task = asyncio.create_task(name="SDNBusDrainer", coro=self.drainer.run_loop())
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
                        traceback: Optional[TracebackType]):
        self.drainer_task.cancel()
        await self.drainer_task
        return None

    async def fire_and_forget(self, to_send: SomfyMessage):
        async with self.writer_lock:
            # Signal the drainer task that we want to talk with the SDN network and that it needs to stop
            # draining the data.
            self.need_to_talk.set()
            try:
                async with self.reader_lock:
                    async with asyncio.timeout(self.timeout):
                        await self.channel.write_bytes(to_send.serialize())
            finally:
                self.need_to_talk.clear()

    async def exchange(self, to_send: Optional[SomfyMessage],
                       msg_filter: Callable[[SomfyMessage], Tuple[bool, bool]]) -> List[SomfyMessage]:
        async with self.writer_lock:
            # Signal the drainer task that we want to talk with the SDN network and that it needs to stop
            # draining the data.
            self.need_to_talk.set()
            try:
                async with self.reader_lock:
                    async with asyncio.timeout(self.timeout):
                        return await self._do_exchange(to_send, msg_filter)
            finally:
                self.need_to_talk.clear()

    async def _do_exchange(self, to_send: Optional[SomfyMessage],
                           msg_filter: Callable[[SomfyMessage], Tuple[bool, bool]]) -> List[SomfyMessage]:
        res: List[SomfyMessage] = []

        if to_send is not None:
            await self.channel.write_bytes(to_send.serialize())

        recognizer = MessageRecognizer()
        while True:
            bt = await self.channel.read_byte()
            msg = recognizer.add_data(bt)
            if msg is not None:
                passed, keep_going = msg_filter(msg)
                if passed:
                    res.append(msg)
                if not keep_going:
                    return res

    # Attempt to detect Somfy devices on the SDN bus. Always waits for the communication timeout
    async def detect_devices(self, node_type: NodeType = NodeType.TYPE_ALL) -> List[Tuple[SomfyAddress, NodeType]]:
        detect_nodes = SomfyMessage(msgid=SomfyMessageId.GET_NODE_ADDR,
                                    from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                                    to_node_type=node_type, to_addr=BROADCAST_ADDR)
        nodes: List[Tuple[SomfyAddress, NodeType]] = []

        try:
            # Gather the node addresses
            def gather_addr(msg: SomfyMessage) -> (bool, bool):
                if (msg.msgid == SomfyMessageId.POST_NODE_ADDR and
                        (node_type == NodeType.TYPE_ALL or msg.from_node_type == node_type)):
                    nodes.append((msg.from_addr, msg.from_node_type))
                return False, True

            await self.exchange(detect_nodes, gather_addr)
        except asyncio.TimeoutError:
            # We expect to end up with the timeout error here, as we try to gather all the replies
            pass

        return nodes

    async def exchange_one(self, addr: SomfyAddress, msgid: SomfyMessageId, expected_reply: SomfyMessageId,
                           payload: Optional[SomfyPayload] = SomfyPayload([])) -> Optional[SomfyMessage]:

        def filter_type(msg: SomfyMessage):
            passed = msg.from_addr == addr and msg.msgid == expected_reply
            return passed, not passed  # Accepted?, continue?

        sent = SomfyMessage(msgid=msgid, from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                            to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=payload)
        try:
            messages = await self.exchange(sent, filter_type)
            if len(messages) == 0:
                return None
        except asyncio.TimeoutError:
            return None

        return messages[0]
