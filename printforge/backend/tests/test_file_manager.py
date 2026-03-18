"""Tests for G-code file storage management."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch


class TestGetGcodePath:
    """Test path traversal protection in get_gcode_path."""

    def test_normal_filename(self, tmp_path):
        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import get_gcode_path

            result = get_gcode_path("benchy.gcode")
            assert result == (tmp_path / "benchy.gcode").resolve()

    def test_path_traversal_blocked(self, tmp_path):
        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import get_gcode_path

            with pytest.raises(ValueError, match="path traversal"):
                get_gcode_path("../../etc/passwd")

    def test_path_traversal_dotdot_in_middle(self, tmp_path):
        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import get_gcode_path

            with pytest.raises(ValueError, match="path traversal"):
                get_gcode_path("subdir/../../outside.gcode")

    def test_subfolder_allowed(self, tmp_path):
        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import get_gcode_path

            result = get_gcode_path("project/benchy.gcode")
            assert str(result).startswith(str(tmp_path.resolve()))

    def test_absolute_path_blocked(self, tmp_path):
        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import get_gcode_path

            # /tmp/evil.gcode resolves outside GCODE_DIR
            with pytest.raises(ValueError, match="path traversal"):
                get_gcode_path("/tmp/evil.gcode")


class TestEnsureGcodeDir:
    """Test directory creation."""

    def test_creates_directory(self, tmp_path):
        target = tmp_path / "new_gcodes"
        with patch("app.storage.file_manager.GCODE_DIR", target):
            from app.storage.file_manager import ensure_gcode_dir

            ensure_gcode_dir()
            assert target.exists()
            assert target.is_dir()

    def test_idempotent(self, tmp_path):
        target = tmp_path / "gcodes"
        target.mkdir()
        with patch("app.storage.file_manager.GCODE_DIR", target):
            from app.storage.file_manager import ensure_gcode_dir

            ensure_gcode_dir()  # should not raise
            assert target.exists()


class TestListGcodeFiles:
    """Test G-code file listing."""

    def test_lists_gcode_extensions(self, tmp_path):
        (tmp_path / "a.gcode").write_text("G28")
        (tmp_path / "b.g").write_text("G28")
        (tmp_path / "c.gc").write_text("G28")
        (tmp_path / "d.txt").write_text("not gcode")
        (tmp_path / "e.stl").write_text("not gcode")

        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import list_gcode_files

            files = list_gcode_files()
            names = {f.name for f in files}
            assert "a.gcode" in names
            assert "b.g" in names
            assert "c.gc" in names
            assert "d.txt" not in names
            assert "e.stl" not in names

    def test_empty_directory(self, tmp_path):
        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import list_gcode_files

            files = list_gcode_files()
            assert files == []

    def test_sorted_by_mtime_descending(self, tmp_path):
        import time

        (tmp_path / "old.gcode").write_text("G28")
        time.sleep(0.05)
        (tmp_path / "new.gcode").write_text("G28")

        with patch("app.storage.file_manager.GCODE_DIR", tmp_path):
            from app.storage.file_manager import list_gcode_files

            files = list_gcode_files()
            assert files[0].name == "new.gcode"
            assert files[1].name == "old.gcode"
