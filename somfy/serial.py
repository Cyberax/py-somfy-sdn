from asyncio import StreamReader, StreamWriter
from typing import override

import serial
import serial_asyncio

from somfy.connector import ConnectionFactory


class SerialConnectionFactory(ConnectionFactory):
    def __init__(self, device: str):
        self.device = device

    @override
    async def connect(self) -> (StreamReader, StreamWriter):
        reader, writer = await serial_asyncio.open_serial_connection(
            url=self.device, baudrate=4800, parity=serial.PARITY_ODD)
        return reader, writer
