# Messages specification
from binascii import unhexlify
from typing import List, Optional, Any

from somfy.enumutils import enum_or_int, hex_enum, IntEnumWithStr


# The destination flag. Only the matching devices will process the message if the flag is set.
class NodeType(IntEnumWithStr):
    TYPE_ALL = 0x00
    TYPE_30DC_SERIES = 0x02
    TYPE_RTS_TRANSMITTER = 0x05
    TYPE_GLYDEA = 0x06
    TYPE_50AC_SERIES = 0x07
    TYPE_50DC_SERIES = 0x08
    TYPE_40AC_SERIES = 0x09


########################################################################
# SDN message types defined in the spec for window covers (DOC155888/2)
########################################################################
class SomfyMessageId(IntEnumWithStr):
    GET_NODE_ADDR = 0x40
    POST_NODE_ADDR = 0x60

    SET_GROUP_ADDR = 0x51
    GET_GROUP_ADDR = 0x41
    POST_GROUP_ADDR = 0x61

    ACK = 0x7F
    NACK = 0x6F

    GET_NODE_APP_VERSION = 0x74
    POST_NODE_APP_VERSION = 0x75

    SET_NODE_LABEL = 0x55
    GET_NODE_LABEL = 0x45
    POST_NODE_LABEL = 0x65

    SET_LOCAL_UI = 0x17
    GET_LOCAL_UI = 0x27
    POST_LOCAL_UI = 0x37

    SET_MOTOR_IP = 0x15
    GET_MOTOR_IP = 0x25
    POST_MOTOR_IP = 0x35

    SET_MOTOR_ROLLING_SPEED = 0x13
    GET_MOTOR_ROLLING_SPEED = 0x23
    POST_MOTOR_ROLLING_SPEED = 0x33

    SET_NETWORK_LOCK = 0x16
    GET_NETWORK_LOCK = 0x26
    POST_NETWORK_LOCK = 0x36

    CTRL_WINK = 0x05
    CTRL_MOVETO = 0x03
    CTRL_STOP = 0x02

    GET_MOTOR_POSITION = 0x0C
    POST_MOTOR_POSITION = 0x0D

    GET_MOTOR_STATUS = 0x0E
    POST_MOTOR_STATUS = 0x0F

    # WARNING! WARNING!
    # The following descriptions were obtained from reverse-engineering. Treat with caution.
    CTRL_MOVE_FORCED = 0x01  # Move outside of bounds
    CTRL_MOVE_RELATIVE = 0x04  # Move relative to the current position (within bounds)

    SET_MOTOR_LIMITS = 0x11
    GET_MOTOR_LIMITS = 0x21
    POST_MOTOR_LIMITS = 0x31

    SET_MOTOR_ROTATION_DIRECTION = 0x12
    GET_MOTOR_ROTATION_DIRECTION = 0x22
    POST_MOTOR_ROTATION_DIRECTION = 0x32

# From other sources:
#     'GET_NODE_ADDR': 0x50,
#     'GET_NODE_SERIAL_NUMBER': 0x5C,
#     'GET_NETWORK_ERROR_STAT': 0x5D,
#     'GET_NETWORK_STAT': 0x5E,
#     'GET_LOCK': 0x4B,
#     'SET_LOCK': 0x5B,


# Somfy SDN node address, they are unique within a given Somfy network. 3 bytes.
class SomfyAddress(object):
    def __init__(self, a: int, b: int, c: int):
        self.a = a
        self.b = b
        self.c = c

    def serialize(self) -> List[int]:
        res = [self.c, self.b, self.a]
        return [f for f in res]

    def __str__(self) -> str:
        return "%02X%02X%02X" % (self.a, self.b, self.c)

    def __eq__(self, other):
        return self.a == other.a and self.b == other.b and self.c == other.c

    def __repr__(self) -> str:
        return self.__str__()

    def to_json(self):
        return self.__str__()

    @classmethod
    def parse_bytes(cls, raw_bytes) -> 'SomfyAddress':
        return SomfyAddress(raw_bytes[2], raw_bytes[1], raw_bytes[0])

    @staticmethod
    def make(addr: str) -> 'SomfyAddress':
        buf = unhexlify(addr)
        if len(buf) != 3:
            raise ValueError("Invalid address")
        return SomfyAddress(buf[0], buf[1], buf[2])


MASTER_ADDRESS = SomfyAddress(0x7F, 0x7F, 0x7F)  # The MASTER node pseudo-address
BROADCAST_ADDR = SomfyAddress(0xFF, 0xFF, 0xFF)  # Broadcast address, useful for node discovery


# Message payload, see payloads.py for the list of typesafe wrappers
class SomfyPayload(object):
    expected_lengths: Optional[list[int]] = None

    def __init__(self, content: List[int]):
        for p in content:
            if p < 0 or p > 255:
                raise ValueError("Content should contain valid bytes")
        if self.expected_lengths is not None and len(content) not in self.expected_lengths:
            raise ValueError("Invalid length")
        self.content = content

    def serialize(self) -> List[int]:
        return self.content

    # Override in derived classes to provide nicer info
    def as_dict(self):
        if len(self.content) == 0:
            return {}
        return {"bytes": ''.join('{:02X} '.format(x) for x in self.content).strip()}

    def __str__(self):
        return str(self.as_dict())


MESSAGE_PAYLOAD_MAP = dict[int, type]()


# Register typesafe wrappers for payloads
def register_message_payloads(payloads: dict[int, type]):
    global MESSAGE_PAYLOAD_MAP
    for k, v in payloads.items():
        MESSAGE_PAYLOAD_MAP[k] = v


# Try to parse the payload for the given message id and create a typesafe wrapper, return a generic
# SomfyPayload if the message can't be parsed.
def attempt_to_parse_payload(msgid: SomfyMessageId | int, content: list[int]) -> SomfyPayload:
    global MESSAGE_PAYLOAD_MAP
    payload_class = MESSAGE_PAYLOAD_MAP.get(msgid, None)
    if payload_class is None:
        return SomfyPayload(content)
    return payload_class(content)


#####################################################################################################
# Represents Somfy SDN messages. The messages are bitwise inverted prior to check-summing and
# transmission. The un-inverted format is:
#
# (msg_id, len, addr_types, from_addr[2], from_addr[1], from_addr[0],
#  to_addr[2], to_addr[1], to_addr[0], [<payload_bytes>], checksum[1], checksum[0])

# msg_id - the message ID (see SomfyMessageId)
# len - the total message length (including the checksum), the minimum value is 11, max is 32,
#       the most significant bit indicates that an ACK/NACK is requested.
# addr_types - the most significant 4 bits denote the source node type, the 4 least significant
#              bits denote the destination type. Types are listed in NodeType enum.
# from_addr, to_addr - the source and destination addresses, the bytes are in the big-endian order
# [<payload_bytes>] - optional command-specific payload, see payloads.py for the list of
#                     typesafe wrappers.
# checksum - the sum of message bytes, after bitwise inversion. The checksum is transmitted in
#            the big-endian order.
#
# The 16-bit payload values (such as the pulse counts) are apparently sent in the LSB order.
####################################################################################################
class SomfyMessage(object):
    def __init__(self, msgid: SomfyMessageId | int,
                 from_node_type: NodeType | int = NodeType.TYPE_ALL, from_addr: SomfyAddress = None,
                 to_node_type: NodeType | int = NodeType.TYPE_ALL, to_addr: SomfyAddress = None,
                 need_ack: bool = False, payload: SomfyPayload = SomfyPayload([])):
        self.msgid = enum_or_int(SomfyMessageId, msgid)
        self.from_node_type = enum_or_int(NodeType, from_node_type)
        self.from_addr = from_addr
        self.to_node_type = enum_or_int(NodeType, to_node_type)
        self.to_addr = to_addr
        self.need_ack = need_ack
        self.payload = payload

    def serialize(self):
        content_data = self.payload.serialize()
        ack_flag = 0x80 if self.need_ack else 0x00
        dest_type = int(self.from_node_type) << 4 | int(self.to_node_type)
        res = ([self.msgid & 0xFF, (len(content_data) + 11) | ack_flag, dest_type] +
               self.from_addr.serialize() + self.to_addr.serialize() + content_data)
        # Invert the message bytes before computing the checksum
        for i in range(0, len(res)):
            res[i] = ~res[i] & 0xFF
        return bytes(res + self.compute_checksum(res))

    def as_dict(self) -> dict[str, Any]:
        return {"msgid": self.msgid, "from_node_type": self.from_node_type, "from_addr": self.from_addr,
                "to_node_type": self.to_node_type, "to_addr": self.to_addr, "need_ack": self.need_ack,
                "payload": self.payload.as_dict()}

    def __str__(self):
        return (f"ID: {hex_enum(self.msgid)} FROM: {hex_enum(self.from_node_type)} {self.from_addr} "
                f"TO: {hex_enum(self.to_node_type)} {self.to_addr} ACK: {self.need_ack} "
                f"DATA: {self.payload}")

    @staticmethod
    def compute_checksum(msg):
        checksum = 0
        for i in msg:
            checksum += i
        return [checksum // 256 & 0xFF, checksum % 256 & 0xFF]

    @staticmethod
    def try_parse(data: List[int]) -> Optional['SomfyMessage']:
        # Validate the checksum
        checksum = SomfyMessage.compute_checksum(data[:-2])
        if checksum[0] != data[-2] or checksum[1] != data[-1]:
            return None  # Checksum mismatch

        # First, invert the data (except the checksum) to make parsing easier
        inverted = [~i & 0xFF for i in data[:-2]]

        msg_id = enum_or_int(SomfyMessageId, inverted[0])

        needs_ack = (inverted[1] & 0x80) != 0
        msg_len = inverted[1] & 0x7F  # Clear the ACK_REQUIRED bit

        if msg_len != len(data):
            return None  # The length field disagrees with the message length

        from_node_type = enum_or_int(NodeType, inverted[2] >> 4 & 0xF)
        to_node_type = enum_or_int(NodeType, inverted[2] & 0xF)

        from_addr = SomfyAddress.parse_bytes(inverted[3:6])
        to_addr = SomfyAddress.parse_bytes(inverted[6:9])

        payload = inverted[9:]
        parsed_payload = attempt_to_parse_payload(msg_id, payload)

        return SomfyMessage(msgid=msg_id,
                            from_node_type=from_node_type, from_addr=from_addr,
                            to_node_type=to_node_type, to_addr=to_addr,
                            need_ack=needs_ack, payload=parsed_payload)
