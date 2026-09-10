# UX specification

[简体中文版](../docs-zh/ux-spec.md)

Status: updated to owner-confirmed behavior. Production UI: Python + PySide6 / Qt Widgets on Windows 10/11 x64, no administrator/installation privileges. Interface language: simplified Chinese; documentation: English. The unchanged local-browser prototype demonstrates the earlier mock scope only; the production requirements below extend it explicitly.

## Information architecture and primary flow

Two top-level destinations: 文档核查 and 检查项管理. Keep product/document identity visible; the historical prototype also keeps its mock-only disclosure visible. Import → loaded/ready → explicit run → results → exception selection → comparison and source. No wizard, dashboard home, login or navigation hierarchy. One locally maintained baseline; no customer/order template selector.

Use a compact horizontal title bar, document toolbar, summary/filter strip, and a split workspace. Left: approximately 40% width, dense rows with code/name/status and difference hint. Right: selected requirement, status and match method, expected/actual comparison, evidence explanation and original context. A narrow footer explains result scope. At smaller widths panes stack; desktop remains the intended usage scene.

## Historical prototype states

- Empty: clear DOCX drop/select target, explanation of local operation, separate “使用示例文档” action.
- Loaded: selected filename and “开始模拟核查”; no results until run. Selected-file bytes are never parsed in the prototype.
- Loading: short simulated progress with disabled run button; do not suggest real parsing. Production requires cancel/progress for long operations.
- Complete: counts for the full baseline, filters, search, selection and detail. Exceptions sort first in the mock: missing, struck-out, changed, ordinary configured. Default All preserves context; an “仅异常” shortcut includes the first three groups.
- Unsupported selection: inline alert names allowed `.docx`; selection of multiple files is rejected. File extension is only a prototype input gate, not production format validation.
- No search/filter results: explicit empty result view and clear-filters action; no stale detail.
- Baseline edited: results cleared and rerun required. Browser refresh resets session edits, visibly disclosed.
- Production parse failure: error with recovery/reselect; never all-missing. Protected/malformed/oversized content is specified but not simulated as a real parser outcome.

## Production result and detail behavior

Summary counts remain stable while filtering. All/configured/missing/struck-out/unresolved (待人工核查) plus exception shortcut; search code/name/category/expected text. Missing and struck-out use distinct words and symbols, not color alone. Selection highlight must not resemble engineering approval.

Detail shows canonical name/category/code, expected requirement, actual text, match method (with scope of what matched), optional separately labelled score, difference, and source. A configured-but-different item keeps CONFIGURED and adds 描述有差异. No “passed” language. `2s → 3s` appears explicitly alongside both full descriptions. Production must show a basic supported text comparison with an explicit NOT_COMPARED state when uncertain; enhanced diff remains V0.2. The browser diff is a fixed token replacement, not a generic engine.

Missing detail says no matching evidence in the checked document scope and gives no fabricated document location. Struck-out detail renders actual text using a strike line and a status label; expected text remains intact. Original context shows previous/current/next blocks with table coordinates. Preview is a reconstructed excerpt, not a Word-page rendering; use one-based coordinates. For repeated evidence, list all occurrences with selectable source context. Active/deleted coexistence, partial/unknown strike and contradictory active parameters display 待人工核查 with explicit reasons and no CheckStatus. Matching normal occurrences can remain 已配置. The first source occurrence is only the initial display selection, not authoritative evidence.

## Checklist management

Compact table: code/name/category/expected description/enabled state/actions. Add/edit dialog includes code, name, detection phrase, category, expected description, aliases (one per line), notes, enabled toggle. Required code/name/detectionPhrase and unique code enforced; blank expected description allowed with explanation. Similar names/aliases need production overlap warning; prototype prevents exact duplicate names. Disable reversible; deletion asks confirmation. Save closes dialog, returns focus and invalidates results. Cancel/Escape discards edits. Production changes persist locally for the current Windows user; the browser prototype remains session-only and must retain its disclosure. Show 检测短语 as a field separate from 功能名称; aliases are explicit alternative phrases. Do not prefill an inferred phrase as though approved.

## Keyboard and mouse

Native buttons, labelled fields, visible focus; Tab/Shift+Tab reach all actions. Dialog traps focus and Escape closes. Arrow Up/Down moves between visible result rows; Enter activates a focused row. Ctrl+F (Cmd+F on Mac preview) focuses result search while results are shown; do not capture it during dialog editing. File drop and select share validation. Tooltips are supplementary, never the only evidence explanation.

## Visual direction

Operate mode: light neutral workspace for office use; dark ink; blue selection/action; restrained green configured, red missing and brown deleted/difference text with readable contrast. System UI fonts with Microsoft YaHei/PingFang fallbacks; 13–14px dense body, 28–36px controls, square/slightly rounded panels, table dividers, no gradients or decorative animation. Keep long Chinese descriptions wrapping rather than hiding the requirement in a tooltip. Default desktop 1440×900; inspect 1024-width and narrow fallback. No external fonts/assets/network requirements.

## Prototype review route

1. Start empty, select a DOCX (name only) or load example; run simulated check.
2. Confirm 11 total, 8 configured, 2 missing, 1 struck-out, 1 description difference.
3. Filter each status; search `2门`; select DR-006 and inspect `2s → 3s` and table context.
4. Select DR-004 to inspect deleted actual text; select DR-003 to inspect missing evidence.
5. Select DR-002 NORMALIZED and DR-009 ALIAS; inspect explanations without invented confidence.
6. Open management, add/edit/disable/delete, cancel an edit; verify invalidation and rerun.
7. Keyboard navigation, invalid extension, no-results search and selection replacement should remain understandable.

## Confirmed production states beyond the prototype

- 待人工核查: status unset, resolution UNRESOLVED. Show reasons and all evidence; no confidence badge or “未配置” fallback. Include it in summary and filters. Total enabled = configured + missing + struck-out + unresolved. Description-difference count is orthogonal, not added to that sum.
- 仅异常 includes missing, struck-out, unresolved and description differences. Recommended initial ordering: unresolved, missing, struck-out, configured with differences, remaining configured; stable baseline order within each group. This UX ordering carries no evidence priority.
- 检查范围受限 (coverage=LIMITED): persistent run-level notice with excluded/unsupported content details, separate from status. Summary describes checked scope. Scope excludes automatic joining across paragraphs/cells and unsupported Word parts; failure to extract safely is an error instead of a limited success.
- Missing expected description: show 未比较描述. Alias hit without a validated comparison also shows 未比较描述. A single established function with a changed value remains 已配置 + 描述有差异; conflicting active values across occurrences are 待人工核查.
- Loading/progress/cancel: keep the UI usable; cancelled/failed runs do not show successful final counts. Document/baseline changes invalidate prior results. Recover from local access/locked-file/write failures with actionable messages.
- First launch/deployment: no elevation prompt or user-installed Python/Qt prerequisite. The validated distribution may be portable or an allowed per-user installer. Explain user-data location and preserve baseline during app replacement. Report IT policy blocks without suggesting privilege escalation or policy bypass.

## Qt Widgets implementation direction

Use a main window, splitter-based list/detail workspace, item views for results/baseline, and standard dialogs for file selection and item editing. These are implementation directions for the selected toolkit, not a reusable widget framework. Keep matching/parsing outside widgets. Test keyboard focus, Chinese input, long labels and Windows DPI on both target OS families. The compact browser layout is a visual reference, not a requirement to embed HTML in Qt.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
