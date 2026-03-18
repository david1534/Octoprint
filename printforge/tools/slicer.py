"""
CuraEngine subprocess wrapper.

Slices STL files to G-code using CuraEngine CLI with exported Cura profiles.

Usage:
    python slicer.py path/to/model.stl --profile functional
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


@dataclass
class SliceResult:
    success: bool
    output_path: Path | None
    duration_seconds: float
    stdout: str
    stderr: str
    error: str | None = None


def load_config() -> dict:
    """Load config.toml from the tools directory."""
    config_path = Path(__file__).parent / "config.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_profile_settings(profile_name: str) -> dict[str, str]:
    """Load a profile's settings from the exported JSON file."""
    profile_path = Path(__file__).parent / "profiles" / f"{profile_name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(
            f"Profile '{profile_name}' not found at {profile_path}. "
            f"Run 'python profile_loader.py' to export profiles first."
        )
    with open(profile_path) as f:
        return json.load(f)


def build_command(
    stl_path: Path,
    output_path: Path,
    profile_settings: dict[str, str],
    config: dict,
) -> list[str]:
    """Build the CuraEngine CLI command."""
    cura_engine = config["paths"]["cura_engine"]
    cura_resources = config["paths"]["cura_resources"]
    definitions_dir = Path(cura_resources) / "definitions"
    extruders_dir = Path(cura_resources) / "extruders"

    printer_def = definitions_dir / "creality_ender3s1pro.def.json"
    extruder_def = extruders_dir / "creality_base_extruder_0.def.json"

    cmd = [
        cura_engine,
        "slice",
        "-v",
        "-p",
        # Printer definition
        "-j", str(printer_def),
        # Extruder 0 definition
        "-e0",
        "-j", str(extruder_def),
    ]

    # Add all profile settings as -s flags
    for key, value in profile_settings.items():
        cmd.extend(["-s", f"{key}={value}"])

    # Input and output
    cmd.extend([
        "-l", str(stl_path),
        "-o", str(output_path),
    ])

    return cmd


def slice(
    stl_path: Path,
    output_path: Path | None = None,
    profile_name: str = "functional",
    config: dict | None = None,
) -> SliceResult:
    """
    Slice an STL file to G-code using CuraEngine.

    Args:
        stl_path: Path to the input STL file.
        output_path: Path for the output gcode. If None, uses {stl_stem}_{profile}.gcode.
        profile_name: Name of the slicing profile to use.
        config: Config dict. If None, loads from config.toml.

    Returns:
        SliceResult with success status, paths, and output.
    """
    if config is None:
        config = load_config()

    stl_path = Path(stl_path).resolve()
    if not stl_path.exists():
        return SliceResult(
            success=False, output_path=None, duration_seconds=0,
            stdout="", stderr="", error=f"STL file not found: {stl_path}"
        )

    if output_path is None:
        output_path = stl_path.parent / f"{stl_path.stem}_{profile_name}.gcode"
    output_path = Path(output_path).resolve()

    try:
        profile_settings = load_profile_settings(profile_name)
    except FileNotFoundError as e:
        return SliceResult(
            success=False, output_path=None, duration_seconds=0,
            stdout="", stderr="", error=str(e)
        )

    cmd = build_command(stl_path, output_path, profile_settings, config)
    timeout = config.get("slicing", {}).get("timeout_seconds", 300)

    # Set CURA_ENGINE_SEARCH_PATH so CuraEngine can resolve definition inheritance
    cura_resources = Path(config["paths"]["cura_resources"])
    search_paths = ";".join([
        str(cura_resources / "definitions"),
        str(cura_resources / "extruders"),
    ])
    env = {**os.environ, "CURA_ENGINE_SEARCH_PATH": search_paths}

    print(f"Slicing: {stl_path.name} with profile '{profile_name}'")
    print(f"Output:  {output_path}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        duration = time.time() - start

        if result.returncode == 0 and output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"Success! {size_kb:.0f} KB gcode in {duration:.1f}s")
            return SliceResult(
                success=True,
                output_path=output_path,
                duration_seconds=duration,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        else:
            # Extract useful error from stderr
            err_lines = [
                line for line in result.stderr.splitlines()
                if "error" in line.lower() or "failed" in line.lower()
            ]
            error_msg = "\n".join(err_lines[-5:]) if err_lines else result.stderr[-500:]
            return SliceResult(
                success=False,
                output_path=None,
                duration_seconds=duration,
                stdout=result.stdout,
                stderr=result.stderr,
                error=f"CuraEngine exited with code {result.returncode}: {error_msg}",
            )

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return SliceResult(
            success=False, output_path=None, duration_seconds=duration,
            stdout="", stderr="", error=f"Slicing timed out after {timeout}s"
        )
    except FileNotFoundError:
        return SliceResult(
            success=False, output_path=None, duration_seconds=0,
            stdout="", stderr="",
            error=f"CuraEngine not found at: {config['paths']['cura_engine']}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Slice STL to G-code with CuraEngine")
    parser.add_argument("stl", help="Path to STL file")
    parser.add_argument("--profile", "-p", default="functional", help="Slicing profile name")
    parser.add_argument("--output", "-o", help="Output gcode path (default: alongside STL)")
    args = parser.parse_args()

    result = slice(
        stl_path=Path(args.stl),
        output_path=Path(args.output) if args.output else None,
        profile_name=args.profile,
    )

    if result.success:
        print(f"\nDone: {result.output_path}")
    else:
        print(f"\nFailed: {result.error}", file=sys.stderr)
        sys.exit(1)
