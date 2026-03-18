"""Tests for database operations (SQLite)."""

import os
import tempfile
import pytest
import asyncio

# Override data dir BEFORE importing any app modules
_test_data_dir = tempfile.mkdtemp(prefix="pf_dbtest_")
os.environ["PRINTFORGE_DATA_DIR"] = _test_data_dir


@pytest.fixture
async def db():
    """Provide a fresh database for each test."""
    from app.storage import database

    # Force a fresh DB path for each test
    test_db = tempfile.mktemp(suffix=".db", dir=_test_data_dir)
    database.DB_PATH = __import__("pathlib").Path(test_db)
    database._db = None  # Reset singleton

    await database.init_db()
    yield
    await database.close_db()
    # Cleanup
    try:
        os.unlink(test_db)
    except OSError:
        pass


class TestDatabaseInit:
    """Test database initialization."""

    @pytest.mark.asyncio
    async def test_init_creates_tables(self, db):
        from app.storage.database import get_db

        conn = await get_db()
        # Check tables exist
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}
        assert "print_jobs" in tables
        assert "settings" in tables
        assert "filament_spools" in tables

    @pytest.mark.asyncio
    async def test_init_is_idempotent(self, db):
        from app.storage.database import init_db

        # Should not raise on second call
        await init_db()


class TestPrintJobs:
    """Test print job CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_print_job(self, db):
        from app.storage.models import create_print_job, get_print_history

        job_id = await create_print_job("benchy.gcode", 5000, 210.0, 60.0)
        assert job_id is not None
        assert isinstance(job_id, int)
        assert job_id > 0

    @pytest.mark.asyncio
    async def test_complete_print_job(self, db):
        from app.storage.models import (
            create_print_job,
            complete_print_job,
            get_print_history,
        )

        job_id = await create_print_job("test.gcode", 1000)
        await complete_print_job(job_id, "completed", 3600, 950, 2500.0)

        history = await get_print_history()
        assert len(history) == 1
        assert history[0]["status"] == "completed"
        assert history[0]["duration_seconds"] == 3600
        assert history[0]["lines_printed"] == 950
        assert history[0]["filament_used_mm"] == pytest.approx(2500.0)

    @pytest.mark.asyncio
    async def test_print_history_ordered_desc(self, db):
        from app.storage.models import create_print_job, get_print_history

        await create_print_job("first.gcode", 100)
        await create_print_job("second.gcode", 200)
        await create_print_job("third.gcode", 300)

        history = await get_print_history()
        assert history[0]["filename"] == "third.gcode"
        assert history[2]["filename"] == "first.gcode"

    @pytest.mark.asyncio
    async def test_print_history_limit(self, db):
        from app.storage.models import create_print_job, get_print_history

        for i in range(10):
            await create_print_job(f"job_{i}.gcode", 100)

        history = await get_print_history(limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_cancelled_job(self, db):
        from app.storage.models import (
            create_print_job,
            complete_print_job,
            get_print_history,
        )

        job_id = await create_print_job("failed.gcode", 5000)
        await complete_print_job(job_id, "cancelled", 600, 500)

        history = await get_print_history()
        assert history[0]["status"] == "cancelled"


class TestSettings:
    """Test key-value settings."""

    @pytest.mark.asyncio
    async def test_get_default_when_missing(self, db):
        from app.storage.models import get_setting

        val = await get_setting("nonexistent", "fallback")
        assert val == "fallback"

    @pytest.mark.asyncio
    async def test_set_and_get(self, db):
        from app.storage.models import set_setting, get_setting

        await set_setting("theme", "dark")
        val = await get_setting("theme")
        assert val == "dark"

    @pytest.mark.asyncio
    async def test_overwrite_setting(self, db):
        from app.storage.models import set_setting, get_setting

        await set_setting("key", "value1")
        await set_setting("key", "value2")
        assert await get_setting("key") == "value2"

    @pytest.mark.asyncio
    async def test_get_all_settings(self, db):
        from app.storage.models import set_setting, get_all_settings

        await set_setting("a", "1")
        await set_setting("b", "2")
        all_settings = await get_all_settings()
        assert all_settings["a"] == "1"
        assert all_settings["b"] == "2"

    @pytest.mark.asyncio
    async def test_get_all_settings_empty(self, db):
        from app.storage.models import get_all_settings

        all_settings = await get_all_settings()
        assert all_settings == {}


class TestFilamentSpools:
    """Test filament spool management."""

    @pytest.mark.asyncio
    async def test_create_spool(self, db):
        from app.storage.models import create_spool, get_spools

        spool_id = await create_spool("Hatchbox PLA", "PLA", "#FF0000", 1000, 18.0)
        assert spool_id > 0
        spools = await get_spools()
        assert len(spools) == 1
        assert spools[0]["name"] == "Hatchbox PLA"
        assert spools[0]["material"] == "PLA"

    @pytest.mark.asyncio
    async def test_activate_spool(self, db):
        from app.storage.models import create_spool, set_active_spool, get_active_spool

        id1 = await create_spool("Spool A", "PLA")
        id2 = await create_spool("Spool B", "PETG")

        await set_active_spool(id1)
        active = await get_active_spool()
        assert active["name"] == "Spool A"

        # Switch active spool
        await set_active_spool(id2)
        active = await get_active_spool()
        assert active["name"] == "Spool B"

    @pytest.mark.asyncio
    async def test_no_active_spool(self, db):
        from app.storage.models import get_active_spool

        active = await get_active_spool()
        assert active is None

    @pytest.mark.asyncio
    async def test_deduct_filament(self, db):
        from app.storage.models import create_spool, deduct_filament, get_spool

        spool_id = await create_spool("Test Spool", total_weight_g=1000)
        await deduct_filament(spool_id, 50.0)
        spool = await get_spool(spool_id)
        assert spool["used_weight_g"] == pytest.approx(50.0)

        await deduct_filament(spool_id, 25.0)
        spool = await get_spool(spool_id)
        assert spool["used_weight_g"] == pytest.approx(75.0)

    @pytest.mark.asyncio
    async def test_update_spool(self, db):
        from app.storage.models import create_spool, update_spool, get_spool

        spool_id = await create_spool("Old Name", "PLA")
        await update_spool(spool_id, name="New Name", material="PETG")
        spool = await get_spool(spool_id)
        assert spool["name"] == "New Name"
        assert spool["material"] == "PETG"

    @pytest.mark.asyncio
    async def test_delete_spool(self, db):
        from app.storage.models import create_spool, delete_spool, get_spools

        spool_id = await create_spool("Doomed Spool")
        await delete_spool(spool_id)
        spools = await get_spools()
        assert len(spools) == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_spool(self, db):
        from app.storage.models import get_spool

        spool = await get_spool(99999)
        assert spool is None

    @pytest.mark.asyncio
    async def test_only_one_active_spool(self, db):
        from app.storage.models import create_spool, set_active_spool, get_spools

        ids = []
        for name in ["A", "B", "C"]:
            ids.append(await create_spool(name))

        await set_active_spool(ids[0])
        await set_active_spool(ids[2])

        spools = await get_spools()
        active_count = sum(1 for s in spools if s["active"])
        assert active_count == 1


class TestTimeCorrectionFactor:
    """Test print time correction calculation."""

    @pytest.mark.asyncio
    async def test_returns_1_with_no_data(self, db):
        from app.storage.models import get_time_correction_factor

        factor = await get_time_correction_factor()
        assert factor == 1.0

    @pytest.mark.asyncio
    async def test_returns_1_with_one_datapoint(self, db):
        from app.storage.models import (
            create_print_job,
            complete_print_job,
            update_job_estimated_seconds,
            get_time_correction_factor,
        )

        job_id = await create_print_job("test.gcode", 100)
        await update_job_estimated_seconds(job_id, 1000.0)
        await complete_print_job(job_id, "completed", 1200, 100)

        factor = await get_time_correction_factor()
        assert factor == 1.0  # needs at least 2 data points
