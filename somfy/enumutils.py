import enum
from enum import IntEnum
from typing import Any


class FlexibleEnumMeta(enum.EnumMeta):
    def __call__(cls, value: Any, *args, **kwargs):
        try:
            # attempt to get an enum member
            return super().__call__(value, *args, **kwargs)
        except ValueError:
            # no such member exists, but we don't care
            return value


class EnumWithMissing(IntEnum, metaclass=FlexibleEnumMeta):
    def __str__(self):
        return self.name


def hex_enum(val: IntEnum | int) -> str:
    if isinstance(val, IntEnum):
        return "%02X(%s)" % (int(val), str(val))
    return "%02X" % val
