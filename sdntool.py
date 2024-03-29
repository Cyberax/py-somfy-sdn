#!/usr/bin/env python3
import asyncio
import typing
from asyncio import get_event_loop
from optparse import OptionParser

from somfy.connector import SomfyConnector, SocketChannel
from somfy.messages import SomfyMessage, SomfyMessageId, MASTER_ADDRESS, NodeType, SomfyAddress
from somfy.payloads import MotorRotationDirectionPayload, PostMotorLimitsPayload, PostMotorPositionPayload, \
    CtrlMoveToPayload, CtrlMoveToFunction, CtrlStopPayload, NackPayload
from somfy.serial import SerialChannel


async def do_detect(connector: SomfyConnector):
    res = await connector.detect_devices()
    for d, t in res:
        print("%s\t%s" % (d, t))


async def do_info(connector: SomfyConnector, opts):
    if not opts.addr:
        raise Exception("No --addr specified")
    addr = SomfyAddress.make(opts.addr)

    reply = await connector.exchange_one(addr, SomfyMessageId.GET_MOTOR_ROTATION_DIRECTION,
                                         SomfyMessageId.POST_MOTOR_ROTATION_DIRECTION)
    if not reply:
        raise Exception("Failed to get motor rotation direction")

    rot = typing.cast(MotorRotationDirectionPayload, reply.payload)
    print("Rotation direction\t%s" % rot.get_direction())

    reply = await connector.exchange_one(addr, SomfyMessageId.GET_MOTOR_LIMITS, SomfyMessageId.POST_MOTOR_LIMITS)
    if not reply:
        raise Exception("Failed to get motor limits")
    lim = typing.cast(PostMotorLimitsPayload, reply.payload)
    print("Limit (in pulses)\t%d" % lim.get_limit())

    reply = await connector.exchange_one(addr, SomfyMessageId.GET_MOTOR_POSITION, SomfyMessageId.POST_MOTOR_POSITION)
    if not reply:
        raise Exception("Failed to get motor position")
    pos = typing.cast(PostMotorPositionPayload, reply.payload)
    print("Position pulses\t%d" % pos.get_position_pulses())
    print("Position percent\t%d" % pos.get_position_percent())
    print("Tilt percent\t%d" % (pos.get_tilt_percent() or -1))
    print("Tilt degrees\t%d" % (pos.get_tilt_degrees() or -1))
    print("Intermediate Position\t%d" % (pos.get_ip() or -1))


async def do_move(connector: SomfyConnector, opts):
    if not opts.addr:
        raise Exception("No --addr specified")
    if not opts.percent:
        raise Exception("No --percent specified")

    addr = SomfyAddress.make(opts.addr)

    def filter_type(msg: SomfyMessage):
        passed = msg.from_addr == addr and msg.msgid in [SomfyMessageId.ACK, SomfyMessageId.NACK]
        return passed, not passed  # Accepted?, continue?

    payload = CtrlMoveToPayload.make(func=CtrlMoveToFunction.POSITION_PERCENT, position=int(opts.percent))
    sent = SomfyMessage(msgid=SomfyMessageId.CTRL_MOVETO, need_ack=True,
                        from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                        to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=payload)
    try:
        messages = await connector.exchange(sent, filter_type)
        if len(messages) == 0:
            raise Exception("No ACK or NACK messages")
    except asyncio.TimeoutError:
        raise Exception("Move command timed out")

    if messages[0].msgid == SomfyMessageId.NACK:
        raise Exception("NACK received, reason: %s" % typing.cast(NackPayload, messages[0].payload).get_nack_code())
    elif messages[0].msgid != SomfyMessageId.ACK:
        raise Exception("Move command failed")

    await wait_for_completion(addr, connector)


async def wait_for_completion(addr, connector):
    loop = get_event_loop()
    last_change_time = loop.time()
    last_pulses = 0
    # Keep polling while the shades are moving
    while loop.time() - last_change_time <= 3:
        reply = await connector.exchange_one(addr, SomfyMessageId.GET_MOTOR_POSITION,
                                             SomfyMessageId.POST_MOTOR_POSITION)
        if reply:
            pos = typing.cast(PostMotorPositionPayload, reply.payload)
            if pos.get_position_pulses() != last_pulses:
                last_pulses = pos.get_position_pulses()
                last_change_time = loop.time()
            print("Position: %d%% (pulses: %d), IP=%d" % (pos.get_position_percent(), pos.get_position_pulses(),
                                                          pos.get_ip() or -1))

        await asyncio.sleep(0.5)


async def do_stop(connector: SomfyConnector, opts):
    if not opts.addr:
        raise Exception("No --addr specified")

    addr = SomfyAddress.make(opts.addr)
    sent = SomfyMessage(msgid=SomfyMessageId.CTRL_STOP, need_ack=True,
                        from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                        to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=CtrlStopPayload.make())
    await connector.exchange(sent, lambda o: (False, False))


async def run(opts, cmd):
    if opts.tcp:
        host, port = opts.tcp.split(":")
        ch = SocketChannel(host=host, port=port)
    elif opts.serial:
        ch = SerialChannel(opts.serial)
    else:
        raise Exception("Neither --tcp nor --serial options specified")

    async with ch:
        async with SomfyConnector(ch) as connector:
            if cmd == "detect":
                await do_detect(connector)
            elif cmd == "info":
                await do_info(connector, opts)
            elif cmd == "move":
                await do_move(connector, opts)
            elif cmd == "stop":
                await do_stop(connector, opts)
            else:
                raise Exception("Unknown command")


if __name__ == '__main__':
    parser = OptionParser("sdntool.py [options] detect|info|move|stop")
    parser.add_option("--tcp", dest="tcp",
                      help="use the TCP endpoint for the Somfy connection (host:port)")
    parser.add_option("--serial", dest="serial",
                      help="use directly attached RS-485 serial device (/dev/tty<...>)")
    parser.add_option("--addr", dest="addr", help="The Somfy device address")
    parser.add_option("--percent", dest="percent", help="The percentage (0-100) for the move command")
    (options, args) = parser.parse_args()

    if len(args) == 0:
        parser.print_usage()
        exit(1)

    asyncio.run(run(options, args[0]))
