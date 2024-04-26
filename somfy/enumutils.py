from enum import IntEnum
from typing import Type


class IntEnumWithStr(IntEnum):
    def __str__(self):
        return self.name


def enum_or_int[T](enum_type: Type[T], val: int) -> T | int:
    try:
        return enum_type(val)
    except ValueError:
        return val


def hex_enum(val: IntEnum | int) -> str:
    if isinstance(val, IntEnum):
        return "%02X(%s)" % (int(val), str(val))
    return "%02X" % val
