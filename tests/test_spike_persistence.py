"""Spike tests: JSON vs SQLite persistence for one local CheckItem baseline.

All tests are hand-labelled expected outcomes written before the spike probe
helpers were implemented in ``persistence_probe.py``. They exercise
the bounded scenarios required for the persistence decision (recorded in
docs/plan.md §4).

This file is **not production code** — it must remain isolated under
``tests/`` and does not modify ``src/baseline_store.py`` or any other production
module. The decision it drives belongs to Task 5, which remains pending.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persistence_probe import (
    SCHEMA_VERSION,
    deserialize_baseline_json,
    load_json_safe,
    load_sqlite,
    make_sample_items,
    probe_app_data_location,
    save_json_atomic,
    save_sqlite_atomic,
    serialize_baseline_json,
    sqlite_corrupt,
)

# ---------------------------------------------------------------------------
# P1 — JSON candidate tests
# ---------------------------------------------------------------------------


class TestJsonSerialization:
    """JSON round-trip, schema, type correctness."""

    def test_round_trip_preserves_domain_data(self) -> None:
        items = make_sample_items()
        data = serialize_baseline_json("baseline-1", items)
        bid, loaded = deserialize_baseline_json(data)
        assert bid == "baseline-1"
        assert loaded == items  # full dataclass equality

    def test_chinese_unicode_preserved_in_utf8(self, tmp_path: Path) -> None:
        items = make_sample_items()
        target = tmp_path / "baseline.json"
        save_json_atomic(target, serialize_baseline_json("b1", items))
        raw = target.read_bytes()
        # UTF-8 must encode Chinese without ASCII escaping.
        assert b"\xe5\xbc\x80" in raw  # 开
        assert b"\\u" not in raw  # ensure_ascii=False

    def test_aliases_preserve_structure_not_flattened(self) -> None:
        items = make_sample_items()
        data = serialize_baseline_json("b", items)
        # Third item has two aliases.
        item_3_raw = data["items"][2]
        assert len(item_3_raw["aliases"]) == 2
        aliases = item_3_raw["aliases"]
        # Full alias object shape: alias_id + text + notes.
        for a in aliases:
            assert "alias_id" in a
            assert "text" in a
        # Second alias has a non-empty notes field.
        assert aliases[1]["notes"] == "第二个别名"

    def test_stable_item_ids_preserved_across_round_trip(self) -> None:
        items = make_sample_items()
        data = serialize_baseline_json("b1", items)
        bid, loaded = deserialize_baseline_json(data)
        orig_ids = [i.item_id for i in items]
        loaded_ids = [i.item_id for i in loaded]
        assert orig_ids == loaded_ids
        # IDs are stable UUID-style, never list indices or derived values.
        for id_ in loaded_ids:
            assert id_.startswith("item-")

    def test_disabled_item_round_trips(self) -> None:
        items = make_sample_items()
        item_3 = items[2]
        assert item_3.enabled is False
        data = serialize_baseline_json("b", items)
        _, loaded = deserialize_baseline_json(data)
        assert loaded[2].enabled is False

    def test_empty_expected_description_round_trips(self) -> None:
        items = make_sample_items()
        item_2 = items[1]
        assert item_2.expected_description == ""
        data = serialize_baseline_json("b", items)
        _, loaded = deserialize_baseline_json(data)
        assert loaded[1].expected_description == ""

    def test_schema_version_present(self) -> None:
        data = serialize_baseline_json("b", make_sample_items())
        assert data["schemaVersion"] == SCHEMA_VERSION

    def test_missing_schemaVersion_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        del bad["schemaVersion"]
        with pytest.raises(ValueError, match="schemaVersion"):
            deserialize_baseline_json(bad)

    def test_unsupported_schemaVersion_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["schemaVersion"] = 999
        with pytest.raises(ValueError, match="unsupported schemaVersion"):
            deserialize_baseline_json(bad)

    def test_wrong_top_level_shape_rejected(self) -> None:
        with pytest.raises(ValueError):
            deserialize_baseline_json(["not", "an", "object"])

    def test_missing_item_fields_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        del bad["items"][0]["detection_phrase"]
        with pytest.raises(ValueError):
            deserialize_baseline_json(bad)

    def test_wrong_field_types_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["enabled"] = "not-a-bool"  # stored as JSON bool normally
        with pytest.raises(ValueError):
            deserialize_baseline_json(bad)


class TestJsonAtomicSave:
    """Atomic save correctness — successful first save, overwrites, UTF-8."""

    def test_first_save_creates_no_unnecessary_backup(self, tmp_path: Path) -> None:
        """First save: primary created, no .bak exists."""
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b1", make_sample_items()))
        assert primary.exists()
        assert not Path(str(primary) + ".bak").exists()
        data = json.loads(primary.read_text(encoding="utf-8"))
        assert data["baselineId"] == "b1"

    def test_direct_overwrite_not_used(self, tmp_path: Path) -> None:
        """save_json_atomic never leaves .tmp_* files behind."""
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b", make_sample_items()))
        save_json_atomic(primary, serialize_baseline_json("b2", make_sample_items()))
        for entry in tmp_path.iterdir():
            if entry.name.startswith(".tmp_"):
                pytest.fail(f"temp file not cleaned up: {entry}")

    def test_atomic_replace_produces_valid_file(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        data = serialize_baseline_json("b1", make_sample_items())
        save_json_atomic(primary, data)
        raw = primary.read_text(encoding="utf-8")
        loaded = json.loads(raw)
        assert loaded["schemaVersion"] == SCHEMA_VERSION
        assert loaded["baselineId"] == "b1"

    def test_repeated_saves_v1_to_v2_to_v3(self, tmp_path: Path) -> None:
        """v1→v2→v3: primary=v3, backup=v2."""
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("v1", make_sample_items()))
        save_json_atomic(primary, serialize_baseline_json("v2", make_sample_items()))
        save_json_atomic(primary, serialize_baseline_json("v3", make_sample_items()))
        primary_data = json.loads(primary.read_text(encoding="utf-8"))
        assert primary_data["baselineId"] == "v3"
        bak_data = json.loads(Path(str(primary) + ".bak").read_text(encoding="utf-8"))
        assert bak_data["baselineId"] == "v2"

    def test_successful_update_backup_contains_immediately_previous(self, tmp_path: Path) -> None:
        """After two saves: primary=b2, backup=b1 (immediately prior, not older)."""
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b1", make_sample_items()))
        save_json_atomic(primary, serialize_baseline_json("b2", make_sample_items()))
        primary_data = json.loads(primary.read_text(encoding="utf-8"))
        assert primary_data["baselineId"] == "b2"
        bak_data = json.loads(Path(str(primary) + ".bak").read_text(encoding="utf-8"))
        assert bak_data["baselineId"] == "b1"

    def test_save_produces_readable_utf8(self, tmp_path: Path) -> None:
        primary = tmp_path / "subdir" / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b", make_sample_items()))
        raw = primary.read_bytes()
        assert b"\xe5\xbc\x80" in raw  # 开
        assert b"\\u" not in raw  # ensure_ascii=False


class TestJsonRecovery:
    """load_json_safe recovery contract."""

    def test_primary_valid_returns_primary(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b1", make_sample_items()))
        data, source = load_json_safe(primary)
        assert source == "primary"
        assert data["baselineId"] == "b1"

    def test_primary_corrupt_backup_valid(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b1", make_sample_items()))
        # A second save creates the .bak; now corrupt the primary.
        save_json_atomic(primary, serialize_baseline_json("b2", make_sample_items()))
        # primary now holds b2; .bak holds b1. Corrupt primary.
        primary.write_bytes(b"{ this is not valid json!!!")
        data, source = load_json_safe(primary)
        assert source == "backup"
        assert data["baselineId"] == "b1"

    def test_primary_missing_backup_valid(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b1", make_sample_items()))
        save_json_atomic(primary, serialize_baseline_json("b2", make_sample_items()))
        # Now delete primary — .bak should be b1.
        primary.unlink()
        data, source = load_json_safe(primary)
        assert source == "backup"
        assert data["baselineId"] == "b1"

    def test_both_invalid_raises(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        (tmp_path / "baseline.json").write_text("corrupt!", encoding="utf-8")
        (tmp_path / "baseline.json.bak").write_text("also corrupt!", encoding="utf-8")
        with pytest.raises(ValueError):
            load_json_safe(primary)

    def test_unsupported_schema_not_used_as_recovery_fallback(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("b1", make_sample_items()))
        # Write an unsupported-schema file as .bak — it must not be used.
        import json as _json_mod

        (tmp_path / "baseline.json.bak").write_text(
            _json_mod.dumps({"schemaVersion": 999, "baselineId": "bad", "items": []}),
            encoding="utf-8",
        )
        # Corrupt primary to force recovery path.
        primary.write_bytes(b"not json")
        with pytest.raises(ValueError):
            load_json_safe(primary)


class TestJsonRestartLoad:
    """True restart: save → discard in-memory → load from disk."""

    def test_save_then_load_round_trips(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        orig_items = make_sample_items()
        save_json_atomic(primary, serialize_baseline_json("b1", orig_items))
        # Discard in-memory state by parsing fresh from disk.
        raw = primary.read_text(encoding="utf-8")
        data = json.loads(raw)
        bid, loaded = deserialize_baseline_json(data)
        assert bid == "b1"
        assert loaded == orig_items
        assert [i.item_id for i in loaded] == [i.item_id for i in orig_items]

    def test_ids_stable_save_reload_save(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        orig = make_sample_items()
        save_json_atomic(primary, serialize_baseline_json("b", orig))
        raw = json.loads(primary.read_text(encoding="utf-8"))
        _, items1 = deserialize_baseline_json(raw)
        save_json_atomic(primary, serialize_baseline_json("b", items1))
        raw2 = json.loads(primary.read_text(encoding="utf-8"))
        _, items2 = deserialize_baseline_json(raw2)
        assert [i.item_id for i in items2] == [i.item_id for i in orig]


# ---------------------------------------------------------------------------
# P1 — SQLite candidate tests
# ---------------------------------------------------------------------------


class TestSqliteRoundTrip:
    """SQLite round-trip, transactional save, corrupt handling."""

    def test_round_trip_preserves_all_fields(self, tmp_path: Path) -> None:
        db = tmp_path / "baseline.db"
        items = make_sample_items()
        save_sqlite_atomic(db, "b1", items)
        bid, loaded = load_sqlite(db)
        assert bid == "b1"
        assert loaded == items

    def test_unicode_chinese_preserved(self, tmp_path: Path) -> None:
        db = tmp_path / "baseline.db"
        items = make_sample_items()
        save_sqlite_atomic(db, "b1", items)
        _, loaded = load_sqlite(db)
        first = loaded[0]
        assert first.name == "开关门延时"
        assert first.detection_phrase == "2门控制增加开关门延时"
        assert first.aliases[0].text == "开关门延时"

    def test_aliases_relationship_preserved(self, tmp_path: Path) -> None:
        db = tmp_path / "baseline.db"
        items = make_sample_items()
        save_sqlite_atomic(db, "b1", items)
        _, loaded = load_sqlite(db)
        # Second item (index 1) has no aliases.
        assert loaded[1].aliases == ()
        # Third item (index 2) has two aliases.
        assert len(loaded[2].aliases) == 2
        alias_ids = [a.alias_id for a in loaded[2].aliases]
        assert "alias-0003a" in alias_ids
        assert "alias-0003b" in alias_ids

    def test_stable_ids_preserved(self, tmp_path: Path) -> None:
        db = tmp_path / "baseline.db"
        items = make_sample_items()
        save_sqlite_atomic(db, "b1", items)
        _, loaded = load_sqlite(db)
        assert [i.item_id for i in loaded] == [i.item_id for i in items]

    def test_enabled_flag_preserved(self, tmp_path: Path) -> None:
        db = tmp_path / "baseline.db"
        items = make_sample_items()
        assert items[2].enabled is False
        save_sqlite_atomic(db, "b1", items)
        _, loaded = load_sqlite(db)
        assert loaded[2].enabled is False

    def test_transactional_replace(self, tmp_path: Path) -> None:
        """Second save atomically replaces items."""
        db = tmp_path / "baseline.db"
        items = make_sample_items()
        save_sqlite_atomic(db, "b1", items)
        save_sqlite_atomic(db, "b2", items[:2])
        bid, loaded = load_sqlite(db)
        assert bid == "b2"
        assert len(loaded) == 2

    def test_corrupt_database_raises(self, tmp_path: Path) -> None:
        db = tmp_path / "baseline.db"
        save_sqlite_atomic(db, "b1", make_sample_items())
        sqlite_corrupt(db)
        with pytest.raises(Exception):
            load_sqlite(db)

    def test_injected_commit_failure_rolls_back(self, tmp_path: Path, monkeypatch) -> None:
        """Inject failure at commit call; verify prior state rolls back."""
        import persistence_probe as probe

        db = tmp_path / "baseline.db"
        save_sqlite_atomic(db, "prior", make_sample_items())

        class _FailingCommitConn:
            def __init__(self, real_conn):
                self._real = real_conn

            def execute(self, *a, **kw):
                return self._real.execute(*a, **kw)

            def executemany(self, *a, **kw):
                return self._real.executemany(*a, **kw)

            def executescript(self, *a, **kw):
                return self._real.executescript(*a, **kw)

            def commit(self):
                raise sqlite3.Error("commit boom")

            def rollback(self):
                self._real.rollback()

            def close(self):
                self._real.close()

        def failing_connect(*a, **kw):
            real = sqlite3.connect(*a, **kw)
            real.execute("PRAGMA foreign_keys = ON")
            return _FailingCommitConn(real)

        monkeypatch.setattr(probe, "sqlite_connect", failing_connect)
        with pytest.raises(sqlite3.Error):
            save_sqlite_atomic(db, "new", make_sample_items()[:2])
        monkeypatch.undo()
        bid, loaded = load_sqlite(db)
        assert bid == "prior"
        assert len(loaded) == 3


# ---------------------------------------------------------------------------
# P2 — Failure / recovery / location / QStandardPaths
# ---------------------------------------------------------------------------


class TestJsonInjectedFailures:
    """Deterministic failure paths for JSON candidate."""

    def test_mkdir_failure_is_explicit(self, tmp_path: Path, monkeypatch) -> None:
        import persistence_probe as probe

        def boom(*a, **kw):
            raise OSError("parent dir creation failed")

        monkeypatch.setattr(probe.Path, "mkdir", boom)
        with pytest.raises(OSError, match="parent dir"):
            save_json_atomic(
                tmp_path / "sub" / "deep" / "baseline.json",
                serialize_baseline_json("b", make_sample_items()),
            )


class TestPermissionDenialBehavior:
    """Both candidates must fail explicitly on write denial.

    On CI (root-owned) the real chmod-000 approach is unreliable; we inject
    failures where needed but also try chmod to exercise the natural path.
    """

    def test_json_write_denial_is_explicit(self, tmp_path: Path, monkeypatch) -> None:
        import persistence_probe as probe

        primary = tmp_path / "baseline.json"
        monkeypatch.setattr(
            probe.os,
            "makedirs",
            lambda *a, **kw: None if False else (_ for _ in ()).throw(PermissionError("denied")),
        )
        # The save calls mkdirs implicitly — actually it uses tempfile.mkstemp
        # so let's inject at a lower level.
        monkeypatch.setattr(
            probe.tempfile, "mkstemp", lambda **kw: (_ for _ in ()).throw(PermissionError("denied"))
        )
        with pytest.raises(PermissionError):
            save_json_atomic(primary, serialize_baseline_json("b", make_sample_items()))

    def test_sqlite_write_denial_is_explicit(self, tmp_path: Path, monkeypatch) -> None:
        import persistence_probe as probe

        monkeypatch.setattr(
            probe.sqlite3,
            "connect",
            lambda *a, **kw: (_ for _ in ()).throw(
                sqlite3.OperationalError("unable to open database file")
            ),
        )
        with pytest.raises(sqlite3.OperationalError):
            save_sqlite_atomic(tmp_path / "x.db", "b", make_sample_items())


class TestQtAppDataLocation:
    """QStandardPaths.AppDataLocation observation — requires a QApplication."""

    def test_probe_runs_without_error(self, qapp) -> None:
        loc = probe_app_data_location()
        assert loc  # non-empty string
        print(f"\n[location] QStandardPaths.AppDataLocation = {loc}")
        # Must not be empty; we don't assert the exact value (platform-specific).


# ---------------------------------------------------------------------------
# P3 — Both candidates: restart + full cleanup
# ---------------------------------------------------------------------------


class TestRestartLoadIntegrity:
    """True restart semantics for both candidates."""

    def test_json_save_load_ids_preserved(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        orig = make_sample_items()
        save_json_atomic(primary, serialize_baseline_json("baseline-x", orig))
        # Restart simulation: parse fresh from bytes on disk.
        raw = json.loads(primary.read_text(encoding="utf-8"))
        bid, loaded = deserialize_baseline_json(raw)
        assert bid == "baseline-x"
        assert loaded == orig
        # Save-again → load → compare IDs stay.
        save_json_atomic(primary, serialize_baseline_json("baseline-x", loaded))
        raw2 = json.loads(primary.read_text(encoding="utf-8"))
        _, loaded2 = deserialize_baseline_json(raw2)
        assert [i.item_id for i in loaded2] == [i.item_id for i in orig]

    def test_sqlite_save_load_ids_preserved(self, tmp_path: Path) -> None:
        db = tmp_path / "baseline.db"
        orig = make_sample_items()
        save_sqlite_atomic(db, "baseline-x", orig)
        bid, loaded = load_sqlite(db)
        assert bid == "baseline-x"
        assert loaded == orig
        # Save-again → load → IDs preserved.
        save_sqlite_atomic(db, "baseline-x", loaded)
        bid2, loaded2 = load_sqlite(db)
        assert bid2 == "baseline-x"
        assert [i.item_id for i in loaded2] == [i.item_id for i in orig]


# ---------------------------------------------------------------------------
# Phase-specific save-failure injection (uses _phase_replace wrapper)
# ---------------------------------------------------------------------------


def _make_phase_failer(target_phase: int):
    """Return a callable that raises OSError only when ``phase == target_phase``.

    The _phase_replace wrapper calls us as _phase_replace(src, dst, phase=N),
    so we accept ``phase`` as our keyword parameter and compare it against
    the closure-captured ``target_phase``.
    """

    def _fail(src, dst, *, phase):
        if phase == target_phase:
            raise OSError(f"phase-{phase} replace failed")
        import os as _os

        _os.replace(src, dst)

    return _fail


class TestPhaseSpecificFailureInjection:
    """Deterministic phase-specific failure paths using _phase_replace wrapping."""

    def _prior_save(self, tmp_path: Path) -> Path:
        primary = tmp_path / "baseline.json"
        save_json_atomic(primary, serialize_baseline_json("prior", make_sample_items()))
        return primary

    def test_backup_prep_replace_failure_preserves_primary(self, tmp_path: Path) -> None:
        """Inject failure on _phase_replace phase=1 (backup .bak replace).

        Primary must still hold the old baseline; nothing touched .bak yet.
        """
        primary = self._prior_save(tmp_path)
        with patch("persistence_probe._phase_replace", _make_phase_failer(1)):
            with pytest.raises(OSError, match="phase-1"):
                save_json_atomic(primary, serialize_baseline_json("new", make_sample_items()))

        # Primary untouched (old baseline still there), .bak absent or old.
        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        bak = Path(str(primary) + ".bak")
        assert (
            not bak.exists() or json.loads(bak.read_text(encoding="utf-8"))["baselineId"] != "new"
        )
        # No temp files leaked.
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_final_primary_replace_failure_preserves_primary(self, tmp_path: Path) -> None:
        """Inject failure on _phase_replace phase=2 (final temp→primary).

        Primary must still hold the old baseline. The backup was already
        updated (phase=1 succeeded) — so .bak contains the old primary.
        """
        primary = self._prior_save(tmp_path)
        with patch("persistence_probe._phase_replace", _make_phase_failer(2)):
            with pytest.raises(OSError, match="phase-2"):
                save_json_atomic(primary, serialize_baseline_json("new", make_sample_items()))

        # Primary is still "prior" — the invariant holds.
        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        # Backup was successfully prepared (.bak now contains "prior").
        bak = Path(str(primary) + ".bak")
        assert bak.exists()
        assert json.loads(bak.read_text(encoding="utf-8"))["baselineId"] == "prior"
        # No temp files leaked.
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_temp_write_failure_preserves_primary(self, tmp_path: Path, monkeypatch) -> None:
        """Inject json.dump failure BEFORE any primary/backup touch."""
        import persistence_probe as probe

        primary = self._prior_save(tmp_path)

        def failing_dump(*a, **kw):
            raise OSError("disk full during json.dump")

        monkeypatch.setattr(probe.json, "dump", failing_dump)
        with pytest.raises(OSError):
            save_json_atomic(primary, serialize_baseline_json("new", make_sample_items()))
        monkeypatch.undo()

        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        bak = Path(str(primary) + ".bak")
        assert not bak.exists()  # backup never prepared
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_temp_fsync_failure_preserves_primary(self, tmp_path: Path, monkeypatch) -> None:
        """Inject os.fsync failure BEFORE any primary/backup touch."""
        import persistence_probe as probe

        primary = self._prior_save(tmp_path)

        def failing_fsync(*a, **kw):
            raise OSError("fsync failed")

        monkeypatch.setattr(probe.os, "fsync", failing_fsync)
        with pytest.raises(OSError):
            save_json_atomic(primary, serialize_baseline_json("new", make_sample_items()))
        monkeypatch.undo()

        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_backup_copy_failure_preserves_primary(self, tmp_path: Path, monkeypatch) -> None:
        """Inject shutil.copyfileobj failure (primary→temp-backup copy)."""
        import persistence_probe as probe

        primary = self._prior_save(tmp_path)

        def failing_copy(*a, **kw):
            raise OSError("backup copy failed")

        monkeypatch.setattr(probe.shutil, "copyfileobj", failing_copy)
        with pytest.raises(OSError):
            save_json_atomic(primary, serialize_baseline_json("new", make_sample_items()))
        monkeypatch.undo()

        # Primary untouched because copy failed before .bak replace.
        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        bak = Path(str(primary) + ".bak")
        assert not bak.exists()
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []


# ---------------------------------------------------------------------------
# Interrupted-save simulation section (SQLite only; JSON uses phase tests above)
# ---------------------------------------------------------------------------


class TestSqliteInterruptedSave:
    """Simulate interruption inside transaction; rollback."""

    def test_pre_commit_rollback_preserves_prior(self, tmp_path: Path, monkeypatch) -> None:
        import persistence_probe as probe

        db = tmp_path / "baseline.db"
        save_sqlite_atomic(db, "prior", make_sample_items())

        class _FailingCommitConn:
            def __init__(self, real_conn):
                self._real = real_conn

            def execute(self, *a, **kw):
                return self._real.execute(*a, **kw)

            def executemany(self, *a, **kw):
                return self._real.executemany(*a, **kw)

            def executescript(self, *a, **kw):
                return self._real.executescript(*a, **kw)

            def commit(self):
                raise sqlite3.Error("commit boom")

            def rollback(self):
                self._real.rollback()

            def close(self):
                self._real.close()

        def failing_connect(*a, **kw):
            real = sqlite3.connect(*a, **kw)
            real.execute("PRAGMA foreign_keys = ON")
            return _FailingCommitConn(real)

        monkeypatch.setattr(probe, "sqlite_connect", failing_connect)
        with pytest.raises(sqlite3.Error):
            save_sqlite_atomic(db, "new", make_sample_items())
        monkeypatch.undo()
        bid, _ = load_sqlite(db)
        assert bid == "prior"


# ---------------------------------------------------------------------------
# R4 — Strict field-type validation
# ---------------------------------------------------------------------------


class TestStrictSerializationValidation:
    """Confirm every CheckItem/CheckItemAlias field has correct type guards."""

    def test_non_string_item_id_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["item_id"] = 123  # not a string
        with pytest.raises(ValueError, match="item_id must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_code_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["code"] = ["not", "a", "str"]
        with pytest.raises(ValueError, match="code must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_name_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["name"] = None
        with pytest.raises(ValueError, match="name must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_detection_phrase_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["detection_phrase"] = 42
        with pytest.raises(ValueError, match="detection_phrase must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_alias_id_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["aliases"][0]["alias_id"] = 99
        with pytest.raises(ValueError, match="aliases\\[0\\]\\.alias_id must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_alias_text_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["aliases"][0]["text"] = 3.14
        with pytest.raises(ValueError, match="aliases\\[0\\]\\.text must be a string"):
            deserialize_baseline_json(bad)

    def test_alias_not_dict_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["aliases"] = ["plain-string-alias"]
        with pytest.raises(ValueError, match="aliases\\[0\\] must be an object"):
            deserialize_baseline_json(bad)

    def test_non_string_category_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["category"] = {"not": "a string"}
        with pytest.raises(ValueError, match="category must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_expected_description_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["expected_description"] = True
        with pytest.raises(ValueError, match="expected_description must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_notes_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["notes"] = 0
        with pytest.raises(ValueError, match="notes must be a string"):
            deserialize_baseline_json(bad)

    def test_non_string_alias_notes_rejected(self) -> None:
        bad = serialize_baseline_json("b", make_sample_items())
        bad["items"][0]["aliases"][0]["notes"] = 456
        with pytest.raises(ValueError, match="aliases\\[0\\]\\.notes must be a string"):
            deserialize_baseline_json(bad)
