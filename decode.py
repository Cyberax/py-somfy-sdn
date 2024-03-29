#!/usr/bin/env python3
import json
import sys
from binascii import unhexlify
from optparse import OptionParser

from somfy.recognizer import MessageRecognizer


def do_read(input_stream, as_json, as_dict):
    mr = MessageRecognizer()
    b1 = None
    while True:
        hexdata = input_stream.read(1)
        if not hexdata:
            break
        for hexpart in hexdata:
            if chr(hexpart) not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                                    'A', 'B', 'C', 'D', 'E', 'F', 'a', 'b', 'c', 'd', 'e', 'f']:
                continue
            if b1 is not None:
                byte = unhexlify(chr(b1) + chr(hexpart))
                b1 = None
                msg = mr.add_data(byte[0])
                if msg:
                    if as_dict:
                        print(msg.as_dict())
                    elif as_json:
                        print(json.dumps(msg.as_dict(), sort_keys=True, default=lambda o: o.to_json()))
                    else:
                        print(msg.__str__())
            else:
                b1 = hexpart


if __name__ == '__main__':
    parser = OptionParser("decode.py [options]")
    parser.add_option("-f", "--file", dest="filename",
                      help="read data from FILENAME instead of stdin")
    parser.add_option("-j", "--json", action="store_true", dest="json",
                      help="use JSON output")
    parser.add_option("-d", "--dict", action="store_true", dest="as_dict",
                      help="use augmented dict output")
    (options, args) = parser.parse_args()

    if options.filename:
        with open(options.filename, 'rb') as f:
            do_read(f, options.json, options.as_dict)
    else:
        do_read(sys.stdin.buffer, options.json, options.as_dict)
