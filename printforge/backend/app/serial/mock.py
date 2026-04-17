"""Mock serial device that simulates Marlin firmware responses.

Used for development and testing without a physical printer connected.
Simulates: startup messages, ok responses, temperature auto-reports,
position queries, and basic G-code handling.
"""

import asyncio
import random
import time


class MockMarlinPrinter:
    """Simulates a Marlin firmware printer for testing."""

    def __init__(self):
        self.hotend_actual = 22.0
        self.hotend_target = 0.0
        self.bed_actual = 21.0
        self.bed_target = 0.0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.e = 0.0
        self.fan_speed = 0
        self.homed = False
        self.relative_mode = False
        self._auto_report_interval = 0
        self._response_queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = True
        self._report_task = None

    async def start(self) -> None:
        """Send startup messages like real Marlin."""
        startup_messages = [
            "start",
            "echo: Marlin 2.1.2.1",
            "echo: Last Updated: 2023-06-01",
            "echo:Compiled: Jun  1 2023",
            "echo: Free Memory: 3391  PlannerBufferBytes: 1232",
            'echo:Hardcoded Default Settings Loaded',
            "ok",
        ]
        for msg in startup_messages:
            await self._response_queue.put(msg)

    async def process_command(self, command: str) -> None:
        """Process a G-code command and queue responses."""
        # Strip line numbers and checksums
        cmd = command.strip()
        if cmd.startswith("N"):
            # Remove N123 prefix and *checksum suffix
            parts = cmd.split("*")[0].split(" ", 1)
            cmd = parts[1] if len(parts) > 1 else ""

        cmd_upper = cmd.upper().strip()
        cmd_base = cmd_upper.split()[0] if cmd_upper else ""

        if cmd_base == "G28":
            # Home
            await asyncio.sleep(0.5)  # Simulate homing time
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self.homed = True
            await self._response_queue.put("ok")

        elif cmd_base == "G0" or cmd_base == "G1":
            # Move
            self._parse_move(cmd_upper)
            await self._response_queue.put("ok")

        elif cmd_base == "G90":
            self.relative_mode = False
            await self._response_queue.put("ok")

        elif cmd_base == "G91":
            self.relative_mode = True
            await self._response_queue.put("ok")

        elif cmd_base == "M104":
            # Set hotend temp (non-blocking)
            self._parse_temp(cmd_upper, "hotend")
            await self._response_queue.put("ok")

        elif cmd_base == "M109":
            # Set hotend temp and wait
            self._parse_temp(cmd_upper, "hotend")
            # Simulate heating
            while abs(self.hotend_actual - self.hotend_target) > 2:
                if self.hotend_actual < self.hotend_target:
                    self.hotend_actual = min(
                        self.hotend_target,
                        self.hotend_actual + random.uniform(2, 5),
                    )
                else:
                    self.hotend_actual = max(
                        self.hotend_target,
                        self.hotend_actual - random.uniform(2, 5),
                    )
                await self._response_queue.put(self._temp_report())
                await asyncio.sleep(0.5)
            await self._response_queue.put("ok")

        elif cmd_base == "M140":
            # Set bed temp (non-blocking)
            self._parse_temp(cmd_upper, "bed")
            await self._response_queue.put("ok")

        elif cmd_base == "M190":
            # Set bed temp and wait
            self._parse_temp(cmd_upper, "bed")
            while abs(self.bed_actual - self.bed_target) > 2:
                if self.bed_actual < self.bed_target:
                    self.bed_actual = min(
                        self.bed_target,
                        self.bed_actual + random.uniform(1, 3),
                    )
                else:
                    self.bed_actual = max(
                        self.bed_target,
                        self.bed_actual - random.uniform(1, 3),
                    )
                await self._response_queue.put(self._temp_report())
                await asyncio.sleep(0.5)
            await self._response_queue.put("ok")

        elif cmd_base == "M105":
            # Report temperatures
            await self._response_queue.put(self._temp_report())
            await self._response_queue.put("ok")

        elif cmd_base == "M114":
            # Report position
            await self._response_queue.put(
                f"X:{self.x:.2f} Y:{self.y:.2f} Z:{self.z:.2f} E:{self.e:.2f}"
            )
            await self._response_queue.put("ok")

        elif cmd_base == "M115":
            # Firmware info
            await self._response_queue.put(
                "FIRMWARE_NAME:Marlin 2.1.2.1 (MockPrinter) "
                "SOURCE_CODE_URL:https://github.com/MarlinFirmware/Marlin"
            )
            await self._response_queue.put(
                "Cap:AUTOREPORT_TEMP:1"
            )
            await self._response_queue.put("ok")

        elif cmd_base == "M155":
            # Auto-report temperature interval
            for part in cmd_upper.split():
                if part.startswith("S"):
                    self._auto_report_interval = int(part[1:])
            if self._auto_report_interval > 0:
                if self._report_task is None or self._report_task.done():
                    self._report_task = asyncio.create_task(
                        self._auto_report_loop()
                    )
            await self._response_queue.put("ok")

        elif cmd_base == "M106":
            # Fan speed
            for part in cmd_upper.split():
                if part.startswith("S"):
                    self.fan_speed = int(part[1:])
            await self._response_queue.put("ok")

        elif cmd_base == "M84":
            # Disable motors
            await self._response_queue.put("ok")

        elif cmd_base == "M112":
            # Emergency stop
            self.hotend_target = 0
            self.bed_target = 0
            self.fan_speed = 0
            await self._response_queue.put("ok")

        else:
            # Unknown command, just ack
            await self._response_queue.put("ok")

    def _parse_move(self, cmd: str) -> None:
        for part in cmd.split():
            if part.startswith("X"):
                val = float(part[1:])
                self.x = self.x + val if self.relative_mode else val
            elif part.startswith("Y"):
                val = float(part[1:])
                self.y = self.y + val if self.relative_mode else val
            elif part.startswith("Z"):
                val = float(part[1:])
                self.z = self.z + val if self.relative_mode else val
            elif part.startswith("E"):
                val = float(part[1:])
                self.e = self.e + val if self.relative_mode else val

    def _parse_temp(self, cmd: str, heater: str) -> None:
        for part in cmd.split():
            if part.startswith("S"):
                temp = float(part[1:])
                if heater == "hotend":
                    self.hotend_target = temp
                elif heater == "bed":
                    self.bed_target = temp

    def _temp_report(self) -> str:
        return (
            f" T:{self.hotend_actual:.1f} /{self.hotend_target:.1f}"
            f" B:{self.bed_actual:.1f} /{self.bed_target:.1f}"
            f" @:0 B@:0"
        )

    async def _auto_report_loop(self) -> None:
        """Periodically send temperature reports like M155 auto-report."""
        while self._running and self._auto_report_interval > 0:
            await asyncio.sleep(self._auto_report_interval)
            # Simulate temperature drift toward target
            self._simulate_heating()
            await self._response_queue.put(self._temp_report())

    def _simulate_heating(self) -> None:
        """Simulate gradual heating/cooling."""
        ambient = 22.0
        # Hotend
        if self.hotend_target > 0:
            diff = self.hotend_target - self.hotend_actual
            self.hotend_actual += diff * 0.1 + random.uniform(-0.3, 0.3)
        else:
            diff = ambient - self.hotend_actual
            self.hotend_actual += diff * 0.05

        # Bed
        if self.bed_target > 0:
            diff = self.bed_target - self.bed_actual
            self.bed_actual += diff * 0.08 + random.uniform(-0.2, 0.2)
        else:
            diff = ambient - self.bed_actual
            self.bed_actual += diff * 0.03

    async def read_response(self) -> str:
        """Get the next response line (blocks until available)."""
        return await self._response_queue.get()

    async def stop(self) -> None:
        self._running = False
        if self._report_task:
            self._report_task.cancel()
            try:
                await self._report_task
            except asyncio.CancelledError:
                pass
