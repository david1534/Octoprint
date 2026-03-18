"""
PrintForge G-code upload client.

Uploads sliced G-code files to the PrintForge API.

Usage:
    python uploader.py path/to/file.gcode
    python uploader.py path/to/file.gcode --subfolder "My Project"
"""

import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def upload(
    gcode_path: Path,
    subfolder: str = "",
    url: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> dict:
    """
    Upload a G-code file to PrintForge.

    Args:
        gcode_path: Path to the .gcode file.
        subfolder: Optional subfolder in PrintForge to place the file.
        url: PrintForge base URL. If None, reads from config.
        api_key: API key for auth. If None, reads from config.
        timeout: Upload timeout in seconds.

    Returns:
        Parsed JSON response from the API.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        FileNotFoundError: If gcode file doesn't exist.
    """
    gcode_path = Path(gcode_path).resolve()
    if not gcode_path.exists():
        raise FileNotFoundError(f"G-code file not found: {gcode_path}")

    if url is None or api_key is None:
        config = load_config()
        if url is None:
            url = config["printforge"]["url"]
        if api_key is None:
            api_key = config["printforge"].get("api_key", "")

    upload_url = f"{url}/api/files/upload"
    if subfolder:
        upload_url += f"?path={subfolder}"

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"Uploading: {gcode_path.name} -> {url}")
    if subfolder:
        print(f"  Subfolder: {subfolder}")

    with open(gcode_path, "rb") as f:
        files = {"file": (gcode_path.name, f, "application/octet-stream")}
        response = httpx.post(
            upload_url,
            files=files,
            headers=headers,
            timeout=timeout,
        )

    response.raise_for_status()
    data = response.json()
    print(f"  Uploaded successfully: {data.get('filename', gcode_path.name)}")
    return data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload G-code to PrintForge")
    parser.add_argument("gcode", help="Path to G-code file")
    parser.add_argument("--subfolder", "-s", default="", help="Target subfolder in PrintForge")
    args = parser.parse_args()

    try:
        result = upload(Path(args.gcode), subfolder=args.subfolder)
        print(f"\nDone: {result}")
    except httpx.HTTPStatusError as e:
        print(f"\nUpload failed: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
