# Design Requirement Checker — Demo Runbook

[简体中文版](../docs-zh/demo-runbook.md)

A short practical guide for running the v0.1 internal demo.

## 1. Start the application

For the packaged Windows artifact:

1. Extract the **whole** `DesignRequirementChecker/` directory (the `.exe`
   alone will not run — the adjacent runtime files are part of the
   application).
2. Launch `DesignRequirementChecker.exe`.

No Python installation is required or intended for demo users.

For source runs (development machines): `python -m design_requirement_checker`.

## 2. Configure the checklist

Click **检查项管理** → **新增检查项**, then fill in:

- `功能名称` (name) — required
- `编号` (code) — required, must be unique
- `检测短语` (detection phrase) — required
- optionally `期望描述` (expected description), `类别` (category),
  `备注` (notes) and `别名` (aliases, one per line)

Note: **功能名称 ≠ 检测短语**. The name is the human label; the detection
phrase is what the matcher actually searches for in the document. Verification
never matches on the name alone.

Use **编辑**, **切换启用/禁用** and **删除** (with confirmation) to maintain
items; IDs stay stable across edits and restarts. Click **保存基准** to
persist. Duplicate codes are rejected; duplicate names and overlapping
detection phrases are flagged for confirmation.

## 3. Import a DOCX

Click **导入 DOCX** and select a `.docx` file through the file dialog.

Current production import uses file selection only — drag/drop is not
implemented (deferred usability enhancement). Import runs in the background;
a LIMITED coverage notice appears if the document contains structures outside
the checked scope.

## 4. Run verification

Click **开始核查**. **取消核查** requests cooperative cancellation; a
cancelled run shows no result set (cancelled ≠ completed).

Result statuses:

- **已配置** (CONFIGURED) — qualifying evidence found and active
- **未配置** (MISSING) — no matching evidence found *within the checked
  scope* (does not prove physical absence)
- **已划除** (STRUCK_OUT) — all qualifying evidence fully struck
- **待人工核查** (UNRESOLVED) — partial/unknown strike, conflicting or
  ambiguous evidence; needs a human decision

**描述有差异** (description DIFFERENT) is orthogonal: an item can be
已配置 *and* have a description difference. It never turns a CONFIGURED item
into MISSING.

## 5. Review evidence

- Filter with 全部 / 已配置 / 未配置 / 已划除 / 待人工核查 / 仅异常, or search
  by code/name/category/expected/description. Filters never recompute
  verification.
- The detail pane shows expected vs actual text, match method, reasons,
  **every evidence occurrence** (selector) and the reconstructed source
  context (previous/current/next block with the requirement span
  highlighted).
- A persistent "检查范围受限" notice marks LIMITED-coverage runs.

## 6. Persistence

The checklist baseline is saved automatically as one local JSON file at
`QStandardPaths.AppDataLocation / baseline.json` (plus a `baseline.json.bak`
backup used for recovery). The application does not display the resolved
absolute path; on Windows this location is under the per-user application
data directory, not beside the executable.

Keep these concepts separate:

- the **application directory** (the extracted `DesignRequirementChecker/`
  folder) can be replaced by a newer build at any time;
- the **user baseline directory** (AppDataLocation) holds your checklist and
  survives application replacement.

At startup, backup-recovered, corrupt and unsupported-schema baselines are
shown as explicit, distinct banners.

## 7. Demo limitations

Formal historical measurement (Task 6), clean-machine / no-admin / offline
deployment validation (Task 7 / S3), DPI / Chinese-input / long-description
validation matrices and report export are **deferred** for this milestone.
See [demo-readiness.md](demo-readiness.md).
