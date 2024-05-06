#!/usr/bin/env python3
import asyncio
import json
from optparse import OptionParser
from typing import Optional

from somfy.connector import SomfyConnector, SocketConnectionFactory, ReconnectingSomfyConnector
from somfy.messages import SomfyMessage, SomfyAddress
from somfy.serial import SerialConnectionFactory


async def sniff(opts):
    if opts.tcp:
        host, port = opts.tcp.split(":")
        ch = SocketConnectionFactory(host=host, port=port)
    elif opts.serial:
        ch = SerialConnectionFactory(opts.serial)
    else:
        raise Exception("Neither --tcp nor --serial options specified")

    addr: Optional[SomfyAddress] = None
    if opts.addr:
        addr = SomfyAddress.make(opts.addr)

    def on_message(msg: SomfyMessage):
        if addr and (msg.from_addr != addr and msg.to_addr != addr):
            return
        if opts.as_dict:
            print(msg.as_dict())
        elif opts.as_json:
            print(json.dumps(msg.as_dict(), sort_keys=True, default=lambda o: o.to_json()))
        else:
            print(msg.__str__())

    async with ReconnectingSomfyConnector(ch, sniffer_callback=on_message) as conn:
        try:
            await conn.done_notification().wait()
        except asyncio.CancelledError:
            pass


if __name__ == '__main__':
    parser = OptionParser("sniffer.py [options]")
    parser.add_option("--tcp", dest="tcp",
                      help="use the TCP endpoint for the Somfy connection (host:port)")
    parser.add_option("--serial", dest="serial",
                      help="use directly attached RS-485 serial device (/dev/tty<...>)")
    parser.add_option("--addr", dest="addr", help="The Somfy source/dest device address")
    parser.add_option("-j", "--json", action="store_true", dest="as_json",
                      help="use JSON output")
    parser.add_option("-d", "--dict", action="store_true", dest="as_dict",
                      help="use augmented dict output")
    (options, args) = parser.parse_args()

    asyncio.run(sniff(options))
