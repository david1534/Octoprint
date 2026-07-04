"""Filesystem path safety helpers.

Centralizes the containment check used by every endpoint that resolves a
user-supplied path under a trusted root (G-code storage). The previous
`str(resolved).startswith(str(root))` idiom let a sibling directory whose
name merely *starts with* the root's name (e.g. ``gcodes_backup`` next to
``gcodes``) pass the check via ``..``. This uses real path-component
containment instead, which has no such prefix-collision hole.
"""

from __future__ import annotations

from pathlib import Path


def is_within(root: Path, target: Path) -> bool:
    """Return True if `target` is `root` itself or lives inside it.

    Both paths are resolved (symlinks + ``..`` collapsed) before comparison,
    so traversal attempts like ``../gcodes_backup/x`` are rejected.
    """
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    return target_resolved == root_resolved or root_resolved in target_resolved.parents
