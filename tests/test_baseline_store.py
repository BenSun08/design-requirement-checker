"""Production baseline_store tests (Task 5, subtask T5.1).

All tests are hand-labelled expected outcomes written before the production
module was implemented. They exercise the validated persistence contract from
docs/technical-spikes.md. No test imports from ``tests/persistence_probe.py`` —
production behavior is tested independently.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from design_requirement_checker.baseline_store import (
    BaselineLoadSource,
    default_path,
    deserialize_baseline,
    load_baseline,
    save_baseline,
    serialize_baseline,
)
from design_requirement_checker.domain import CheckItem, CheckItemAlias


def _item(item_id: str = "", phrase: str = "检测短语") -> CheckItem:
    """Build a CheckItem with stable UUID-style IDs for deterministic tests."""
    actual_id = item_id or f"item-{uuid.uuid4().hex[:8]}"
    return CheckItem(
        item_id=actual_id,
        code=f"CODE-{actual_id}",
        name=f"功能-{actual_id}",
        detection_phrase=phrase,
        aliases=(
            CheckItemAlias(
                alias_id=f"alias-{actual_id}-a",
                text=f"别名-{actual_id}",
                notes="",
            ),
        ),
        category="测试",
        expected_description="期望描述",
        enabled=True,
        notes="备注",
    )


def _empty_alias_item() -> CheckItem:
    return CheckItem(
        item_id="item-empty-alias",
        code="EA",
        name="无别名项",
        detection_phrase="无别名检测短语",
        aliases=(),
        category="",
        expected_description="",
        enabled=True,
        notes="",
    )


def _disabled_item() -> CheckItem:
    return CheckItem(
        item_id="item-disabled",
        code="DIS",
        name="禁用项",
        detection_phrase="禁用检测短语",
        aliases=(),
        enabled=False,
    )


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------


class TestSerializationRoundTrip:
    def test_round_trip_all_checkitem_fields(self) -> None:
        items = (_item("item-rt-01"),)
        data = serialize_baseline("b1", items)
        bid, loaded = deserialize_baseline(data)
        assert bid == "b1"
        assert loaded == items

    def test_round_trip_alias_ids_and_notes(self) -> None:
        alias = CheckItemAlias(alias_id="alias-xyz", text="替代短语", notes="别名备注")
        item = CheckItem(
            item_id="item-alias-notes",
            code="A",
            name="别名项",
            detection_phrase="主短语",
            aliases=(alias,),
        )
        data = serialize_baseline("b", (item,))
        _, loaded = deserialize_baseline(data)
        assert loaded[0].aliases[0].alias_id == "alias-xyz"
        assert loaded[0].aliases[0].text == "替代短语"
        assert loaded[0].aliases[0].notes == "别名备注"

    def test_chinese_utf8_preserved(self, tmp_path: Path) -> None:
        items = (
            CheckItem(
                item_id="item-cn",
                code="CN",
                name="开关门延时",
                detection_phrase="2门控制增加开关门延时",
                category="门禁",
                expected_description="2门控制增加开关门延时2s功能",
                aliases=(CheckItemAlias(alias_id="a1", text="延时", notes="短名称"),),
            ),
        )
        primary = tmp_path / "baseline.json"
        save_baseline(primary, items, "b-cn")
        raw = primary.read_bytes()
        assert b"\xe5\xbc\x80" in raw  # 开
        assert b"\\u" not in raw  # ensure_ascii=False

    def test_enabled_false_round_trips(self, tmp_path: Path) -> None:
        items = (_disabled_item(),)
        primary = tmp_path / "baseline.json"
        save_baseline(primary, items, "b")
        loaded, _, _ = load_baseline(primary)
        assert loaded[0].enabled is False

    def test_empty_expected_description_round_trips(self, tmp_path: Path) -> None:
        items = (_empty_alias_item(),)
        primary = tmp_path / "baseline.json"
        save_baseline(primary, items, "b")
        loaded, _, _ = load_baseline(primary)
        assert loaded[0].expected_description == ""

    def test_schema_version_equals_1(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item(),), "b")
        data = json.loads(primary.read_text(encoding="utf-8"))
        assert data["schemaVersion"] == 1

    def test_stable_ids_preserved(self, tmp_path: Path) -> None:
        """ID generation never happens — IDs are only written/round-tripped."""
        items = (_item("item-stable-01"), _item("item-stable-02"))
        primary = tmp_path / "baseline.json"
        save_baseline(primary, items, "b")
        loaded, _, _ = load_baseline(primary)
        assert [i.item_id for i in loaded] == ["item-stable-01", "item-stable-02"]


# ---------------------------------------------------------------------------
# Strict validation
# ---------------------------------------------------------------------------


class TestStrictValidation:
    def test_missing_schemaVersion_rejected(self) -> None:
        data = serialize_baseline("b", (_item(),))
        del data["schemaVersion"]
        with pytest.raises(ValueError, match="schemaVersion"):
            deserialize_baseline(data)

    def test_wrong_schemaVersion_type_rejected(self) -> None:
        data = serialize_baseline("b", (_item(),))
        data["schemaVersion"] = "one"
        with pytest.raises(ValueError, match="schemaVersion"):
            deserialize_baseline(data)

    def test_unsupported_schemaVersion_rejected(self) -> None:
        data = serialize_baseline("b", (_item(),))
        data["schemaVersion"] = 999
        with pytest.raises(ValueError, match="unsupported schemaVersion"):
            deserialize_baseline(data)

    def test_non_string_item_id_rejected(self) -> None:
        data = serialize_baseline("b", (_item(),))
        data["items"][0]["item_id"] = 123
        with pytest.raises(ValueError, match="item_id must be a string"):
            deserialize_baseline(data)

    def test_non_boolean_enabled_rejected(self) -> None:
        data = serialize_baseline("b", (_item(),))
        data["items"][0]["enabled"] = "yes"
        with pytest.raises(ValueError, match="enabled must be a boolean"):
            deserialize_baseline(data)

    def test_non_list_aliases_rejected(self) -> None:
        data = serialize_baseline("b", (_item(),))
        data["items"][0]["aliases"] = "not-a-list"
        with pytest.raises(ValueError, match="aliases must be a list"):
            deserialize_baseline(data)

    def test_alias_not_dict_rejected(self) -> None:
        data = serialize_baseline("b", (_item(),))
        data["items"][0]["aliases"] = ["plain-string"]
        with pytest.raises(ValueError, match="aliases\\[0\\] must be an object"):
            deserialize_baseline(data)


# ---------------------------------------------------------------------------
# Save success paths
# ---------------------------------------------------------------------------


class TestSaveSuccessPaths:
    def test_first_save_creates_no_backup(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item(),), "first")
        assert primary.exists()
        assert not Path(str(primary) + ".bak").exists()
        data = json.loads(primary.read_text(encoding="utf-8"))
        assert data["baselineId"] == "first"

    def test_second_save_creates_backup(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("v1"),), "v1")
        save_baseline(primary, (_item("v2"),), "v2")
        assert primary.exists()
        assert Path(str(primary) + ".bak").exists()
        primary_data = json.loads(primary.read_text(encoding="utf-8"))
        bak_data = json.loads(Path(str(primary) + ".bak").read_text(encoding="utf-8"))
        assert primary_data["baselineId"] == "v2"
        assert bak_data["baselineId"] == "v1"

    def test_v1_to_v2_to_v3_primary_v3_backup_v2(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("a"),), "v1")
        save_baseline(primary, (_item("b"),), "v2")
        save_baseline(primary, (_item("c"),), "v3")
        primary_data = json.loads(primary.read_text(encoding="utf-8"))
        bak_data = json.loads(Path(str(primary) + ".bak").read_text(encoding="utf-8"))
        assert primary_data["baselineId"] == "v3"
        assert bak_data["baselineId"] == "v2"

    def test_no_temp_leak_after_save(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item(),), "b")
        for entry in tmp_path.iterdir():
            if entry.name.startswith(".tmp_"):
                pytest.fail(f"temp file leaked: {entry}")

    def test_parent_directory_created(self, tmp_path: Path) -> None:
        primary = tmp_path / "subdir" / "nested" / "baseline.json"
        save_baseline(primary, (_item(),), "b")
        assert primary.exists()


# ---------------------------------------------------------------------------
# Load / recovery contract
# ---------------------------------------------------------------------------


class TestLoadRecovery:
    def test_no_baseline_first_launch(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        items, bid, source = load_baseline(primary)
        assert source is BaselineLoadSource.NO_BASELINE
        assert items == ()
        assert bid == ""

    def test_primary_load(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("p1"),), "primary-id")
        items, bid, source = load_baseline(primary)
        assert source is BaselineLoadSource.PRIMARY
        assert bid == "primary-id"
        assert items[0].item_id == "p1"

    def test_backup_recovery_primary_corrupt(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("bak-valid"),), "b1")
        save_baseline(primary, (_item("corrupt-primary"),), "b2")
        # primary now has b2, .bak has b1. Corrupt primary.
        primary.write_bytes(b"{not valid json!!!")
        items, bid, source = load_baseline(primary)
        assert source is BaselineLoadSource.BACKUP
        assert bid == "b1"
        assert items[0].item_id == "bak-valid"

    def test_backup_recovery_primary_missing(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("bak-p"),), "b1")
        save_baseline(primary, (_item("new-p"),), "b2")
        primary.unlink()
        items, bid, source = load_baseline(primary)
        assert source is BaselineLoadSource.BACKUP
        assert bid == "b1"

    def test_both_corrupt_raises(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        primary.write_text("garbage", encoding="utf-8")
        Path(str(primary) + ".bak").write_text("also garbage", encoding="utf-8")
        with pytest.raises(ValueError, match="both primary"):
            load_baseline(primary)

    def test_unsupported_schema_primary_not_fallback(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        Path(str(primary) + ".bak").write_text(
            json.dumps(
                {
                    "schemaVersion": 999,
                    "baselineId": "bad",
                    "items": [],
                }
            ),
            encoding="utf-8",
        )
        primary.write_bytes(b"not json")
        with pytest.raises(ValueError, match="both primary"):
            load_baseline(primary)


# ---------------------------------------------------------------------------
# Phase-specific save failure injection
# ---------------------------------------------------------------------------


def _make_phase_failer(target_phase: int):
    def _fail(src: str, dst: str, *, phase: int) -> None:
        if phase == target_phase:
            raise OSError(f"phase-{phase} replace failed")
        import os as _os

        _os.replace(src, dst)

    return _fail


class TestPhaseSpecificFailureInjection:
    def _prior_save(self, tmp_path: Path) -> Path:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("prior"),), "prior")
        return primary

    def test_temp_write_failure_preserves_primary(self, tmp_path: Path, monkeypatch) -> None:
        import design_requirement_checker.baseline_store as bs

        primary = self._prior_save(tmp_path)

        def failing_dump(*a, **kw):
            raise OSError("disk full during json.dump")

        monkeypatch.setattr(bs.json, "dump", failing_dump)
        with pytest.raises(OSError):
            save_baseline(primary, (_item("new"),), "new")
        monkeypatch.undo()

        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_temp_fsync_failure_preserves_primary(self, tmp_path: Path, monkeypatch) -> None:
        import design_requirement_checker.baseline_store as bs

        primary = self._prior_save(tmp_path)

        def failing_fsync(*a, **kw):
            raise OSError("fsync failed")

        monkeypatch.setattr(bs.os, "fsync", failing_fsync)
        with pytest.raises(OSError):
            save_baseline(primary, (_item("new"),), "new")
        monkeypatch.undo()

        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_backup_copy_failure_preserves_primary(self, tmp_path: Path, monkeypatch) -> None:
        import design_requirement_checker.baseline_store as bs

        primary = self._prior_save(tmp_path)

        def failing_copy(*a, **kw):
            raise OSError("backup copy failed")

        monkeypatch.setattr(bs.shutil, "copyfileobj", failing_copy)
        with pytest.raises(OSError):
            save_baseline(primary, (_item("new"),), "new")
        monkeypatch.undo()

        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        bak = Path(str(primary) + ".bak")
        assert not bak.exists()
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_backup_replace_failure_preserves_primary(self, tmp_path: Path) -> None:
        primary = self._prior_save(tmp_path)
        with patch(
            "design_requirement_checker.baseline_store._phase_replace",
            _make_phase_failer(1),
        ):
            with pytest.raises(OSError, match="phase-1"):
                save_baseline(primary, (_item("new"),), "new")

        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []

    def test_final_primary_replace_failure_preserves_primary(self, tmp_path: Path) -> None:
        primary = self._prior_save(tmp_path)
        with patch(
            "design_requirement_checker.baseline_store._phase_replace",
            _make_phase_failer(2),
        ):
            with pytest.raises(OSError, match="phase-2"):
                save_baseline(primary, (_item("new"),), "new")

        # PRIMARY MUST still hold the old baseline.
        assert json.loads(primary.read_text(encoding="utf-8"))["baselineId"] == "prior"
        # .bak was prepared in phase 1 (succeeded), so it holds the old primary.
        bak = Path(str(primary) + ".bak")
        assert bak.exists()
        assert json.loads(bak.read_text(encoding="utf-8"))["baselineId"] == "prior"
        temps = [e for e in tmp_path.iterdir() if e.name.startswith(".tmp_")]
        assert temps == []


# ---------------------------------------------------------------------------
# Corrupt-primary + valid-backup + subsequent-save
# ---------------------------------------------------------------------------


class TestCorruptPrimarySubsequentSave:
    """Critical regression: when primary is corrupt but .bak is valid, a later
    save must NOT copy corrupt primary into .bak (destroying the recoverable
    backup). The valid .bak must remain intact unless the new save succeeds
    fully."""

    def test_corrupt_primary_save_does_not_destroy_valid_backup(self, tmp_path: Path) -> None:
        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("bak-item"),), "bak-bid")
        # Do a second save so .bak gets created holding save-1's data.
        save_baseline(primary, (_item("primary-item"),), "primary-bid")
        # Now: primary=save2 data ("primary-bid"), .bak=save1 data ("bak-bid")
        # Corrupt primary.
        primary.write_bytes(b"{corrupt garbage!!!")

        # Confirm backup recovery gives save1's data (the .bak content).
        items, bid, source = load_baseline(primary)
        assert source is BaselineLoadSource.BACKUP
        assert bid == "bak-bid"
        assert items[0].item_id == "bak-item"

        # Now perform a save with new data. Since primary is corrupt, the
        # backup-prep step is SKIPPED — we NEVER copy corrupt primary into .bak.
        # Then primary is replaced atomically.
        save_baseline(primary, (_item("new-save-item"),), "new-save-bid")

        # primary is now the new data.
        new_items, new_bid, new_source = load_baseline(primary)
        assert new_source is BaselineLoadSource.PRIMARY
        assert new_bid == "new-save-bid"
        assert new_items[0].item_id == "new-save-item"

        # .bak still holds save1's data ("bak-bid") — the valid backup we
        # recovered from, never destroyed by the corrupt-primary save.
        bak = Path(str(primary) + ".bak")
        assert bak.exists()
        bak_data = json.loads(bak.read_text(encoding="utf-8"))
        assert bak_data["baselineId"] == "bak-bid"

    def test_corrupt_primary_save_failure_preserves_valid_backup(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """If save fails while primary is corrupt (backup-prep skipped), the
        valid .bak is still recoverable and primary remains untouched."""
        import design_requirement_checker.baseline_store as bs

        primary = tmp_path / "baseline.json"
        save_baseline(primary, (_item("bak-item"),), "bak-bid")
        save_baseline(primary, (_item("primary-item"),), "primary-bid")
        primary.write_bytes(b"corrupt!!!")

        def failing_dump(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr(bs.json, "dump", failing_dump)
        with pytest.raises(OSError):
            save_baseline(primary, (_item("new"),), "new")

        # Primary still corrupt, valid backup (save1) still recoverable.
        items, bid, source = load_baseline(primary)
        assert source is BaselineLoadSource.BACKUP
        assert bid == "bak-bid"
        assert items[0].item_id == "bak-item"


# ---------------------------------------------------------------------------
# Permission / access failures
# ---------------------------------------------------------------------------


class TestPermissionDenial:
    def test_write_denial_is_explicit(self, tmp_path: Path, monkeypatch) -> None:
        import design_requirement_checker.baseline_store as bs

        monkeypatch.setattr(
            bs.tempfile,
            "mkstemp",
            lambda **kw: (_ for _ in ()).throw(PermissionError("denied")),
        )
        with pytest.raises(PermissionError):
            save_baseline(tmp_path / "baseline.json", (_item(),), "b")


# ---------------------------------------------------------------------------
# Default path
# ---------------------------------------------------------------------------


class TestDefaultPath:
    def test_default_path_returns_path(self) -> None:
        path = default_path()
        assert isinstance(path, Path)
        assert path.name == "baseline.json"
