"""Tests for the shared command guards (during-print allowlist + temp ceiling).

These guards are the fix for the review's C1 (OctoPrint-compat shim allowed
G28/M84 mid-print) and H1 (no ceiling on temperature targets), so the endpoint
tests here are regression tests against reintroducing those bypasses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.printer.command_guard import (
    ALLOWED_DURING_PRINT,
    command_base,
    is_allowed_during_print,
    temperature_command_error,
    temperature_value_error,
)


class TestCommandBase:
    def test_simple(self):
        assert command_base("M104 S200") == "M104"

    def test_lowercase(self):
        assert command_base("g28 x y") == "G28"

    def test_leading_whitespace(self):
        assert command_base("   G29") == "G29"

    def test_empty(self):
        assert command_base("") == ""
        assert command_base("   ") == ""


class TestAllowedDuringPrint:
    @pytest.mark.parametrize("cmd", sorted(ALLOWED_DURING_PRINT))
    def test_allowed_bases(self, cmd):
        assert is_allowed_during_print(cmd) is True
        assert is_allowed_during_print(f"{cmd.lower()} S1") is True

    @pytest.mark.parametrize(
        "cmd",
        [
            "G0 X0 Y0 F6000",       # linear travel
            "G1 X10",               # linear print move
            "G1 E5 F300",           # extrusion-only move
            "G2 X10 Y10 I5 J0",     # clockwise arc
            "G3 X0 Y0 I-5 J0",      # counter-clockwise arc
            "G5 X10 Y10 I2 J2",     # Bezier move
            "G10",                  # firmware retract
            "G11",                  # firmware unretract
            "T0",                   # tool change
            "T1",                   # tool change
            "M600",                 # filament-change movement sequence
            "M701",                 # load filament
            "M702",                 # unload filament
            "M810",                 # stored G-code macro
            "M819",                 # stored G-code macro
            "M98 P\"macro.g\"",    # subprogram/macro call
            "G28",                  # home
            "G90",                  # positioning mode
            "G91",                  # positioning mode
            "G92 E0",               # rewrite coordinate origin
            "M18",                  # disable steppers
            "M84",                  # disable steppers
        ],
    )
    def test_motion_extrusion_tool_and_macro_commands_are_blocked(self, cmd):
        assert is_allowed_during_print(cmd) is False

    @pytest.mark.parametrize(
        "cmd", ["M105", "M104 S200", "M106 S128", "M220 S50", "M117 hi"]
    )
    def test_benign_commands_pass(self, cmd):
        assert is_allowed_during_print(cmd) is True

    def test_unknown_commands_fail_closed(self):
        assert is_allowed_during_print("G280") is False
        assert is_allowed_during_print("M840") is False

    def test_embedded_newline_cannot_smuggle_a_move(self):
        assert is_allowed_during_print("M105\nG1 X0 Y0") is False


class TestTemperatureCommandError:
    def test_hotend_over_limit(self):
        err = temperature_command_error("M104 S500", 290.0, 110.0)
        assert err is not None and "500" in err and "290" in err

    def test_hotend_wait_form(self):
        assert temperature_command_error("M109 S400", 290.0, 110.0) is not None

    def test_r_parameter_checked(self):
        # M109/M190 accept R (wait even while cooling) — same target semantics
        assert temperature_command_error("M109 R400", 290.0, 110.0) is not None

    def test_bed_over_limit(self):
        err = temperature_command_error("M140 S150", 290.0, 110.0)
        assert err is not None and "150" in err and "110" in err

    def test_bed_wait_form(self):
        assert temperature_command_error("M190 S150", 290.0, 110.0) is not None

    def test_within_limits_ok(self):
        assert temperature_command_error("M104 S215", 290.0, 110.0) is None
        assert temperature_command_error("M140 S60", 290.0, 110.0) is None

    def test_heater_off_ok(self):
        assert temperature_command_error("M104 S0", 290.0, 110.0) is None

    def test_lowercase_command(self):
        assert temperature_command_error("m104 s500", 290.0, 110.0) is not None

    def test_non_temp_command_ignored(self):
        assert temperature_command_error("G1 X10 S500", 290.0, 110.0) is None

    def test_bed_limit_not_applied_to_hotend(self):
        # 200C is fine for a hotend even though it's over the bed cap
        assert temperature_command_error("M104 S200", 290.0, 110.0) is None


class TestTemperatureValueError:
    def test_hotend_over(self):
        assert temperature_value_error(500.0, None, 290.0, 110.0) is not None

    def test_bed_over(self):
        assert temperature_value_error(None, 150.0, 290.0, 110.0) is not None

    def test_both_none_ok(self):
        assert temperature_value_error(None, None, 290.0, 110.0) is None

    def test_at_limit_ok(self):
        assert temperature_value_error(290.0, 110.0, 290.0, 110.0) is None


def _make_ctrl(status_value: str) -> MagicMock:
    """Build a minimal fake controller for endpoint-level guard tests."""
    ctrl = MagicMock()
    ctrl.state.status.value = status_value
    ctrl.safety_monitor.max_hotend_temp = 290.0
    ctrl.safety_monitor.max_bed_temp = 110.0
    result = MagicMock(ok=True, command="X", response_lines=[], error=None)
    ctrl.send_command = AsyncMock(return_value=result)
    return ctrl


class TestNativeCommandEndpointGuards:
    """POST /api/printer/command uses the shared guards."""

    async def test_g1_move_blocked_while_printing(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("printing")
        printer_api.set_controller(ctrl)
        with pytest.raises(HTTPException) as exc:
            await printer_api.send_command(
                printer_api.CommandRequest(command="G1 X0 Y0 F6000")
            )
        assert exc.value.status_code == 409
        ctrl.send_command.assert_not_awaited()

    async def test_g28_blocked_while_printing(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("printing")
        printer_api.set_controller(ctrl)
        with pytest.raises(HTTPException) as exc:
            await printer_api.send_command(printer_api.CommandRequest(command="G28"))
        assert exc.value.status_code == 409
        ctrl.send_command.assert_not_awaited()

    async def test_overtemp_rejected_even_when_idle(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("idle")
        printer_api.set_controller(ctrl)
        with pytest.raises(HTTPException) as exc:
            await printer_api.send_command(
                printer_api.CommandRequest(command="M104 S500")
            )
        assert exc.value.status_code == 400
        ctrl.send_command.assert_not_awaited()

    async def test_safe_command_passes_while_printing(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("printing")
        printer_api.set_controller(ctrl)
        resp = await printer_api.send_command(
            printer_api.CommandRequest(command="M220 S95")
        )
        assert resp["ok"] is True
        ctrl.send_command.assert_awaited_once()


class TestListFormCommandGuards:
    """OctoPrint clients POST {"commands": [...]} to /api/printer/command.

    The compat router's identical route was shadowed (dead) by the native one,
    so the native endpoint now owns BOTH shapes — these are the C1 regression
    tests for the slicer-facing list form.
    """

    async def test_dangerous_command_in_list_blocks_whole_batch(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("paused")
        printer_api.set_controller(ctrl)
        with pytest.raises(HTTPException) as exc:
            await printer_api.send_command(
                printer_api.CommandRequest(commands=["M105", "M84"])
            )
        assert exc.value.status_code == 409
        # Guard runs over the whole batch BEFORE anything is sent
        ctrl.send_command.assert_not_awaited()

    async def test_overtemp_in_list_rejected(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("idle")
        printer_api.set_controller(ctrl)
        with pytest.raises(HTTPException) as exc:
            await printer_api.send_command(
                printer_api.CommandRequest(commands=["M190 S150"])
            )
        assert exc.value.status_code == 400
        ctrl.send_command.assert_not_awaited()

    async def test_list_form_returns_204(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("idle")
        printer_api.set_controller(ctrl)
        resp = await printer_api.send_command(
            printer_api.CommandRequest(commands=["G91", "G1 X10", "G90"])
        )
        assert resp.status_code == 204
        assert ctrl.send_command.await_count == 3

    async def test_empty_request_is_400(self):
        from app.api import printer as printer_api

        ctrl = _make_ctrl("idle")
        printer_api.set_controller(ctrl)
        with pytest.raises(HTTPException) as exc:
            await printer_api.send_command(printer_api.CommandRequest())
        assert exc.value.status_code == 400
