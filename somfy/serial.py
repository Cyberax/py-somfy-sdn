import asyncio
from asyncio import StreamReader, StreamWriter
from typing import List, Optional

import serial
import serial_asyncio

from somfy.connector import Channel


class SerialChannel(Channel):
    def __init__(self, port: str):
        self.port = port
        self.last_activity = 0
        self.reader: Optional[StreamReader] = None
        self.writer: Optional[StreamWriter] = None

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.writer is not None:
            self.writer.close()
            self.writer = None
            self.reader = None
        return

    async def open(self):
        self.reader, self.writer = await serial_asyncio.open_serial_connection(
            url=self.port, baudrate=4800, parity=serial.PARITY_ODD)

    async def close(self):
        self.writer.close()

    async def read_byte(self) -> int:
        chunk = await self.reader.readexactly(1)
        loop = asyncio.get_running_loop()
        self.last_activity = loop.time()
        return chunk[0]

    async def write_bytes(self, data: List[int]):
        loop = asyncio.get_running_loop()
        self.writer.write(bytes(data))
        await self.writer.drain()
        self.last_activity = loop.time()

    def get_last_activity(self):
        return self.last_activity
