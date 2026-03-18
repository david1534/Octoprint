"""Tests for bed mesh parsing."""

import pytest

from app.serial.bed_mesh import BedMesh, BedMeshParser


class TestBedMeshParser:
    """Test parsing of Marlin bed mesh output."""

    def test_bilinear_grid_parsing(self):
        """Parse a standard Bilinear Leveling Grid output."""
        parser = BedMeshParser()
        lines = [
            "Bilinear Leveling Grid:",
            "      0      1      2",
            " 0 +0.125 +0.087 +0.050",
            " 1 +0.100 +0.062 +0.025",
            " 2 -0.010 -0.050 -0.100",
            "ok",
        ]
        result = None
        for line in lines:
            r = parser.feed_line(line)
            if r is not None:
                result = r

        assert result is not None
        assert result.rows == 3
        assert result.cols == 3
        assert result.grid[0] == [0.125, 0.087, 0.050]
        assert result.grid[2] == [-0.010, -0.050, -0.100]

    def test_ubl_topography_report(self):
        """Parse a UBL Bed Topography Report."""
        parser = BedMeshParser()
        lines = [
            "Bed Topography Report:",
            "        0       1       2       3",
            " 0  +0.120  +0.090  +0.050  +0.010",
            " 1  +0.080  +0.040  +0.000  -0.030",
            "ok",
        ]
        result = None
        for line in lines:
            r = parser.feed_line(line)
            if r is not None:
                result = r

        assert result is not None
        assert result.rows == 2
        assert result.cols == 4
        assert result.grid[0][0] == pytest.approx(0.120)

    def test_manual_mesh_leveling(self):
        """Parse a Manual Mesh Bed Leveling output."""
        parser = BedMeshParser()
        lines = [
            "Mesh Bed Leveling:",
            "      0      1      2",
            " 0 +0.050 +0.020 -0.010",
            " 1 +0.030 +0.000 -0.020",
            "ok",
        ]
        result = None
        for line in lines:
            r = parser.feed_line(line)
            if r is not None:
                result = r

        assert result is not None
        assert result.rows == 2
        assert result.cols == 3

    def test_mesh_statistics(self):
        """Verify min/max/mean/range calculations."""
        parser = BedMeshParser()
        lines = [
            "Bilinear Leveling Grid:",
            "      0      1",
            " 0 +0.100 -0.100",
            " 1 +0.200 -0.200",
            "ok",
        ]
        result = None
        for line in lines:
            r = parser.feed_line(line)
            if r is not None:
                result = r

        assert result is not None
        assert result.min_z == pytest.approx(-0.200)
        assert result.max_z == pytest.approx(0.200)
        assert result.range_z == pytest.approx(0.400)
        assert result.mean_z == pytest.approx(0.0)

    def test_mesh_property_persists(self):
        """Parsed mesh is accessible via the .mesh property."""
        parser = BedMeshParser()
        assert parser.mesh is None
        lines = [
            "Bilinear Leveling Grid:",
            "      0      1",
            " 0 +0.100 +0.050",
            "ok",
        ]
        for line in lines:
            parser.feed_line(line)
        assert parser.mesh is not None
        assert parser.mesh.rows == 1

    def test_no_data_rows_after_header(self):
        """Header detected but no data rows follow -> no mesh produced."""
        parser = BedMeshParser()
        parser.feed_line("Bilinear Leveling Grid:")
        result = parser.feed_line("ok")
        assert result is None
        assert parser.mesh is None

    def test_non_mesh_lines_ignored(self):
        """Lines without a mesh header are ignored."""
        parser = BedMeshParser()
        assert parser.feed_line("ok") is None
        assert parser.feed_line("echo:Compiled Jun 2023") is None
        assert parser.feed_line("T:200.0 /200.0 B:60.0 /60.0") is None

    def test_mesh_active_defaults_true_after_g29(self):
        """G29 output mesh should default to active."""
        parser = BedMeshParser()
        lines = [
            "Bilinear Leveling Grid:",
            "      0      1",
            " 0 +0.100 +0.050",
            "ok",
        ]
        for line in lines:
            parser.feed_line(line)
        assert parser.mesh.mesh_active is True


class TestM420Status:
    """Test M420 bed leveling status parsing."""

    def test_leveling_on(self):
        parser = BedMeshParser()
        result = parser.parse_m420_status("echo:Bed Leveling ON")
        assert result is True

    def test_leveling_off(self):
        parser = BedMeshParser()
        result = parser.parse_m420_status("echo:Bed Leveling OFF")
        assert result is False

    def test_unrelated_line_returns_none(self):
        parser = BedMeshParser()
        assert parser.parse_m420_status("ok") is None
        assert parser.parse_m420_status("T:200.0 /200.0") is None

    def test_m420_updates_existing_mesh(self):
        """M420 status should update the mesh_active flag on existing mesh."""
        parser = BedMeshParser()
        # First parse a mesh
        for line in [
            "Bilinear Leveling Grid:",
            "      0      1",
            " 0 +0.100 +0.050",
            "ok",
        ]:
            parser.feed_line(line)
        assert parser.mesh.mesh_active is True

        # Turn off via M420
        parser.parse_m420_status("echo:Bed Leveling OFF")
        assert parser.mesh.mesh_active is False


class TestBedMeshToDict:
    """Test BedMesh serialization."""

    def test_to_dict_structure(self):
        mesh = BedMesh(
            grid=[[0.1, -0.1], [0.2, -0.2]],
            rows=2,
            cols=2,
            min_z=-0.2,
            max_z=0.2,
            mean_z=0.0,
            range_z=0.4,
            mesh_active=True,
            timestamp=1234567890.0,
        )
        d = mesh.to_dict()
        assert d["rows"] == 2
        assert d["cols"] == 2
        assert d["min"] == -0.2
        assert d["max"] == 0.2
        assert d["mean"] == 0.0
        assert d["range"] == 0.4
        assert d["active"] is True
        assert d["grid"] == [[0.1, -0.1], [0.2, -0.2]]
        assert d["timestamp"] == 1234567890.0
