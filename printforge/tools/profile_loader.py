"""
Parse Cura quality_changes .inst.cfg profiles into flat key-value dicts
suitable for CuraEngine CLI -s flags.

Resolves the full default settings chain (fdmprinter -> creality_base ->
creality_ender3s1pro + extruder) then overlays user profile settings on top.

Usage:
    python profile_loader.py                # Export all profiles to tools/profiles/
    python profile_loader.py --list         # List available profiles
"""

import configparser
import json
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

# Where Cura stores user quality_changes profiles
CURA_QUALITY_DIR = Path.home() / "AppData/Roaming/cura/5.11/quality_changes"

# Profile definitions: name -> (machine_cfg_filename, extruder_cfg_filename)
PROFILE_MAP = {
    "functional": (
        "creality_ender3s1pro_functional_profile.inst.cfg",
        "creality_base_extruder_0_%232_functional_profile.inst.cfg",
    ),
    "fast": (
        "creality_ender3s1pro_fast_printing_profile.inst.cfg",
        "creality_base_extruder_0_%232_fast_printing_profile.inst.cfg",
    ),
    "petg": (
        "creality_ender3s1pro_petg_prints.inst.cfg",
        "creality_base_extruder_0_%232_petg_prints.inst.cfg",
    ),
    "ultra_fast": (
        "creality_ender3s1pro_uber_fast_printing_profile.inst.cfg",
        "creality_base_extruder_0_%232_uber_fast_printing_profile.inst.cfg",
    ),
}

# Human-readable display names
PROFILE_LABELS = {
    "functional": "Functional (PLA, 80% infill, 8 walls)",
    "fast": "Fast Printing (15% infill, 3 walls)",
    "petg": "PETG (gyroid, slower speeds)",
    "ultra_fast": "Ultra Fast (high accel/jerk, 2 walls)",
}


def get_cura_resources() -> Path:
    """Get the Cura resources path from config.toml."""
    config_path = Path(__file__).parent / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return Path(config["paths"]["cura_resources"])


def extract_definition_defaults(filepath: Path) -> dict[str, str]:
    """Extract all default_value entries from a Cura definition JSON file."""
    with open(filepath) as f:
        data = json.load(f)

    defaults = {}

    def walk_settings(settings: dict):
        for key, val in settings.items():
            if isinstance(val, dict):
                if "default_value" in val:
                    defaults[key] = val["default_value"]
                if "children" in val:
                    walk_settings(val["children"])

    if "settings" in data:
        walk_settings(data["settings"])
    if "overrides" in data:
        for key, val in data["overrides"].items():
            if isinstance(val, dict) and "default_value" in val:
                defaults[key] = val["default_value"]

    return defaults


def load_all_defaults() -> dict[str, str]:
    """
    Load all default settings by walking the definition inheritance chain:
    fdmprinter -> creality_base -> creality_ender3s1pro + extruder defaults.
    """
    resources = get_cura_resources()
    defs_dir = resources / "definitions"
    extruders_dir = resources / "extruders"

    # Walk printer definition chain (base first, overrides later)
    all_defaults: dict[str, str] = {}
    for name in ["fdmprinter", "creality_base", "creality_ender3s1pro"]:
        fp = defs_dir / f"{name}.def.json"
        if fp.exists():
            defs = extract_definition_defaults(fp)
            # Convert all values to strings for CuraEngine -s flags
            for k, v in defs.items():
                all_defaults[k] = str(v)

    # Also get extruder defaults
    extruder_def = extruders_dir / "creality_base_extruder_0.def.json"
    if extruder_def.exists():
        defs = extract_definition_defaults(extruder_def)
        for k, v in defs.items():
            all_defaults[k] = str(v)

    # Also check fdmextruder (base extruder definition)
    fdm_extruder = defs_dir / "fdmextruder.def.json"
    if fdm_extruder.exists():
        defs = extract_definition_defaults(fdm_extruder)
        for k, v in defs.items():
            if k not in all_defaults:  # Don't override more specific values
                all_defaults[k] = str(v)

    return all_defaults


def parse_cfg_values(filepath: Path) -> dict[str, str]:
    """Parse the [values] section from a Cura .inst.cfg file."""
    cfg = configparser.ConfigParser()
    cfg.read(filepath, encoding="utf-8")
    if cfg.has_section("values"):
        return dict(cfg.items("values"))
    return {}


def load_profile(name: str, include_defaults: bool = True) -> dict[str, str]:
    """
    Load a complete settings dict for a named profile.

    If include_defaults is True (default), starts with ALL resolved default
    settings from the printer definition chain, then overlays the user's
    profile settings on top. This produces a complete settings dict that
    CuraEngine can use without hitting missing-value errors.
    """
    if name not in PROFILE_MAP:
        raise ValueError(f"Unknown profile: {name}. Available: {list(PROFILE_MAP.keys())}")

    # Start with defaults
    settings: dict[str, str] = {}
    if include_defaults:
        settings = load_all_defaults()

    # Overlay user profile settings
    machine_file, extruder_file = PROFILE_MAP[name]
    machine_path = CURA_QUALITY_DIR / machine_file
    extruder_path = CURA_QUALITY_DIR / extruder_file

    if machine_path.exists():
        settings.update(parse_cfg_values(machine_path))
    else:
        print(f"  Warning: machine config not found: {machine_path}")

    if extruder_path.exists():
        settings.update(parse_cfg_values(extruder_path))
    else:
        print(f"  Warning: extruder config not found: {extruder_path}")

    return settings


def export_all(output_dir: Path) -> None:
    """Export all profiles as JSON files (with full defaults included)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Also export just the defaults for reference
    defaults = load_all_defaults()
    defaults_path = output_dir / "defaults.json"
    with open(defaults_path, "w") as f:
        json.dump(defaults, f, indent=2, sort_keys=True)
    print(f"Exported defaults: {len(defaults)} settings -> {defaults_path}")

    for name in PROFILE_MAP:
        print(f"Exporting profile: {name}")
        settings = load_profile(name, include_defaults=True)
        out_path = output_dir / f"{name}.json"
        with open(out_path, "w") as f:
            json.dump(settings, f, indent=2, sort_keys=True)

        # Count how many are user overrides vs defaults
        user_overrides = load_profile(name, include_defaults=False)
        print(f"  -> {out_path} ({len(settings)} total, {len(user_overrides)} user overrides)")

    print(f"\nDone! Exported {len(PROFILE_MAP)} profiles + defaults.")


def list_profiles() -> None:
    """Print available profiles and their settings counts."""
    for name, label in PROFILE_LABELS.items():
        try:
            user_settings = load_profile(name, include_defaults=False)
            print(f"  {name:12s} - {label} [{len(user_settings)} user overrides]")
        except Exception as e:
            print(f"  {name:12s} - ERROR: {e}")


if __name__ == "__main__":
    tools_dir = Path(__file__).parent
    profiles_dir = tools_dir / "profiles"

    if "--list" in sys.argv:
        print("Available profiles:")
        list_profiles()
    else:
        export_all(profiles_dir)
