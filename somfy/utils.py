import asyncio
import typing
from asyncio import get_event_loop

from somfy.connector import SomfyExchanger, try_to_exchange_one
from somfy.messages import SomfyMessage, SomfyMessageId, SomfyAddress
from somfy.payloads import NackPayload, PostMotorPositionPayload


class SomfyException(Exception):
    pass


class SomfyNackException(SomfyException):
    def __init__(self, nack: NackPayload):
        self.nack_data = nack
        super().__init__("NACK received, reason: %s" % nack.get_nack_code())

    def nack(self) -> NackPayload:
        return self.nack_data


async def move_with_ack(addr, connector: SomfyExchanger, to_sent: SomfyMessage):
    ack_or_nack: typing.Optional[SomfyMessage] = None

    def filter_type(msg: SomfyMessage):
        if msg.from_addr == addr and msg.msgid in [SomfyMessageId.ACK, SomfyMessageId.NACK]:
            nonlocal ack_or_nack
            ack_or_nack = msg
            return False
        return True

    try:
        await connector.exchange(to_sent, filter_type)
        if ack_or_nack is None:
            raise SomfyException("No ACK or NACK messages")
    except asyncio.TimeoutError:
        raise SomfyException("Command timed out")
    if ack_or_nack.msgid == SomfyMessageId.NACK:
        raise SomfyNackException(typing.cast(NackPayload, ack_or_nack.payload))
    elif ack_or_nack.msgid != SomfyMessageId.ACK:
        raise SomfyException("Command failed")


async def wait_for_completion(addr: SomfyAddress, connector: SomfyExchanger,
                              progres_callback: typing.Callable[[PostMotorPositionPayload], None]):
    loop = get_event_loop()
    last_change_time = loop.time()
    last_pulses = 0
    # Keep polling while the shades are moving
    while loop.time() - last_change_time <= 1:
        reply = await try_to_exchange_one(connector, addr, SomfyMessageId.GET_MOTOR_POSITION,
                                          SomfyMessageId.POST_MOTOR_POSITION)
        if reply:
            pos = typing.cast(PostMotorPositionPayload, reply.payload)
            if pos.get_position_pulses() != last_pulses:
                last_pulses = pos.get_position_pulses()
                last_change_time = loop.time()
            if progres_callback:
                progres_callback(pos)

        await asyncio.sleep(0.5)

