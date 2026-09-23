"""Isolated spike helpers for baseline persistence validation.

This is **not production code**. The probe exercises two candidate local
persistence formats (JSON file, stdlib SQLite) against the confirmed
CheckItem domain model so a bounded engineering decision can be recorded
before Task 5 (baseline management and persistence) is authorized.

All results are deterministic and replayable. See docs/plan.md §4
for the recorded persistence decision.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3

# Import CheckItem and CheckItemAlias only — do not touch production source
# beyond reading existing value models. This spike does not modify src/.
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from design_requirement_checker.domain import CheckItem, CheckItemAlias  # noqa: E402

# ---------------------------------------------------------------------------
# Logical data contract — shared by both candidates
# ---------------------------------------------------------------------------

#: Current validated schema version for persistence.
#: Bump if the persisted shape changes after this spike.
SCHEMA_VERSION = 1


def item_to_serializable(item: CheckItem) -> dict:
    """Convert one CheckItem to a JSON-compatible dict.

    Preserves alias identity (each CheckItemAlias keeps its alias_id).
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


def serializable_to_item(data: dict) -> CheckItem:
    """Reconstruct one CheckItem from a JSON-like dict.

    Raises ValueError for every type/structure defect. No silent coercion.
    """
    if not isinstance(data, dict):
        raise ValueError("item must be a JSON object")

    # Strict type validation for every CheckItem field.
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

    # enabled must be an actual JSON boolean, not an arbitrary truthy value.
    if "enabled" in data and not isinstance(data["enabled"], bool):
        raise ValueError("enabled must be a boolean")

    # aliases must be a list; each alias must be a dict with correct types.
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


# ---------------------------------------------------------------------------
# JSON candidate
# ---------------------------------------------------------------------------


def serialize_baseline_json(baseline_id: str, items: list[CheckItem]) -> dict:
    """Produce the top-level JSON document shape.

    Intentionally minimal: schemaVersion + baselineId + items[].
    """
    return {
        "schemaVersion": SCHEMA_VERSION,
        "baselineId": baseline_id,
        "items": [item_to_serializable(i) for i in items],
    }


def deserialize_baseline_json(data: dict) -> tuple[str, list[CheckItem]]:
    """Reconstruct baseline_id and CheckItems from a top-level dict.

    Raises ValueError for every structural defect — never silently coerces
    corrupt data.
    """
    if not isinstance(data, dict):
        raise ValueError("baseline must be a JSON object")
    # Schema identification
    sv = data.get("schemaVersion")
    if sv is None:
        raise ValueError("missing schemaVersion")
    if not isinstance(sv, int):
        raise ValueError("schemaVersion must be an integer")
    if sv != SCHEMA_VERSION:
        raise ValueError(f"unsupported schemaVersion: {sv} (expected {SCHEMA_VERSION})")
    # baselineId
    bid = data.get("baselineId")
    if not isinstance(bid, str) or not bid:
        raise ValueError("baselineId must be a non-empty string")
    # items
    items_raw = data.get("items")
    if not isinstance(items_raw, list):
        raise ValueError("items must be a list")
    items: list[CheckItem] = []
    for idx, raw in enumerate(items_raw):
        try:
            item = serializable_to_item(raw)
        except KeyError as exc:
            raise ValueError(f"item[{idx}] missing field: {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"item[{idx}] invalid: {exc}") from exc
        items.append(item)
    return bid, items


def save_json_atomic(
    primary_path: Path,
    data: dict,
    *,
    make_backup: bool = True,
) -> None:
    """Atomically save data to primary_path.

    CORRECTED algorithm (two temp files; primary never touched until final step):

      1. Create parent directory if it doesn't exist.
      2. Write new baseline to temp-new in same directory.
      3. flush + fsync temp-new.
      4. If make_backup AND primary exists:
           a. copy primary → temp-backup (never move primary)
           b. flush + fsync temp-backup
           c. os.replace(temp-backup → .bak)
      5. os.replace(temp-new → primary)

    Safety invariant: **primary is never modified or moved until step 5.**
    Every failure path before step 5 leaves the prior primary untouched and
    loadable. Step 5 failure leaves primary untouched too (the old .bak was
    already updated in step 4c, but primary itself is unchanged).

    Phase numbering for testing: step 4c is PHASE_BACKUP_REPLACE, step 5 is
    PHASE_PRIMARY_REPLACE. The ``_phase_replace`` helper below lets tests
    inject failures at exactly one phase without blanket-monkeypatching
    ``os.replace``.
    """
    primary_path = Path(primary_path)
    dir_path = primary_path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    temp_new_path: str | None = None
    temp_bak_path: str | None = None
    try:
        # --- Phase 1: write new data ---
        fd, temp_new_path = tempfile.mkstemp(prefix=".tmp_new_", suffix=".json", dir=str(dir_path))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())

        # --- Phase 2: backup preparation ---
        if make_backup and primary_path.exists():
            fd2, temp_bak_path = tempfile.mkstemp(
                prefix=".tmp_bak_", suffix=".json", dir=str(dir_path)
            )
            os.close(fd2)  # will be overwritten by copy below
            # Copy primary → temp-backup, then fsync. Both input and output
            # handles must close before the next fsync open on temp-backup
            # (Windows may hold locks across handles).
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
            if temp_new_path is not None:
                os.unlink(temp_new_path)
        except OSError:
            pass
        try:
            if temp_bak_path is not None:
                os.unlink(temp_bak_path)
        except OSError:
            pass
        raise


# Phase-aware replace helper. Tests wrap this function via monkeypatch to
# inject failures at specific phases. phase=1 is the backup .bak replace,
# phase=2 is the final primary replace.
def _phase_replace(src: str, dst: str, *, phase: int) -> None:
    """os.replace wrapper with phase tag for deterministic failure injection."""
    os.replace(src, dst)


def load_json_safe(primary_path: Path) -> tuple[dict, str]:
    """Load with explicit recovery policy.

    Behavior:
      - primary valid → (primary, "primary")
      - primary missing/invalid + backup valid → (backup, "backup")
      - primary missing/invalid + backup missing/invalid → ValueError

    Never silently replaces corrupt primary data without the application seeing
    which source was used.
    """
    primary_path = Path(primary_path)
    backup_path = Path(str(primary_path) + ".bak")

    def try_load(p: Path) -> dict | None:
        try:
            raw = p.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            # Validate structural shape
            deserialize_baseline_json(parsed)
            return parsed
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    primary_data = try_load(primary_path)
    if primary_data is not None:
        return primary_data, "primary"
    backup_data = try_load(backup_path)
    if backup_data is not None:
        return backup_data, "backup"
    raise ValueError(
        f"both primary ({primary_path}) and backup ({backup_path}) are invalid or missing"
    )


# ---------------------------------------------------------------------------
# SQLite candidate
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS baseline_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    detection_phrase TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    expected_description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS aliases (
    alias_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    text TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);
"""


def sqlite_connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def sqlite_init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT OR REPLACE INTO baseline_meta (key, value) VALUES ('schemaVersion', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def save_sqlite_atomic(
    db_path: Path,
    baseline_id: str,
    items: list[CheckItem],
) -> None:
    """Transactionally save one baseline to SQLite.

    Opens the database, initializes the schema, and replaces items+aliases
    atomically inside one transaction. Rollback is explicit on any failure.
    """
    db_path = Path(db_path)
    conn = sqlite_connect(db_path)
    try:
        sqlite_init_schema(conn)
        # Check schema version
        row = conn.execute("SELECT value FROM baseline_meta WHERE key='schemaVersion'").fetchone()
        if row is None or int(row[0]) != SCHEMA_VERSION:
            raise ValueError(f"unsupported schemaVersion: {row}")
        # Transactional replace: DELETE first, INSERT new items.
        conn.execute("BEGIN")
        conn.execute("DELETE FROM aliases")
        conn.execute("DELETE FROM items")
        conn.execute(
            "INSERT OR REPLACE INTO baseline_meta (key, value) VALUES ('baselineId', ?)",
            (baseline_id,),
        )
        for item in items:
            conn.execute(
                """INSERT INTO items
                   (item_id, code, name, detection_phrase, category,
                    expected_description, enabled, notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    item.item_id,
                    item.code,
                    item.name,
                    item.detection_phrase,
                    item.category,
                    item.expected_description,
                    1 if item.enabled else 0,
                    item.notes,
                ),
            )
            for alias in item.aliases:
                conn.execute(
                    """INSERT INTO aliases (alias_id, item_id, text, notes)
                       VALUES (?,?,?,?)""",
                    (alias.alias_id, item.item_id, alias.text, alias.notes),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_sqlite(db_path: Path) -> tuple[str, list[CheckItem]]:
    """Load baseline_id and CheckItems from SQLite.

    Raises ValueError for invalid/unsupported schema or corrupt database.
    """
    db_path = Path(db_path)
    conn = sqlite_connect(db_path)
    try:
        sqlite_init_schema(conn)
        row = conn.execute("SELECT value FROM baseline_meta WHERE key='schemaVersion'").fetchone()
        if row is None:
            raise ValueError("missing schemaVersion")
        if int(row[0]) != SCHEMA_VERSION:
            raise ValueError(f"unsupported schemaVersion: {row[0]}")
        bid_row = conn.execute("SELECT value FROM baseline_meta WHERE key='baselineId'").fetchone()
        if bid_row is None or not bid_row[0]:
            raise ValueError("missing baselineId")
        baseline_id = bid_row[0]
        # Load items
        item_rows = conn.execute(
            """SELECT item_id, code, name, detection_phrase, category,
                      expected_description, enabled, notes
               FROM items"""
        ).fetchall()
        items: list[CheckItem] = []
        for row in item_rows:
            (iid, code, name, phrase, cat, exp_desc, enabled_int, notes) = row
            alias_rows = conn.execute(
                "SELECT alias_id, text, notes FROM aliases WHERE item_id=?",
                (iid,),
            ).fetchall()
            aliases = tuple(
                CheckItemAlias(alias_id=a[0], text=a[1], notes=a[2]) for a in alias_rows
            )
            items.append(
                CheckItem(
                    item_id=iid,
                    code=code,
                    name=name,
                    detection_phrase=phrase,
                    aliases=aliases,
                    category=cat,
                    expected_description=exp_desc,
                    enabled=bool(enabled_int),
                    notes=notes,
                )
            )
        return baseline_id, items
    finally:
        conn.close()


def sqlite_corrupt(db_path: Path) -> None:
    """Write garbage bytes into a SQLite file to simulate corruption.

    Used by tests to exercise corrupt-database failure paths deterministically.
    """
    Path(db_path).write_bytes(b"not a sqlite database; corrupt!")


# ---------------------------------------------------------------------------
# Qt QStandardPaths probe (run from inside a Qt test with qapp)
# ---------------------------------------------------------------------------


def probe_app_data_location() -> str:
    """Print and return Qt's AppDataLocation for the current identity.

    Run only from within a Qt-enabled test (``qapp`` fixture or similar).
    """
    from PySide6.QtCore import QStandardPaths

    loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    return loc


# ---------------------------------------------------------------------------
# Helpers for tests
# ---------------------------------------------------------------------------


def make_sample_items() -> list[CheckItem]:
    """A small representative CheckItem set with Chinese, aliases, and variety.

    All item_ids are stable UUID-style values so the round-trip test can assert
    identity preservation.
    """
    return [
        CheckItem(
            item_id="item-0001",
            code="DR-001",
            name="开关门延时",
            detection_phrase="2门控制增加开关门延时",
            category="门禁",
            expected_description="2门控制增加开关门延时2s功能",
            enabled=True,
            notes="主功能",
            aliases=(CheckItemAlias(alias_id="alias-0001a", text="开关门延时", notes="短名称"),),
        ),
        CheckItem(
            item_id="item-0002",
            code="DR-002",
            name="门锁状态反馈",
            detection_phrase="门锁状态反馈信号",
            category="门禁",
            expected_description="",
            enabled=True,
            notes="",
            aliases=(),
        ),
        CheckItem(
            item_id="item-0003",
            code="DR-003",
            name="未启用项",
            detection_phrase="不存在的短语",
            category="测试",
            expected_description="期望描述",
            enabled=False,
            notes="disabled 测试",
            aliases=(
                CheckItemAlias(alias_id="alias-0003a", text="别名一", notes=""),
                CheckItemAlias(alias_id="alias-0003b", text="别名二", notes="第二个别名"),
            ),
        ),
    ]
