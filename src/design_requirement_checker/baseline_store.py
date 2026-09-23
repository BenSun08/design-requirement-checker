"""One local baseline's load, save and recovery.

Production JSON persistence following the validated contract from
docs/constitution.md §9 (persistence decision recorded in docs/plan.md §4).
This module owns serialization, strict deserialize validation, the
two-temp-file atomic-save algorithm, and backup recovery. It has no Qt
imports (``default_path`` does a lazy QStandardPaths lookup at call time
with a safe fallback for non-Qt contexts) and no imports from ``tests/``.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Any

from design_requirement_checker.domain import CheckItem, CheckItemAlias

# ---------------------------------------------------------------------------
# Schema identity
# ---------------------------------------------------------------------------

#: Current validated persistence schema version. Bump only after a schema
#: change and an explicit migration contract is approved.
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Load source enum
# ---------------------------------------------------------------------------


class BaselineLoadSource(Enum):
    """Which file supplied the loaded baseline.

    ``NO_BASELINE`` means neither primary nor backup existed — normal first
    launch, not an error. ``PRIMARY`` and ``BACKUP`` carry no reliability
    claim; they only say which path produced the data.
    """

    NO_BASELINE = "no-baseline"
    PRIMARY = "primary"
    BACKUP = "backup"


class UnsupportedBaselineSchemaError(ValueError):
    """Raised when a persisted baseline has a schemaVersion we do not understand.

    Distinct from generic corrupt/invalid structure. A file with the wrong
    schema version must NOT trigger backup recovery — it signals a
    forward-compatibility or downgrade scenario that needs explicit user
    handling, not silent side-stepping.
    """


# ---------------------------------------------------------------------------
# Strict serialization helpers
# ---------------------------------------------------------------------------


def _item_to_dict(item: CheckItem) -> dict[str, Any]:
    """Convert one CheckItem to a JSON-compatible dict.

    Alias identity is preserved (each CheckItemAlias keeps its alias_id).
    """
    return {
        "item_id": item.item_id,
        "code": item.code,
        "name": item.name,
        "detection_phrase": item.detection_phrase,
        "category": item.category,
        "expected_description": item.expected_description,
        "enabled": item.enabled,
        "notes": item.notes,
        "aliases": [
            {"alias_id": a.alias_id, "text": a.text, "notes": a.notes} for a in item.aliases
        ],
    }


def _dict_to_item(data: dict[str, Any]) -> CheckItem:
    """Reconstruct one CheckItem from a JSON-like dict.

    Raises ``ValueError`` for every type/structure defect — never silently
    coerces corrupt data.
    """
    if not isinstance(data, dict):
        raise ValueError("item must be a JSON object")

    for field in (
        "item_id",
        "code",
        "name",
        "detection_phrase",
        "category",
        "expected_description",
        "notes",
    ):
        if field in data and not isinstance(data[field], str):
            raise ValueError(f"{field} must be a string")

    if "enabled" in data and not isinstance(data["enabled"], bool):
        raise ValueError("enabled must be a boolean")

    aliases_raw = data.get("aliases", ())
    if not isinstance(aliases_raw, (list, tuple)):
        raise ValueError("aliases must be a list")
    aliases_list: list[CheckItemAlias] = []
    for idx, a in enumerate(aliases_raw):
        if not isinstance(a, dict):
            raise ValueError(f"aliases[{idx}] must be an object")
        for field in ("alias_id", "text", "notes"):
            if field in a and not isinstance(a[field], str):
                raise ValueError(f"aliases[{idx}].{field} must be a string")
        aliases_list.append(
            CheckItemAlias(
                alias_id=a["alias_id"],
                text=a["text"],
                notes=a.get("notes", ""),
            )
        )
    aliases = tuple(aliases_list)

    return CheckItem(
        item_id=data["item_id"],
        code=data["code"],
        name=data["name"],
        detection_phrase=data["detection_phrase"],
        aliases=aliases,
        category=data.get("category", ""),
        expected_description=data.get("expected_description", ""),
        enabled=data.get("enabled", True),
        notes=data.get("notes", ""),
    )


def serialize_baseline(baseline_id: str, items: Sequence[CheckItem]) -> dict[str, Any]:
    """Produce the top-level JSON document shape."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "baselineId": baseline_id,
        "items": [_item_to_dict(i) for i in items],
    }


def deserialize_baseline(data: dict[str, Any]) -> tuple[str, tuple[CheckItem, ...]]:
    """Reconstruct baseline_id and CheckItems from a top-level dict.

    Raises ``ValueError`` for every structural defect — never silently coerces
    corrupt data.
    """
    if not isinstance(data, dict):
        raise ValueError("baseline must be a JSON object")

    sv = data.get("schemaVersion")
    if sv is None:
        raise ValueError("missing schemaVersion")
    if not isinstance(sv, int):
        raise ValueError("schemaVersion must be an integer")
    if sv != SCHEMA_VERSION:
        raise UnsupportedBaselineSchemaError(
            f"unsupported schemaVersion: {sv} (expected {SCHEMA_VERSION})"
        )

    bid = data.get("baselineId")
    if not isinstance(bid, str) or not bid:
        raise ValueError("baselineId must be a non-empty string")

    items_raw = data.get("items")
    if not isinstance(items_raw, list):
        raise ValueError("items must be a list")

    items: list[CheckItem] = []
    for idx, raw in enumerate(items_raw):
        try:
            item = _dict_to_item(raw)
        except KeyError as exc:
            raise ValueError(f"item[{idx}] missing field: {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"item[{idx}] invalid: {exc}") from exc
        items.append(item)
    return bid, tuple(items)


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------


def _validate_primary_for_backup(primary_path: Path) -> bool:
    """Return True only when ``primary_path`` exists AND parses as valid JSON.

    A corrupt-but-existing primary must NOT become the .bak source on the next
    save — the existing valid .bak would be overwritten by garbage.

    An existing primary with an *unsupported* schemaVersion is neither valid
    nor corrupt: the error propagates so :func:`save_baseline` aborts before
    touching primary or backup. Overwriting a file written by a newer
    application version is a compatibility violation, not recovery.
    """
    if not primary_path.exists():
        return False
    try:
        raw = primary_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        deserialize_baseline(parsed)
        return True
    except UnsupportedBaselineSchemaError:
        raise
    except (OSError, json.JSONDecodeError, ValueError):
        return False


def _phase_replace(src: str, dst: str, *, phase: int) -> None:
    """``os.replace`` wrapper tagged with a phase number for test injection.

    ``phase=1`` is the .bak replace; ``phase=2`` is the final primary replace.
    Production callers do not care about the tag — it lets tests monkeypatch
    this one function to inject failures at exactly one phase without
    blanket-patching ``os.replace`` everywhere.
    """
    os.replace(src, dst)


def save_baseline(
    primary_path: Path,
    items: Sequence[CheckItem],
    baseline_id: str,
) -> None:
    """Atomically save items to ``primary_path``.

    CORRECTED two-temp-file contract (never moves primary before installing
    the new primary):

      1. Create parent directory.
      2. Write new baseline to temp-new in same directory; flush + fsync.
      3. If existing primary is VALID (not corrupt):
           a. copy primary → temp-backup (copy, never move)
           b. flush + fsync temp-backup
           c. ``os.replace`` temp-backup → ``primary_path + ".bak"``
      4. ``os.replace`` temp-new → primary_path

    Critical edge case: when primary is corrupt/missing but ``.bak`` holds a
    valid recovered baseline, step 3 is SKIPPED — we never copy corrupt data
    into ``.bak`` because that would destroy the recoverable backup. Step 4
    still installs the new primary atomically, so the valid ``.bak`` remains
    recoverable if step 4 fails.

    Raises:
        OSError: on mkdir, write, fsync, or replace failures.
        UnsupportedBaselineSchemaError: when the existing primary was written
            with a schemaVersion this build does not understand. Primary and
            backup are left byte-identical — a direct production caller
            cannot silently overwrite unsupported-schema data.
        ValueError: on validation defects in the serialized data shape,
            including an empty ``baseline_id`` — the persistence layer will
            never write an empty identity even if higher layers regress.
    """
    if not baseline_id or not baseline_id.strip():
        raise ValueError("baseline_id must be a non-empty string (not whitespace-only)")

    primary_path = Path(primary_path)
    dir_path = primary_path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    data = serialize_baseline(baseline_id, items)

    temp_new_path: str | None = None
    temp_bak_path: str | None = None
    try:
        # --- Phase 1: write new data ---
        fd, temp_new_path = tempfile.mkstemp(prefix=".tmp_new_", suffix=".json", dir=str(dir_path))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())

        # --- Phase 2: backup preparation (only if primary is VALID) ---
        if _validate_primary_for_backup(primary_path):
            fd2, temp_bak_path = tempfile.mkstemp(
                prefix=".tmp_bak_", suffix=".json", dir=str(dir_path)
            )
            os.close(fd2)
            with open(primary_path, "rb") as src_fh:
                with open(temp_bak_path, "wb") as dst_fh:
                    shutil.copyfileobj(src_fh, dst_fh)
                    dst_fh.flush()
                    os.fsync(dst_fh.fileno())
            _phase_replace(temp_bak_path, str(primary_path) + ".bak", phase=1)

        # --- Phase 3: install new primary ---
        _phase_replace(temp_new_path, str(primary_path), phase=2)

    except Exception:
        try:
            if temp_new_path is not None and os.path.exists(temp_new_path):
                os.unlink(temp_new_path)
        except OSError:
            pass
        try:
            if temp_bak_path is not None and os.path.exists(temp_bak_path):
                os.unlink(temp_bak_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------


def _try_load_file(path: Path) -> dict[str, Any] | None:
    """Return parsed JSON dict if ``path`` exists AND valid; else None.

    Lets :class:`UnsupportedBaselineSchemaError` bubble so the caller can
    distinguish a forward-compatibility/downgrade scenario from mundane
    corrupt/missing files.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        parsed: dict[str, Any] = json.loads(raw)
        deserialize_baseline(parsed)
        return parsed
    except UnsupportedBaselineSchemaError:
        raise
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def load_baseline(
    primary_path: Path,
) -> tuple[tuple[CheckItem, ...], str, BaselineLoadSource]:
    """Load baseline from ``primary_path`` with explicit recovery policy.

    Returns:
        ``(items, baseline_id, source)``

    Behavior:
      - Both missing → ``source=NO_BASELINE``, empty items, empty baseline_id.
      - Primary valid → ``source=PRIMARY``.
      - Primary missing/corrupt + backup valid → ``source=BACKUP``.
      - Primary exists with unsupported schemaVersion → raises
        :class:`UnsupportedBaselineSchemaError` (never silently falls back
        to backup — a forward-compatibility / downgrade scenario must be
        surfaced explicitly).
      - Primary corrupt + backup exists with unsupported schemaVersion →
        raises :class:`UnsupportedBaselineSchemaError` (no silent fallback
        to primary).
      - Both exist but neither is loadable → raises ``ValueError`` (generic
        corrupt/missing case, distinct from the compatibility error above).

    Never silently rewrites corrupt files.
    """
    primary_path = Path(primary_path)
    backup_path = Path(str(primary_path) + ".bak")

    primary_data = _try_load_file(primary_path)
    if primary_data is not None:
        bid, items = deserialize_baseline(primary_data)
        return items, bid, BaselineLoadSource.PRIMARY

    backup_data = _try_load_file(backup_path)
    if backup_data is not None:
        bid, items = deserialize_baseline(backup_data)
        return items, bid, BaselineLoadSource.BACKUP

    # Neither file exists at all → normal first-launch state.
    if not primary_path.exists() and not backup_path.exists():
        return (), "", BaselineLoadSource.NO_BASELINE

    # Both exist but neither is valid.
    raise ValueError(
        f"both primary ({primary_path}) and backup ({backup_path}) are invalid or missing"
    )


# ---------------------------------------------------------------------------
# Default user-writable path
# ---------------------------------------------------------------------------


def default_path() -> Path:
    """Return the production baseline path: AppDataLocation / baseline.json.

    Does a lazy QStandardPaths lookup (requires a running QApplication) with a
    safe fallback to ``~/.design-requirement-checker/baseline.json`` for non-Qt
    contexts such as unit tests that have not set Qt test mode. Tests should
    prefer injecting an explicit temp path instead of relying on either the
    Qt path or the fallback.
    """
    try:
        from PySide6.QtCore import QStandardPaths  # noqa: PLC0415

        loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)  # type: ignore[attr-defined]
        if loc:
            return Path(loc) / "baseline.json"
    except Exception:
        pass
    return Path.home() / ".design-requirement-checker" / "baseline.json"
