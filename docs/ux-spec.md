# UX specification

Status: DRAFT FOR REVIEW. Interface language: simplified Chinese; documentation: English. Target: Windows engineering workstation. Prototype: local browser only.

## Information architecture and primary flow

Two top-level destinations: 文档核查 and 检查项管理. Keep product/document identity and prototype disclosure visible. Import → loaded/ready → explicit run → results → exception selection → comparison and source. No wizard, dashboard home, login or navigation hierarchy.

Use a compact horizontal title bar, document toolbar, summary/filter strip, and a split workspace. Left: approximately 40% width, dense rows with code/name/status and difference hint. Right: selected requirement, status and match method, expected/actual comparison, evidence explanation and original context. A narrow footer explains result scope. At smaller widths panes stack; desktop remains the intended usage scene.

## States

- Empty: clear DOCX drop/select target, explanation of local operation, separate “使用示例文档” action.
- Loaded: selected filename and “开始模拟核查”; no results until run. Selected-file bytes are never parsed in the prototype.
- Loading: short simulated progress with disabled run button; do not suggest real parsing. Production requires cancel/progress for long operations.
- Complete: counts for the full baseline, filters, search, selection and detail. Exceptions sort first in the mock: missing, struck-out, changed, ordinary configured. Default All preserves context; an “仅异常” shortcut includes the first three groups.
- Unsupported selection: inline alert names allowed `.docx`; selection of multiple files is rejected. File extension is only a prototype input gate, not production format validation.
- No search/filter results: explicit empty result view and clear-filters action; no stale detail.
- Baseline edited: results cleared and rerun required. Browser refresh resets session edits, visibly disclosed.
- Production parse failure: error with recovery/reselect; never all-missing. Protected/malformed/oversized content is specified but not simulated as a real parser outcome.

## Result and detail behavior

Summary counts remain stable while filtering. All/configured/missing/struck-out plus exception shortcut; search code/name/category/expected text. Missing and struck-out use distinct words and symbols, not color alone. Selection highlight must not resemble engineering approval.

Detail shows canonical name/category/code, expected requirement, actual text, match method (with scope of what matched), optional separately labelled score, difference, and source. A configured-but-different item keeps CONFIGURED and adds 描述有差异. No “passed” language. `2s → 3s` appears explicitly alongside both full descriptions. Diff is a mock token replacement, not a claimed generic production diff engine.

Missing detail says no matching evidence in the example and gives no fabricated document location. Struck-out detail renders actual text using a strike line and a status label; expected text remains intact. Original context shows previous/current/next blocks with table coordinates. Preview is a reconstructed excerpt, not a Word-page rendering; use one-based coordinates. Repeated candidates and partial strike need production policy approval before their classification can be prototyped honestly.

## Checklist management

Compact table: code/name/category/expected description/enabled state/actions. Add/edit dialog includes code, name, category, expected description, aliases (one per line), notes, enabled toggle. Required code/name and unique code enforced; blank expected description allowed with explanation. Similar names/aliases need production overlap warning; prototype prevents exact duplicate names. Disable reversible; deletion asks confirmation. Save closes dialog, returns focus and invalidates results. Cancel/Escape discards edits. Session-only changes are clearly labelled.

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
