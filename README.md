# Somfy SDN protocol support

This library implements Somfy SDN protocol used to control Somfy RS-485 connected blinds and shades. 
It can also control Somfy SDN keypads, and it can be straightforwardly extended to support other types 
of SDN devices.

# Using the library

The library supports both directly-connected RS-485 adapters (typically implemented as USB-serial adapters), and
connections via Ethernet-to-Serial converters. The library properly implements the timing restrictions specified
in the SDN Integration Guide, with full `asyncio` support.

To use the library, create a channel, a connector, and then exchange the messages:

```python
from somfy import SocketChannel
ch = SocketChannel(host=host, port=port)
async with ch:
    async with SomfyConnector(ch) as conn:
        await conn.do_exchange(...)
        await conn.do_exchange(...)
        await conn.do_exchange(...)
```

The channel (socket or serial) is physically opened in the context manager's `__aenter__` and freed in the `__aexit__`,
there is no support for reconnection. If the socket is closed or the serial device becomes unavailable, you need to
close the `SomfyConnector`, `Channel`, and then create new ones.

`SomfyConnector` is stateless, but it launches a background task that drains the data from the SDN bus. You can
optionally specify a `sniffer_callback` that will be called each time the "drainer" task recognizes a valid SDN 
message. The drainer task is paused during the message exchanges.

# Tools

There are several tools provided both as an example and as simple SDN management tools.

## decode.py

This is a simple decoder for SDN messages. The input must be binhex-formatted, you can use `stdin` or a file. 
The output can be in the form of text, json, and Python dicts.

```bash
$ echo "cef07f39c2ec808080ffff28c5088f\nf3f4ff80808039c2ec064d" | ./decode.py
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
```

## sdntool.py

This tool can be used to detect devices in the SDN network, and to control shades. 

Detecting:
```bash
$ ./sdntool.py --tcp 192.168.20.32:1226 detect
133DC6	TYPE_50DC_SERIES
```

Getting information about a device:
```bash
$ ./sdntool.py --tcp 192.168.20.32:1226 info --addr 133DC6
Rotation direction	STANDARD
Limit (in pulses)	14930
Position pulses	1492
Position percent	10
Tilt percent	255
Tilt degrees	-1
Intermediate Position	-1
```

Commanding a device:
```bash
$ ./sdntool.py --tcp 192.168.20.32:1226 move --addr 133DC6 --percent 44
Position: 38% (pulses: 5717), IP=-1
Position: 42% (pulses: 6312), IP=-1
Position: 44% (pulses: 6538), IP=-1
Position: 44% (pulses: 6570), IP=-1
Position: 44% (pulses: 6570), IP=-1
Position: 44% (pulses: 6570), IP=-1
Position: 44% (pulses: 6570), IP=-1
```

## sniffer.py

This tool can be used to passively listen on the RS-485 bus, it supports JSON, text, and dict output.

# Information sources

## Documentation

This library was started first based on information gleaned from reverse-engineering the protocol by observing the
communication between Somfy-provided tools and Somfy shades. This information was used to make the
https://github.com/Cyberax/ZunoSomfy project, to build a hardware device to control the shades. They worked relatively
well, but ZWave has its own problems, so I decided to add support to HomeAssistant directly.

So this is how this library got developed. After a couple of days of research, I found that Somfy has published an
integration guide that describes the SDN protocol. The document is publicly available, but it's copyrighted. You
can find it by this number: DOC155888/002 ("Integration Guide"), at the time of the writing it is available at:
https://service.somfy.com/downloads/bui_v4/sdn-integration-guide-rev.002.pdf

## Somfy Tools

Somfy provides downloads for several tools at: https://www.somfypro.com/services-support/software

The tools of interest are `Somfy Digital Network™ (SDN) Motor Configuration Software 5.1` and `SDN Configuration Tool
Version: 1.2.4.2`. These tools can be used for straightforward protocol reverse-engineering (i.e. add a sniffer to
the bus, perform an action inside the software and observe the result), and the `SDN Configuration Tool` additionally
provides a helpful `Analyze` feature that shows decoded traces of the bus traffic.

# Short protocol description

The protocol is a bit convoluted, but it's not complicated. The message frames are 11 to 32 bytes long, and are
transmitted on the RS-485 bus at 4800bps, with an _odd_ parity bit, 8 data bits and 1 start/stop bit. The minimum 
interval between messages transmitted by the master node is 25ms. The reply timeout for devices is 280ms.

The node addresses are 3 byte-long. The broadcast address ix `FFFFFF`, the MASTER node is typically `7F7F7F`. A typical 
exchange starts with `SET/GET_....` message sent by the MASTER node, to which the destination node (or nodes) reply 
with the appropriate `POST_...` messages.

The format of the message serialization is documented in `somfy/messages.py`. One thing to note, is that message bytes
are bitwise-inverted prior to computing the checksum and sending them.