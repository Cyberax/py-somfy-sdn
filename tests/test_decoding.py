import random
from binascii import unhexlify

from somfy.recognizer import MessageRecognizer
from somfy.messages import SomfyMessage

message_stream = """bff4ff8080800000000432
9ff47f39c2ec8080800579
9ff47f6bc2ec80808005ab
def4ff80808039c2ec0638
def4ff80808039c2ec0638
cef07f39c2ec808080ffff28c5088f
f3f4ff80808039c2ec064d
f2ef7f39c2ec8080809cf6ef00000848
def4ff80808039c2ec0638
cef07f39c2ec808080ffff28c5088f
f3f4ff80808039c2ec064d
f2ef7f39c2ec8080809cf6ef00000848
daf3ff80808039c2ecfe0731
caf07f39c2ec808080feb2cdaa08c7
daf3ff80808039c2ecfd0730
caf07f39c2ec808080fd000000069d
daf3ff80808039c2ecfc072f
caf07f39c2ec808080fc000000069c
daf3ff80808039c2ecfb072e
caf07f39c2ec808080fb000000069b
daf3ff80808039c2ecfa072d
daf3ff80808039c2ecf9072c
caf07f39c2ec808080fa000000069a
daf3ff80808039c2ecf8072b
caf07f39c2ec808080f90000000699
daf3ff80808039c2ecf7072a
caf07f39c2ec808080f80000000698
daf3ff80808039c2ecf60729
caf07f39c2ec808080f70000000697
daf3ff80808039c2ecf50728
caf07f39c2ec808080f60000000696
daf3ff80808039c2ecf40727
caf07f39c2ec808080f50000000695
daf3ff80808039c2ecf30726
caf07f39c2ec808080f40000000694
daf3ff80808039c2ecf20725
caf07f39c2ec808080f30000000693
daf3ff80808039c2ecf10724
caf07f39c2ec808080f20000000692
daf3ff80808039c2ecf00723
caf07f39c2ec808080f10000000691
daf3ff80808039c2ecef0722
caf07f39c2ec808080f00000000690
caf07f39c2ec808080ef000000068f
dcf4ff80808039c2ec0636
ccf17f39c2ec808080e6e6f0085f
fbf0ff80808039c2ecffffffff0a4d
def4ff80808039c2ec0638
cef07f39c2ec808080ffff28c5088f
f3f4ff80808039c2ec064d
f2ef7f39c2ec808080c5f2e900000867
def4ff80808039c2ec0638
cef07f39c2ec808080ffff28c5088f
f3f4ff80808039c2ec064d
f2ef7f39c2ec808080afeee200000846
def4ff80808039c2ec0638
cef07f39c2ec808080ffff28c5088f
f3f4ff80808039c2ec064d
f2ef7f39c2ec80808062eada000007ed
def4ff80808039c2ec0638
cef07f39c2ec808080ffff28c5088f
f3f4ff80808039c2ec064d
f2ef7f39c2ec8080802ae6d3000007aa
def4ff80808039c2ec0638
cef07f39c2ec808080ffff28c5088f
f3f4ff80808039c2ec064d
f2ef7f39c2ec808080e0cfad00000823"""

decoded_stream = """ID: 40(GET_NODE_ADDR) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) FFFFFF ACK: False DATA: {}
ID: 60(POST_NODE_ADDR) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {}
ID: 60(POST_NODE_ADDR) FROM: 08(TYPE_50DC_SERIES) 133D94 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 0D(POST_MOTOR_POSITION) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'position_pulses': 2403, 'position_percent': 16, 'tilt_percent': 255, 'ip': None, 'tilt_degrees': None}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 0D(POST_MOTOR_POSITION) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'position_pulses': 2403, 'position_percent': 16, 'tilt_percent': 255, 'ip': None, 'tilt_degrees': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 1}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 1, 'position': 50, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 2}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 2, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 3}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 3, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 4}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 4, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 5}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 6}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 5, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 7}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 6, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 8}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 7, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 9}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 8, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 10}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 9, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 11}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 10, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 12}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 11, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 13}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 12, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 14}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 13, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 15}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 14, 'position': 255, 'angle': None}
ID: 25(GET_MOTOR_IP) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'ip_index': 16}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 15, 'position': 255, 'angle': None}
ID: 35(POST_MOTOR_IP) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'ip_index': 16, 'position': 255, 'angle': None}
ID: 23(GET_MOTOR_ROLLING_SPEED) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 33(POST_MOTOR_ROLLING_SPEED) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'up_speed_rpm': 25, 'down_speed_rpm': 25, 'slow_speed_rpm': 15}
ID: 04(CTRL_MOVE_RELATIVE) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {'function': <RelativeMoveFunction.MOVE_NEXT_IP_DOWN: 0>, 'parameter': 0}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 0D(POST_MOTOR_POSITION) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'position_pulses': 3386, 'position_percent': 22, 'tilt_percent': 255, 'ip': None, 'tilt_degrees': None}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 0D(POST_MOTOR_POSITION) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'position_pulses': 4432, 'position_percent': 29, 'tilt_percent': 255, 'ip': None, 'tilt_degrees': None}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 0D(POST_MOTOR_POSITION) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'position_pulses': 5533, 'position_percent': 37, 'tilt_percent': 255, 'ip': None, 'tilt_degrees': None}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 0D(POST_MOTOR_POSITION) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'position_pulses': 6613, 'position_percent': 44, 'tilt_percent': 255, 'ip': None, 'tilt_degrees': None}
ID: 21(GET_MOTOR_LIMITS) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 31(POST_MOTOR_LIMITS) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'reserved': 0, 'limit': 15063}
ID: 0C(GET_MOTOR_POSITION) FROM: 00(TYPE_ALL) 7F7F7F TO: 00(TYPE_ALL) 133DC6 ACK: False DATA: {}
ID: 0D(POST_MOTOR_POSITION) FROM: 08(TYPE_50DC_SERIES) 133DC6 TO: 00(TYPE_ALL) 7F7F7F ACK: False DATA: {'position_pulses': 12319, 'position_percent': 82, 'tilt_percent': 255, 'ip': None, 'tilt_degrees': None}"""


# Check that we can decode a simple captures session
def test_decoding() -> None:
    mr = MessageRecognizer()
    messages = list[SomfyMessage]()
    decoded_bytes = unhexlify(message_stream.replace("\n", "").replace("\r", ""))
    msg_bytes = []
    for bt in decoded_bytes:
        cur_msg = mr.add_data(bt)
        msg_bytes.append(bt)
        if cur_msg is not None:
            messages.append(cur_msg)
            # Check round-tripping (the serialized message must be equal to the source bytes)
            r1 = cur_msg.serialize()
            assert r1 == bytes(msg_bytes)
            m2 = SomfyMessage.try_parse(r1)
            assert m2.as_dict() == cur_msg.as_dict()
            msg_bytes = []

    expected_messages = decoded_stream.split("\n")
    assert len(expected_messages) == len(messages)
    for i in range(0, len(messages)):
        assert messages[i].__str__() == expected_messages[i]


# Test that the recognizer can deal with the noisy input
def test_recognizer() -> None:
    mr = MessageRecognizer()
    messages = list[SomfyMessage]()

    # Deterministic seeded generator:
    rand = random.Random(x=4)  # IEEE-vetted standard random number!
    # We don't use crypto-safe randoms for a slim chance that the generated bytes
    # just happen to form a real message.

    for msg in message_stream.splitlines(keepends=False):
        # Add some noise!
        for i in range(0, rand.randrange(0, 100)):
            mr.add_data(rand.randbytes(1)[0])
        # The rest of the message
        for bt in unhexlify(msg):
            cur_msg = mr.add_data(bt)
            if cur_msg is not None:
                messages.append(cur_msg)
        # More noise!
        for i in range(0, rand.randrange(0, 100)):
            mr.add_data(rand.randbytes(1)[0])

    expected_messages = decoded_stream.split("\n")
    assert len(expected_messages) <= len(messages)
    for i in range(0, len(messages)):
        assert messages[i].__str__() == expected_messages[i]
