###############################################################################################
# Typesafe wrappers for message payloads, based on the SDN Integration Guide
# (and a bit of reverse engineering).
###############################################################################################
from typing import Optional, List, override

from somfy.enumutils import enum_or_int, IntEnumWithStr
from somfy.messages import SomfyPayload, SomfyMessageId, SomfyAddress, register_message_payloads


class EmptyPayload(SomfyPayload):
    expected_lengths = [0]

    def __init__(self, *ignored, **ignored_kwargs):
        super().__init__([])


class GroupAddrPayload(SomfyPayload):
    expected_lengths = [4]

    def get_group_index(self):
        return self.content[0]

    def get_group_id(self):
        return self.content[1] << 16 + self.content[2] << 8 + self.content[3]

    @override
    def as_dict(self):
        return {"group_index": self.get_group_index(), "group_id": self.get_group_id()}

    @staticmethod
    def make(group_index: int, group_id: int) -> 'GroupAddrPayload':
        return GroupAddrPayload([group_index, group_id >> 16 & 0xFF, group_id >> 8 & 0xFF, group_id & 0xFF])


class GroupIndexPayload(SomfyPayload):
    expected_lengths = [1]

    def get_group_index(self):
        return self.content[0]

    @override
    def as_dict(self):
        return {"group_index": self.get_group_index()}

    @staticmethod
    def make(group_index: int) -> 'GroupIndexPayload':
        return GroupIndexPayload([group_index])


# Some message processing fault reasons
class SomfyNackReason(IntEnumWithStr):
    NACK_DATA_OUT_OF_RANGE = 0x01
    NACK_UNKNOWN_MESSAGE = 0x10
    NACK_MESSAGE_LENGTH_ERROR = 0x11
    NACK_BUSY = 0xFF
# Other NACK text codes that I gleaned from the Internet. Don't have numeric values yet.
#     NACK_ACK
#     NACK_RNG
#     NACK_BADMSG
#     NACK_MSGSIZE
#     NACK_BUSY
#     NACK_DATA_ERROR
#     NACK_NODE_IS_LOCKED
#     NACK_WRONG_POSITION
#     NACK_END_LIMITS_NOT_SET
#     NACK_IP_NOT_SET
#     NACK_CURRENT_POSITION_OUT_OF_RANGE
#     NACK_FEATURE_NOT_SUPPORTED
#     NACK_IN_MOTION
#     NACK_IN_SECURITY
#     NACK_LAST_IP_REACHED
#     NACK_THRESHOLD_REACHED
#     NACK_LOW_PRIORITY
#     NACK_WINK_IN_PROGRESS
    NACK_IN_SECURITY = 0x27  # Thermal protection, obstacle detection, etc.
    NACK_LAST_IP_REACHED = 0x28


class NackPayload(SomfyPayload):
    expected_lengths = [1]

    def get_nack_code(self) -> SomfyNackReason | int:
        return enum_or_int(SomfyNackReason, self.content[0])

    @override
    def as_dict(self):
        return {"nack_code": self.get_nack_code()}

    @staticmethod
    def make(nack_code: SomfyNackReason | int) -> 'NackPayload':
        return NackPayload([int(nack_code)])


class NodeAppVersionPayload(SomfyPayload):
    expected_lengths = [6]

    @staticmethod
    def make(version: List[int]) -> 'NodeAppVersionPayload':
        return NodeAppVersionPayload(version)


class NodeLabelPayload(SomfyPayload):
    expected_lengths = [16]

    def get_label(self):
        return bytes(self.content).decode('utf-8').strip()

    @override
    def as_dict(self):
        return {"label": self.get_label()}

    @staticmethod
    def make(label: str) -> 'NodeLabelPayload':
        label_bytes = label.encode('utf-8')
        if len(label_bytes) > 16:
            raise ValueError("Label too long")
        return NodeLabelPayload([b for b in label_bytes])


class SomfyUIFunction(IntEnumWithStr):
    ENABLE = 0x0
    DISABLE = 0x1


class SomfyUIIndex(IntEnumWithStr):
    ALL_CONTROLS = 0x0
    DCT_INPUT = 0x1
    LOCAL_STIMULI = 0x2
    LOCAL_RADIO = 0x03
    TOUCH_MOTION = 0x04
    LEDS = 0x05


class SetLocalUIPayload(SomfyPayload):
    expected_lengths = [3]

    def get_function(self) -> SomfyUIFunction | int:
        return enum_or_int(SomfyUIFunction, self.content[0])

    def get_ui_index(self) -> SomfyUIIndex | int:
        return enum_or_int(SomfyUIIndex, self.content[1])

    def get_priority(self) -> int:
        return self.content[2]

    @override
    def as_dict(self):
        return {"function": self.get_function(), "ui_index": self.get_ui_index(), "priority": self.get_priority()}

    @staticmethod
    def make(func: SomfyUIFunction | int, ui_index: SomfyUIIndex | int, priority: int) -> 'SetLocalUIPayload':
        return SetLocalUIPayload([func, ui_index, priority])


class GetLocalUIPayload(SomfyPayload):
    expected_lengths = [1]

    def get_ui_index(self) -> SomfyUIIndex | int:
        return enum_or_int(SomfyUIIndex, self.content[0])

    @override
    def as_dict(self):
        return {"ui_index": self.get_ui_index()}

    @staticmethod
    def make(ui_index: SomfyUIIndex | int) -> 'GetLocalUIPayload':
        return GetLocalUIPayload([ui_index])


class PostLocalUIPayload(SomfyPayload):
    expected_lengths = [5]

    def get_function(self) -> SomfyUIFunction | int:
        return enum_or_int(SomfyUIFunction, self.content[0])

    def get_source_addr(self) -> SomfyAddress:
        return SomfyAddress.parse_bytes(self.content[1:4])

    def get_priority(self) -> int:
        return self.content[4]

    @override
    def as_dict(self):
        return {"function": self.get_function(),
                "source_addr": self.get_source_addr(), "priority": self.get_priority()}

    @staticmethod
    def make(func: SomfyUIFunction | int, source_address: SomfyAddress, priority: int) -> 'PostLocalUIPayload':
        return PostLocalUIPayload([func] + source_address.serialize() + [priority])


class SomfyMotorIPFunction(IntEnumWithStr):
    DELETE = 0x0
    SET_IP_AT_CURRENT = 0x01
    SET_IP_AT_SPECIFIED_PERCENT = 0x03  # Tilt value is ignored
    DIVIDE_INTO_EQUAL_RANGES = 0x04  # Position specifies the count of ranges, IP index and Tilt value are ignored
    SET_AT_CURRENT_POSITION_AND_ANGLE = 0x05  # Position and tilt value are ignored
    SET_AT_SPECIFIED_POSITION_AND_ANGLE_IN_PERCENTS = 0x0A
    SET_AT_SPECIFIED_POSITION_AND_ANGLE_IN_DEGREES = 0x0B


class SetMotorIPPayload(SomfyPayload):
    expected_lengths = [4, 6]

    IP_POSITION_UNDEFINED = 0xFFFF

    def get_function(self) -> SomfyMotorIPFunction | int:
        return enum_or_int(SomfyMotorIPFunction, self.content[0])

    def get_ip_index(self) -> int:
        return self.content[1]

    def get_position(self) -> int:
        return self.content[3] << 8 | self.content[2]

    def get_angle(self) -> Optional[int]:
        if len(self.content) != 6:
            return None
        return self.content[5] << 8 | self.content[4]

    @override
    def as_dict(self):
        return {"function": self.get_function(), "ip_index": self.get_ip_index(), "position": self.get_position(),
                "angle": self.get_angle()}

    @staticmethod
    def make(func: SomfyMotorIPFunction | int, ip_index: int, position: int,
             angle: Optional[int]) -> 'SetMotorIPPayload':
        angle_list = [angle >> 8 & 0xFF, angle & 0xFF] if angle else []
        return SetMotorIPPayload([func, ip_index, position >> 8 & 0xFF, position & 0xFF] + angle_list)


class GetMotorIPPayload(SomfyPayload):
    expected_lengths = [1]

    def get_ip_index(self):
        return self.content[0]

    @override
    def as_dict(self):
        return {"ip_index": self.get_ip_index()}

    @staticmethod
    def make(ip_index: int) -> 'GetMotorIPPayload':
        return GetMotorIPPayload([ip_index])


class PostMotorIPPayload(SomfyPayload):
    expected_lengths = [4, 9]

    UNSET_POSITION = 0xFF
    UNSET_ANGLE = 0x8000

    def get_ip_index(self) -> int:
        return self.content[0]

    def get_position(self) -> int:
        return self.content[2]

    def get_angle(self) -> Optional[int]:
        if len(self.content) != 9:
            return None
        angle = self.content[8] << 8 | self.content[7]
        return angle

    @override
    def as_dict(self):
        return {"ip_index": self.get_ip_index(), "position": self.get_position(), "angle": self.get_angle()}

    @staticmethod
    def make(ip_index: int, position: int, angle: Optional[int]) -> 'PostMotorIPPayload':
        angle_list = [0, 0, 0, angle & 0xFF, angle >> 8 & 0xFF] if angle else []
        return PostMotorIPPayload([ip_index, 0, 0, position] + angle_list)


class MotorSpeedPayload(SomfyPayload):
    expected_lengths = [3]

    def get_up_speed_rpm(self) -> int:
        return self.content[0]

    def get_down_speed_rpm(self) -> int:
        return self.content[1]

    def get_slow_speed_rpm(self) -> int:
        return self.content[2]

    @override
    def as_dict(self):
        return {"up_speed_rpm": self.get_up_speed_rpm(), "down_speed_rpm": self.get_down_speed_rpm(),
                "slow_speed_rpm": self.get_slow_speed_rpm()}

    @staticmethod
    def make(up_speed_rpm: int, down_speed_rpm: int, slow_speed_rpm: int) -> 'MotorSpeedPayload':
        return MotorSpeedPayload([up_speed_rpm, down_speed_rpm, slow_speed_rpm])


class LockNetworkFunction(IntEnumWithStr):
    UNLOCK = 0x00
    LOCK = 0x01
    PRESERVE_LOCK_ON_POWER_CYCLE = 0x03  # Priority is ignored
    UNPRESERVE_LOCK_ON_POWER_CYCLE = 0x04  # Priority is ignored


class SetNetworkLockPayload(SomfyPayload):
    expected_lengths = [2]

    def get_function(self) -> LockNetworkFunction | int:
        return enum_or_int(LockNetworkFunction, self.content[0])

    def get_priority(self) -> int:
        return self.content[1]

    @override
    def as_dict(self):
        return {"function": self.get_function(), "priority": self.get_priority()}

    @staticmethod
    def make(func: LockNetworkFunction | int, priority: int) -> 'SetNetworkLockPayload':
        return SetNetworkLockPayload([func, priority])


class PostNetworkLockPayload(SomfyPayload):
    expected_lengths = [6]

    def is_locked(self) -> bool:
        return self.content[0] != 0

    def get_lock_holder(self) -> SomfyAddress:
        return SomfyAddress.parse_bytes(self.content[1:4])

    def get_priority(self) -> int:
        return self.content[4]

    def is_persistent_across_power_cycle(self) -> bool:
        return self.content[5] != 0

    @override
    def as_dict(self):
        return {"is_locked": self.is_locked(), "lock_holder": self.get_lock_holder(), "priority": self.get_priority(),
                "is_persistent_across_power_cycle": self.is_persistent_across_power_cycle()}

    @staticmethod
    def make(locked: bool, lock_holder: SomfyAddress, priority: int,
             persistent_across_power_cycle: bool) -> 'PostNetworkLockPayload':
        return PostNetworkLockPayload([int(locked), lock_holder.serialize(), priority,
                                       int(persistent_across_power_cycle)])


class CtrlMoveToFunction(IntEnumWithStr):
    DOWN_LIMIT = 0x00  # Position and angle are ignored
    UP_LIMIT = 0x01  # Position and angle are ignored
    IP = 0x02  # Position contains the Intermediate Position index
    POSITION_PERCENT = 0x04  # Tilt is ignored
    POSITION_PERCENT_ANGLE_PERCENT = 0x0C
    POSITION_PERCENT_ANGLE_DEGREES = 0x0D
    CURRENT_POSITION_ANGLE_PERCENT = 0x0F  # Position is ignored
    CURRENT_POSITION_ANGLE_DEGREES = 0x10  # Position is ignored


class CtrlMoveToPayload(SomfyPayload):
    expected_lengths = [4, 6]

    def get_function(self) -> CtrlMoveToFunction | int:
        return enum_or_int(CtrlMoveToFunction, self.content[0])

    def get_position(self) -> int:
        return self.content[2] << 8 | self.content[1]

    def get_angle(self) -> Optional[int]:
        if len(self.content) != 6:
            return None
        return self.content[5] << 8 | self.content[4]

    @override
    def as_dict(self):
        return {"function": self.get_function(), "position": self.get_position(), "angle": self.get_angle()}

    @staticmethod
    def make(func: CtrlMoveToFunction | int, position: int, angle: Optional[int] = None) -> 'CtrlMoveToPayload':
        angle_list = [angle & 0xFF, angle >> 8 & 0xFF] if angle else []
        return CtrlMoveToPayload([func, position & 0xFF, position >> 8 & 0xFF, 0] + angle_list)


class CtrlStopPayload(SomfyPayload):
    expected_lengths = [1]

    def get_reserved(self) -> int:
        return self.content[0]

    @override
    def as_dict(self):
        return {"reserved": self.get_reserved()}

    @staticmethod
    def make(reserved: int = 0) -> 'CtrlStopPayload':
        return CtrlStopPayload([reserved])


class PostMotorPositionPayload(SomfyPayload):
    expected_lengths = [5, 11]

    IP_UNDEFINED = 0xFF

    def get_position_pulses(self) -> int:
        return self.content[1] << 8 | self.content[0]

    def get_position_percent(self) -> int:
        return self.content[2]

    def get_tilt_percent(self) -> int:
        return self.content[3]

    def get_ip(self) -> Optional[int]:
        ip = self.content[4]
        if ip == self.IP_UNDEFINED:
            return None
        return ip

    def get_tilt_degrees(self) -> Optional[int]:
        if len(self.content) != 11:
            return None
        return self.content[8] << 8 | self.content[7]

    @override
    def as_dict(self):
        return {"position_pulses": self.get_position_pulses(), "position_percent": self.get_position_percent(),
                "tilt_percent": self.get_tilt_percent(), "ip": self.get_ip(), "tilt_degrees": self.get_tilt_degrees()}

    @staticmethod
    def make(position_pulses: int, position_percent: int, tilt_percent: int,
             ip: int, tilt_degrees: Optional[int]) -> 'PostMotorPositionPayload':
        angle_list = [0, 0, tilt_degrees & 0xFF, tilt_degrees >> 8 & 0xFF, 0, 0] if tilt_degrees else []
        return PostMotorPositionPayload(
            [position_pulses & 0xFF, position_pulses >> 8 & 0xFF, position_percent, tilt_percent, ip] + angle_list)


class MotorStatus(IntEnumWithStr):
    STOPPED = 0x00
    RUNNING = 0x01
    BLOCKED = 0x02  # Blocked from movement by an obstacle or thermal protection
    LOCKED = 0x03  # Locked by another device


class MotorDirection(IntEnumWithStr):
    DOWN = 0x00
    UP = 0x01
    UNKNOWN = 0xFF


class MotorCommandSource(IntEnumWithStr):
    INTERNAL = 0x00  # Limit/IP/Position reached, Over-current, obstacle detection, thermal protection, ...
    NETWORK_MESSAGE = 0x01  # Any message received from the SDN bus
    LOCAL_UI = 0x02  # DCT, Local stimulus, local wireless


class MotorStatusCause(IntEnumWithStr):
    TARGET_REACHED = 0x00  # Successful completion of a command
    EXPLICIT_COMMAND = 0x01  # Network or Local UI command
    WINK = 0x02
    OBSTACLE_DETECTION = 0x20
    OVERCURRENT_PROTECTION = 0x21
    THERMAL_PROTECTION = 0x22
    RUNTIME_EXCEEDED = 0x30  # Continuous runtime exceeded limit
    TIMEOUT_EXCEEDED = 0x32  # When using CTRL_MOVE and more than 2min. elapsed
    POWER_CYCLE = 0xFF  # No command after startup


class PostMotorStatusPayload(SomfyPayload):
    expected_lengths = [4]

    def get_status(self) -> MotorStatus | int:
        return enum_or_int(MotorStatus, self.content[0])

    def get_direction(self) -> MotorDirection | int:
        return enum_or_int(MotorDirection, self.content[1])

    def get_command_source(self) -> MotorCommandSource | int:
        return enum_or_int(MotorCommandSource, self.content[2])

    def get_status_cause(self) -> MotorStatusCause | int:
        return enum_or_int(MotorStatusCause, self.content[3])

    @override
    def as_dict(self):
        return {"status": self.get_status(), "direction": self.get_direction(),
                "command_source": self.get_command_source(), "status_cause": self.get_status_cause()}

    @staticmethod
    def make(status: MotorStatus | int, direction: MotorDirection | int, source: MotorCommandSource | int,
             cause: MotorStatusCause | int) -> 'PostMotorStatusPayload':
        return PostMotorStatusPayload([status, direction, source, cause])


#############################################################################################
# Reverse-engineered payloads
#############################################################################################

class SomfyDirection(IntEnumWithStr):
    DOWN = 0x00
    UP = 0x01


class CtrlMoveForcedPayload(SomfyPayload):
    expected_lengths = [3]

    def get_direction(self) -> SomfyDirection | int:
        return enum_or_int(SomfyDirection, self.content[0])

    # The movement duration in the units of 10ms
    def get_tens_of_ms(self) -> int:
        return self.content[2] << 8 | self.content[1]

    def as_dict(self):
        return {"direction": self.get_direction(), "tens_of_ms": self.get_tens_of_ms()}

    @staticmethod
    def make(direction: SomfyDirection, tens_of_ms: int) -> 'CtrlMoveForcedPayload':
        return CtrlMoveForcedPayload([direction, tens_of_ms & 0xFF, tens_of_ms >> 8 & 0xFF])


class RelativeMoveFunction(IntEnumWithStr):
    MOVE_NEXT_IP_DOWN = 0x00
    MOVE_NEXT_IP_UP = 0x01
    MOVE_NUM_PULSES_DOWN = 0x02
    MOVE_NUM_PULSES_UP = 0x03
    MOVE_TENS_OF_MS_DOWN = 0x04
    MOVE_TENS_OF_MS_UP = 0x05


class CtrlMoveRelativePayload(SomfyPayload):
    expected_lengths = [4]

    def get_function(self) -> RelativeMoveFunction | int:
        return enum_or_int(RelativeMoveFunction, self.content[0])

    def get_parameter(self) -> int:
        return self.content[2] >> 8 | self.content[1]

    def as_dict(self):
        return {"function": self.get_function(), "parameter": self.get_parameter()}

    @staticmethod
    def make(func: RelativeMoveFunction | int, parameter: int) -> 'CtrlMoveRelativePayload':
        return CtrlMoveRelativePayload([func, parameter & 0xFF, parameter >> 8 & 0xFF, 0])


class SetLimitsFunction(IntEnumWithStr):
    SET_AT_CURRENT = 0x01
    SET_AT_PULSE_COUNT = 0x02  # At the specified pulse count
    ADJUST_BY_TENS_OF_MS = 0x04  # Adjust up or down by N*10 milliseconds
    ADJUST_BY_PULSE_COUNT = 0x05  # Adjust up or down by N pulses


class SetMotorLimitsPayload(SomfyPayload):
    expected_lengths = [4]

    def get_function(self) -> SetLimitsFunction | int:
        return enum_or_int(SetLimitsFunction, self.content[0])

    def get_direction(self) -> SomfyDirection | int:
        return enum_or_int(SomfyDirection, self.content[1])

    def get_parameter(self) -> int:
        return self.content[3] << 8 | self.content[2]

    @override
    def as_dict(self):
        return {"function": self.get_function(), "direction": self.get_direction(), "parameter": self.get_parameter()}

    @staticmethod
    def make(func: SetLimitsFunction, direction: SomfyDirection, param: int) -> 'SetMotorLimitsPayload':
        return SetMotorLimitsPayload([func, direction, param & 0xFF, param >> 8 & 0xFF])


class PostMotorLimitsPayload(SomfyPayload):
    expected_lengths = [4]

    def get_reserved(self) -> int:
        return self.content[1] << 8 | self.content[0] & 0xFF

    def get_limit(self) -> int:
        return self.content[3] << 8 | self.content[2] & 0xFF

    @override
    def as_dict(self):
        return {"reserved": self.get_reserved(), "limit": self.get_limit()}

    @staticmethod
    def make(limit: int) -> 'PostMotorLimitsPayload':
        return PostMotorLimitsPayload([0, 0, limit & 0xFF, limit >> 8 & 0xFF])


class MotorRotationDirection(IntEnumWithStr):
    STANDARD = 0x00
    REVERSED = 0x01


class MotorRotationDirectionPayload(SomfyPayload):
    expected_lengths = [1]

    def get_direction(self) -> MotorRotationDirection | int:
        return enum_or_int(MotorRotationDirection, self.content[0])

    def as_dict(self):
        return {"direction": self.get_direction()}

    @staticmethod
    def make(direction: MotorRotationDirection | int) -> 'MotorRotationDirectionPayload':
        return MotorRotationDirectionPayload([direction])


def register_documented_payloads():
    dp = dict[int, type]({
        SomfyMessageId.GET_NODE_ADDR: EmptyPayload,
        SomfyMessageId.POST_NODE_ADDR: EmptyPayload,
        SomfyMessageId.SET_GROUP_ADDR: GroupAddrPayload,
        SomfyMessageId.GET_GROUP_ADDR: GroupIndexPayload,
        SomfyMessageId.POST_GROUP_ADDR: GroupAddrPayload,
        SomfyMessageId.ACK: EmptyPayload,
        SomfyMessageId.NACK: NackPayload,
        SomfyMessageId.GET_NODE_APP_VERSION: EmptyPayload,
        SomfyMessageId.POST_NODE_APP_VERSION: NodeAppVersionPayload,
        SomfyMessageId.SET_NODE_LABEL: NodeLabelPayload,
        SomfyMessageId.GET_NODE_LABEL: EmptyPayload,
        SomfyMessageId.POST_NODE_LABEL: NodeLabelPayload,
        SomfyMessageId.SET_LOCAL_UI: SetLocalUIPayload,
        SomfyMessageId.GET_LOCAL_UI: GetLocalUIPayload,
        SomfyMessageId.POST_LOCAL_UI: PostLocalUIPayload,
        SomfyMessageId.SET_MOTOR_IP: SetMotorIPPayload,
        SomfyMessageId.GET_MOTOR_IP: GetMotorIPPayload,
        SomfyMessageId.POST_MOTOR_IP: PostMotorIPPayload,
        SomfyMessageId.SET_MOTOR_ROLLING_SPEED: MotorSpeedPayload,
        SomfyMessageId.GET_MOTOR_ROLLING_SPEED: EmptyPayload,
        SomfyMessageId.POST_MOTOR_ROLLING_SPEED: MotorSpeedPayload,
        SomfyMessageId.SET_NETWORK_LOCK: SetNetworkLockPayload,
        SomfyMessageId.GET_NETWORK_LOCK: EmptyPayload,
        SomfyMessageId.POST_NETWORK_LOCK: PostNetworkLockPayload,
        SomfyMessageId.CTRL_MOVETO: CtrlMoveToPayload,
        SomfyMessageId.CTRL_STOP: CtrlStopPayload,
        SomfyMessageId.GET_MOTOR_POSITION: EmptyPayload,
        SomfyMessageId.POST_MOTOR_POSITION: PostMotorPositionPayload,
        SomfyMessageId.GET_MOTOR_STATUS: EmptyPayload,
        SomfyMessageId.POST_MOTOR_STATUS: PostMotorStatusPayload,
        # Reversed payloads:
        SomfyMessageId.CTRL_MOVE_FORCED: CtrlMoveForcedPayload,
        SomfyMessageId.CTRL_MOVE_RELATIVE: CtrlMoveRelativePayload,
        SomfyMessageId.SET_MOTOR_LIMITS: SetMotorLimitsPayload,
        SomfyMessageId.GET_MOTOR_LIMITS: EmptyPayload,
        SomfyMessageId.POST_MOTOR_LIMITS: PostMotorLimitsPayload,
        SomfyMessageId.SET_MOTOR_ROTATION_DIRECTION: MotorRotationDirectionPayload,
        SomfyMessageId.GET_MOTOR_ROTATION_DIRECTION: EmptyPayload,
        SomfyMessageId.POST_MOTOR_ROTATION_DIRECTION: MotorRotationDirectionPayload,
    })

    register_message_payloads(dp)
