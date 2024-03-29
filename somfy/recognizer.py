from typing import Optional

from somfy.messages import SomfyMessage, NodeType

# Message length limits (page 10)
MIN_MESSAGE_LENGTH = 11
MAX_MESSAGE_LEN = 32


# SDN runs over an RS-485 network, which is a noisy bus. We might periodically get random noise and/or third-party
# traffic. So we need to make sure we can recognize messages with some random padding before (and after) them.
# This class implements a simple ring buffer for the incoming data.
class MessageRecognizer(object):
    def __init__(self, node_type_filter: Optional[NodeType] = None):
        self.ring = list[int]([0] * MAX_MESSAGE_LEN)
        self.node_type_filter = node_type_filter
        self.pos = 0

    def ring_at(self, i) -> int:
        return self.ring[i % MAX_MESSAGE_LEN] & 0xFF

    # Add a byte to the buffer, and try to detect a message. Returns the detected message if successful.
    def add_data(self, cur_byte: int) -> Optional[SomfyMessage]:
        prev_byte = self.ring_at(self.pos - 1)
        self.ring[self.pos] = cur_byte
        possible_checksum = prev_byte * 256 + cur_byte
        self.pos = (self.pos + 1) % MAX_MESSAGE_LEN

        # There's no way the checksum can be that large (or small)
        if possible_checksum >= MAX_MESSAGE_LEN * 256 or possible_checksum == 0:
            return None

        # Try to see if the previous bytes in the ring form a valid message
        probable_message_start_pos = (self.pos - 3) % 32
        remaining_sum = possible_checksum
        count = 3
        # Walk backwards through the ring to try and find a position from which the bytes would sum up to yield
        # the supposed checksum.
        while probable_message_start_pos != self.pos:
            remaining_sum -= self.ring_at(probable_message_start_pos)
            if remaining_sum == 0:
                # 11 bytes is the smallest message:
                # [msg_id, len, direction] + [3 bytes from addr] + [3 bytes to addr] + [2 bytes checksum]
                if count < MIN_MESSAGE_LENGTH:
                    return None

                # We have a possible message starting at this position, create a buffer with it and
                # try parsing it
                buf = self.copy(probable_message_start_pos, count)
                msg = SomfyMessage.try_parse(buf)
                if msg is not None:
                    # We found a message! Blank out the buffer to avoid any false-message confusion
                    self.blank_out(probable_message_start_pos, count)
                    if self.node_type_filter is None or self.node_type_filter == msg.from_node_type:
                        return msg
                else:
                    # The further search is futile, return and wait for the next message
                    return None

            # Try to extend the probable message to the left
            probable_message_start_pos = (probable_message_start_pos - 1) % MAX_MESSAGE_LEN
            count += 1
        return None

    def copy(self, from_pos, count):
        res = []
        for i in range(from_pos, from_pos + count):
            res.append(self.ring_at(i))
        return res

    def blank_out(self, from_pos, count):
        for i in range(from_pos, from_pos + count):
            self.ring[i % MAX_MESSAGE_LEN] = 0xFF
