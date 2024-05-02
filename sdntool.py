#!/usr/bin/env python3
import asyncio
import typing
from optparse import OptionParser

from somfy.connector import SomfyConnector, SocketConnectionFactory, fire_and_forget, detect_devices, \
    try_to_exchange_one, ReconnectingSomfyConnector
from somfy.enumutils import hex_enum
from somfy.messages import SomfyMessage, SomfyMessageId, MASTER_ADDRESS, NodeType, SomfyAddress
from somfy.payloads import MotorRotationDirectionPayload, PostMotorLimitsPayload, PostMotorPositionPayload, \
    CtrlMoveToPayload, CtrlMoveToFunction, CtrlStopPayload, CtrlMoveRelativePayload, RelativeMoveFunction, \
    PostMotorStatusPayload, SomfyNackReason, MotorRotationDirection
from somfy.serial import SerialConnectionFactory
from somfy.utils import wait_for_completion, SomfyNackException, send_with_ack


async def do_detect(connector: SomfyConnector):
    res = await detect_devices(connector)
    for d, t in res:
        print("%s\t%s" % (d, t))


async def do_info(connector: SomfyConnector, opts):
    if not opts.addr:
        raise Exception("No --addr specified")
    addr = SomfyAddress.make(opts.addr)

    reply = await try_to_exchange_one(connector, addr, SomfyMessageId.GET_MOTOR_ROTATION_DIRECTION,
                                      SomfyMessageId.POST_MOTOR_ROTATION_DIRECTION)
    if not reply:
        raise Exception("Failed to get motor rotation direction")

    rot = typing.cast(MotorRotationDirectionPayload, reply.payload)
    print("Rotation direction\t%s" % rot.get_direction())

    reply = await try_to_exchange_one(connector, addr, SomfyMessageId.GET_MOTOR_LIMITS,
                                      SomfyMessageId.POST_MOTOR_LIMITS)
    if not reply:
        raise Exception("Failed to get motor limits")
    lim = typing.cast(PostMotorLimitsPayload, reply.payload)
    print("Limit (in pulses)\t%d" % lim.get_limit())

    reply = await try_to_exchange_one(connector, addr, SomfyMessageId.GET_MOTOR_POSITION,
                                      SomfyMessageId.POST_MOTOR_POSITION)
    if not reply:
        raise Exception("Failed to get motor position")
    pos = typing.cast(PostMotorPositionPayload, reply.payload)
    print("Position pulses\t%d" % pos.get_position_pulses())
    print("Position percent\t%d" % pos.get_position_percent())
    print("Tilt percent\t%d" % (pos.get_tilt_percent() or -1))
    print("Tilt degrees\t%d" % (pos.get_tilt_degrees() or -1))
    print("Intermediate Position\t%d" % (pos.get_ip() or -1))

    reply = await try_to_exchange_one(connector, addr, SomfyMessageId.GET_MOTOR_STATUS,
                                      SomfyMessageId.POST_MOTOR_STATUS)
    if not reply:
        raise Exception("Failed to get motor position")
    stat = typing.cast(PostMotorStatusPayload, reply.payload)
    print("Status\t%s" % hex_enum(stat.get_status()))
    print("Direction\t%s" % hex_enum(stat.get_direction()))
    print("Command Source\t%s" % hex_enum(stat.get_command_source()))
    print("Status Cause\t%s" % hex_enum(stat.get_status_cause()))


async def do_move(connector: SomfyConnector, opts):
    if not opts.addr:
        raise Exception("No --addr specified")
    if opts.percent is None:
        raise Exception("No --percent specified")

    addr = SomfyAddress.make(opts.addr)
    payload = CtrlMoveToPayload.make(func=CtrlMoveToFunction.POSITION_PERCENT, position=int(opts.percent))
    sent = SomfyMessage(msgid=SomfyMessageId.CTRL_MOVETO, need_ack=True,
                        from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                        to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=payload)
    await send_with_ack(addr, connector, sent)

    def print_pos(p):
        print("Position: %d%% (pulses: %d), IP=%d" % (p.get_position_percent(), p.get_position_pulses(),
                                                      p.get_ip() or -1))

    await wait_for_completion(addr, connector, print_pos)


async def do_move_ip(connector, opts, move_down):
    if not opts.addr:
        raise Exception("No --addr specified")

    addr = SomfyAddress.make(opts.addr)
    payload = CtrlMoveRelativePayload.make(
        func=RelativeMoveFunction.MOVE_NEXT_IP_DOWN if move_down else RelativeMoveFunction.MOVE_NEXT_IP_UP, parameter=0)
    sent = SomfyMessage(msgid=SomfyMessageId.CTRL_MOVE_RELATIVE, need_ack=True,
                        from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                        to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=payload)
    try:
        await send_with_ack(addr, connector, sent)
    except SomfyNackException as e:
        if e.nack().get_nack_code() == SomfyNackReason.NACK_LAST_IP_REACHED:
            opts.percent = 100 if move_down else 0.0
            await do_move(connector, opts)
            return

    def print_pos(p):
        print("Position: %d%% (pulses: %d), IP=%d" % (p.get_position_percent(), p.get_position_pulses(),
                                                      p.get_ip() or -1))

    await wait_for_completion(addr, connector, print_pos)


async def do_stop(connector: SomfyConnector, opts):
    if not opts.addr:
        raise Exception("No --addr specified")

    addr = SomfyAddress.make(opts.addr)
    stop_msg = SomfyMessage(msgid=SomfyMessageId.CTRL_STOP, need_ack=True,
                            from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                            to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=CtrlStopPayload.make())
    await fire_and_forget(connector, stop_msg)


async def do_invert(connector: SomfyConnector, opts):
    if not opts.addr:
        raise Exception("No --addr specified")

    addr = SomfyAddress.make(opts.addr)
    reply = await try_to_exchange_one(connector, addr, SomfyMessageId.GET_MOTOR_ROTATION_DIRECTION,
                                      SomfyMessageId.POST_MOTOR_ROTATION_DIRECTION)
    if not reply:
        raise Exception("Failed to get motor rotation direction")
    rot = typing.cast(MotorRotationDirectionPayload, reply.payload)

    if rot.get_direction() == MotorRotationDirection.STANDARD:
        new_payload = MotorRotationDirectionPayload.make(direction=MotorRotationDirection.REVERSED)
    else:
        new_payload = MotorRotationDirectionPayload.make(direction=MotorRotationDirection.STANDARD)

    addr = SomfyAddress.make(opts.addr)
    change = SomfyMessage(msgid=SomfyMessageId.SET_MOTOR_ROTATION_DIRECTION, need_ack=True,
                          from_node_type=NodeType.TYPE_ALL, from_addr=MASTER_ADDRESS,
                          to_node_type=NodeType.TYPE_ALL, to_addr=addr, payload=new_payload)
    await send_with_ack(addr, connector, change)
    await do_info(connector, opts)


async def run(opts, cmd):
    if opts.tcp:
        host, port = opts.tcp.split(":")
        ch = SocketConnectionFactory(host=host, port=port)
    elif opts.serial:
        ch = SerialConnectionFactory(opts.serial)
    else:
        raise Exception("Neither --tcp nor --serial options specified")

    async with ReconnectingSomfyConnector(ch) as connector:
        if cmd == "detect":
            await do_detect(connector)
        elif cmd == "info":
            await do_info(connector, opts)
        elif cmd == "move":
            await do_move(connector, opts)
        elif cmd == "stop":
            await do_stop(connector, opts)
        elif cmd == "down_step":
            await do_move_ip(connector, opts, True)
        elif cmd == "up_step":
            await do_move_ip(connector, opts, False)
        elif cmd == "invert_direction":
            await do_invert(connector, opts)
        else:
            raise Exception("Unknown command")


if __name__ == '__main__':
    parser = OptionParser("sdntool.py [options] detect|info|move|stop|down_step|up_step|invert_direction")
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
