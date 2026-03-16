"""Serial connection management for Marlin-based 3D printers.

Handles opening, closing, and reconnecting the serial port. Provides
async read/write using pyserial-asyncio.
"""

import asyncio
import logging
from typing import Optional

import serial
import serial.tools.list_ports
import serial_asyncio

logger = logging.getLogger(__name__)


class SerialConnection:
    """Manages the physical serial connection to the printer."""

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
    ):
        self.port = port
        self.baudrate = baudrate
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Open the serial connection. Returns True on success."""
        async with self._lock:
            if self._connected:
                return True
            try:
                logger.info("Connecting to %s at %d baud...", self.port, self.baudrate)
                self._reader, self._writer = await serial_asyncio.open_serial_connection(
                    url=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False,
                )
                self._connected = True
                logger.info("Serial connection established to %s", self.port)
                await self._wait_for_startup()
                return True

            except Exception as e:
                logger.error("Failed to connect to %s: %s", self.port, e)
                self._connected = False
                self._reader = None
                self._writer = None
                return False

    async def _wait_for_startup(self, timeout: float = 5.0) -> list[str]:
        """Wait for and capture Marlin's startup messages."""
        lines = []
        try:
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    line = await asyncio.wait_for(
                        self.read_line(), timeout=min(remaining, 1.0)
                    )
                    lines.append(line)
                    logger.debug("Startup: %s", line)
                    if line.strip() == "ok":
                        break
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            logger.warning("Error during startup wait: %s", e)
        return lines

    async def disconnect(self) -> None:
        """Close the serial connection."""
        async with self._lock:
            if self._writer:
                try:
                    self._writer.close()
                except Exception:
                    pass
            self._reader = None
            self._writer = None
            self._connected = False
            logger.info("Serial connection closed")

    async def send(self, command: str) -> None:
        """Send a line to the printer (adds newline)."""
        if not self._connected or not self._writer:
            raise ConnectionError("Not connected to printer")
        line = command.strip() + "\n"
        self._writer.write(line.encode("ascii", errors="replace"))
        await self._writer.drain()
        logger.debug("TX: %s", command.strip())

    async def read_line(self, timeout: float = 10.0) -> str:
        """Read one line from the printer. Raises TimeoutError if no data."""
        if not self._connected or not self._reader:
            raise ConnectionError("Not connected to printer")
        try:
            raw = await asyncio.wait_for(
                self._reader.readline(), timeout=timeout
            )
            line = raw.decode("ascii", errors="replace").strip()
            if line:
                logger.debug("RX: %s", line)
            return line
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error("Serial read error: %s", e)
            self._connected = False
            raise ConnectionError(f"Serial read failed: {e}")

    @staticmethod
    def list_ports() -> list[str]:
        """List available serial ports on the system."""
        ports = []
        for info in serial.tools.list_ports.comports():
            ports.append(info.device)
        return sorted(ports)
