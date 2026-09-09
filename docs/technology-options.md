# Production technology options

**PROVISIONAL — no stack selected.** Researched 2026-09-10 against primary documentation. No candidate engine or Windows package was built. Ratings below are engineering judgements for this project, not benchmark results. Prototype HTML/CSS/JavaScript is disposable and gives no candidate an entitlement to selection.

## Decision context and matrix

Windows desktop, local/offline DOCX, Chinese engineering text, dense review workspace, explainable deterministic checks, approximately eight hours/week of development. Developer/team familiarity and managed-device policy are unknown and could reverse the ranking. AI receives low weight. Every candidate can separate presentation/application/domain/adapters without services.

Weight is ordinal: **Critical** can veto a candidate, **High** materially affects sustainable delivery, **Medium** breaks ties, **Low** is optional future value. No numerical total: differences are not precisely measurable yet. “Strong” means a credible fit, not validated correctness.

| Criterion | Weight | A Python + PySide6 | B Electron + TS/Node | C Electron + Python core | D Tauri + web UI | E C#/.NET + WPF (WinUI variant) |
|---|---|---|---|---|---|---|
| OOXML fidelity and traceability | Critical | Credible; style resolver needed | Credible with lower-level XML; more adapter work | Same Python risk as A | Rust/XML or sidecar; higher uncertainty | Strong typed OOXML access; style resolution still required |
| Sustainable at 8 h/week | High | Strong if Python familiar | Good if web/Node familiar | Weaker: two runtimes + contracts | Weaker without Rust experience | Strong if C# familiar; XAML learning otherwise |
| Dense desktop review UX | High | Strong with Qt Widgets | Strong, web accessibility work | Same as B | Strong web UX | Strong WPF controls/binding |
| Offline Windows installation | High | Feasible; freeze + installer test | Mature distribution; larger runtime | Two packaged runtimes | WebView2 availability/offline install test | Strong; runtime/self-contained choice |
| Debugging/handover | High | One application language + Qt model | TS plus main/renderer boundaries | TS/Python process lifecycle | TS/Rust, possibly Python | C# plus XAML; .NET conventions |
| Deterministic unit testing | High | Strong | Strong | Strong core; IPC tests extra | Strong; mixed-toolchain tests extra | Strong |
| Footprint | Medium | Bundle Python/Qt; measure | Chromium/Node bundle; likely largest base | B plus Python distribution | Smaller app possible; include WebView2 cost | Runtime-dependent versus self-contained tradeoff |
| Windows/Office integration | Medium | Possible via adapters | Possible, additional integration | Python integration possible | Additional integration work | Most direct ecosystem fit |
| Future NLP/AI | Low | Easy Python library access | TS/API options; no AI required | Easy Python library access | Rust/TS/API or sidecar | .NET/API options; no AI required |

All support local file dialogs, file access, drag/drop and Unicode; Chinese IME, fonts, long paths, DPI and dense selection behavior need Windows validation. No measured antivirus ranking or exact installer size is claimed.

## A — Python + PySide6 / Qt Widgets

**Shape:** one desktop application, Python application/domain/adapters, Qt Widgets presentation; background work as necessary to keep UI responsive, without a separate service. No QML or embedded web engine needed for this UI.

**Advantages:** a single authored programming language, convenient text/fixture work, mature desktop controls. Python domain can be tested without launching the UI. Qt for Python provides official bindings; the documented deployment tool can produce a Windows executable. [Qt for Python](https://doc.qt.io/qtforpython-6/index.html), [pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html).

**DOCX strategy:** python-docx for convenient paragraphs/tables/runs, with focused OOXML inspection where its model does not expose enough. `Font.strike` is tri-state; `None` must not become false. Prototype-level plain-text extraction is inadequate. Validate inherited formatting and run span mapping. [python-docx text API](https://python-docx.readthedocs.io/en/latest/api/text.html).

**Disadvantages/risks:** Qt model/view and signals have a learning curve; dependency freezing, plugin inclusion and runtime faults require desktop testing. High-level library support does not prove full Word fidelity. Packaging/license review for chosen Qt components belongs in the spike, not assumptions about zero deployment effort.

**Complexity:** low-to-medium relative to the candidates, assuming Python comfort; inheritance fidelity may dominate total work. **Packaging:** frozen application directory or executable using a supported tool, wrapped in a Windows installer; bundle runtime so end users need not install Python. Begin with manually distributed signed releases; updater is a later business choice. **Future:** Python text/NLP and document generation fit naturally, but document round-trip fidelity still needs proof.

## B — Electron + React + TypeScript + Node.js

**Shape:** renderer presentation, narrow preload/IPC boundary, main/application coordination, Node OOXML/domain adapters; CPU work may need a worker. Electron is already multi-process even with only TypeScript application code. [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model).

**Advantages:** expressive split/list/detail UI; common web tooling and test ecosystem; a single authored application language with Node core. Strong option when maintainer expertise is web-first.

**DOCX strategy:** ZIP/XML-based OOXML adapter retaining runs/styles/locations. A converter that returns plain text or HTML is not automatically a faithful evidence model: Mammoth explicitly focuses on semantic HTML rather than exact styling and offers raw-text extraction that ignores formatting. It should not be accepted as the complete checker parser without a fidelity spike. [Mammoth documentation](https://github.com/mwilliamson/mammoth.js).

**Disadvantages/risks:** Chromium/Node footprint and runtime updates; renderer/main debugging; accidental privileging of document-derived content; potentially more custom OOXML/style code than A/E. Keep document text inert, renderer isolated and local file access narrow. [Electron security guidance](https://www.electronjs.org/docs/latest/tutorial/security).

**Complexity:** medium; higher when Node DOCX fidelity needs custom work. **Packaging:** packaged Electron app plus Windows installer, likely using Forge ecosystem; bundled Chromium/Node provides consistency at a footprint cost. [Electron application packaging](https://www.electronjs.org/docs/latest/tutorial/application-distribution). **Future:** TS text tools and APIs remain viable. A Python sidecar turns this into option C and needs new justification, not an invisible implementation detail.

## C — Electron + React/TypeScript + Python core

**Shape:** Electron presentation/main, a locally spawned Python process for ingestion/matching/persistence; messages over a bounded local IPC mechanism. No HTTP server required. Single owner of baseline persistence; do not implement it twice.

**Advantages:** web UI plus Python document/text ecosystem; independently testable Python domain. **DOCX:** same approach and fidelity uncertainties as A. A second process does not improve parsing correctness.

**Disadvantages/risks:** two language/toolchains, packaging both runtimes, startup/shutdown, cancellation, protocol errors, request identity, Unicode payloads, crash recovery and version compatibility. Avoid shell command construction from file paths. Process isolation can contain faults but creates operational work.

**Complexity:** high relative to A/B/E at eight hours/week. **Packaging:** Electron installer bundling Python executable and dependencies for each architecture; atomic app/core updates. Largest expected footprint of these shapes, unmeasured. **Future:** Python reuse helps only if a real shared core or indispensable Python-only functionality exists. Do not pick this solely for hypothetical AI.

## D — Tauri + React/TypeScript

**Shape alternatives:** (1) TS document processing with file bytes supplied through a constrained native boundary; (2) Rust document/domain backend with web UI; (3) Python sidecar plus Rust/Tauri bridge. These have materially different costs and must not share a single optimistic rating.

**Advantages:** web review UI with a potentially smaller shipped shell; constrained native capabilities; Windows installer tooling. **DOCX:** TS ZIP/XML, Rust ZIP/XML, or A's Python strategy depending on variant; no library has been validated here.

**Disadvantages/risks:** Rust build/toolchain and platform plumbing even when little Rust is authored; web/native debugging; WebView2 provisioning on offline managed machines. Python sidecar adds a third ecosystem and erodes footprint/simplicity advantages. Tauri documents MSI/NSIS installers and WebView2 installation modes, including offline options. [Windows installer](https://v2.tauri.app/distribute/windows-installer/). External binaries require platform-specific packaging/configuration. [Sidecars](https://v2.tauri.app/develop/sidecar/).

**Complexity:** medium-to-high for TS/Rust; high with Python. **Packaging:** MSI or NSIS plus an explicit WebView2 strategy; count offline runtime payload when comparing size. **Future:** possible, but no present requirement earns the extra language. Consider only if footprint or existing Tauri/Rust expertise is material.

## E — C# + .NET + WPF / WinUI

**Shape:** one desktop application with C# application/domain/adapters and XAML presentation. WPF provides desktop controls and data binding and runs on Windows. [WPF overview](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/overview/).

**Advantages:** direct Windows ecosystem fit, established dense data UI patterns, strongly typed Open XML SDK and familiar enterprise maintenance conventions. Good handover if future engineers use .NET.

**DOCX strategy:** Open XML SDK traversal of paragraphs/tables/runs and package parts; own source map and effective-formatting policy. Typed elements provide structural access, not Word layout or automatic policy resolution. Microsoft documents strike inheritance in the style hierarchy. [Open XML document structure](https://learn.microsoft.com/en-us/office/open-xml/word/how-to-open-and-add-text-to-a-word-processing-document), [Strike semantics](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.strike?view=openxml-3.0.1).

**Disadvantages/risks:** C#/XAML/binding learning if unfamiliar; custom diff display and OOXML semantics still work. WPF is Windows-only, which matches this product but limits portability. **WinUI variant:** modern Windows UI through Windows App SDK, but introduces additional deployment/tooling decisions with no clear MVP advantage over WPF's dense desktop fit. Validate only if Windows App SDK integration is required. [WinUI 3](https://learn.microsoft.com/en-us/windows/apps/winui/winui3/).

**Complexity:** low-to-medium for an experienced .NET developer; medium if learning. **Packaging:** framework-dependent deployment with managed runtime prerequisite, or larger self-contained deployment; then installer/MSIX policy selected with IT. A single-file executable is not itself an installer. [NET publishing](https://learn.microsoft.com/en-us/dotnet/core/deploying/). **Future:** document generation/Windows integration fit well; AI need not require Python. Word COM integration, if ever approved, adds Office deployment/version constraints.

## Cross-option operational evaluation

- Measure installer bytes, installed bytes, cold start, memory and responsiveness on the same Windows machine and fixture. Do not quote generic megabyte claims as project estimates.
- Test without development runtimes and without Internet, using standard-user rights, Chinese filenames, locked files and enterprise endpoint protection.
- Prefer manual signed installer distribution initially if IT accepts it. Auto-update adds connectivity, trust, rollback and baseline-preservation work for every stack.
- Antivirus false positives and Windows trust prompts are different phenomena. Signing is useful but is not a guarantee that every policy accepts an executable; test the actual organizational environment. [Microsoft code-signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).
- Codex can assist all candidates; no evidence justifies a productivity multiplier or claim that generated code removes OOXML/packaging validation. One toolchain and inspectable fixtures make assistance easier to review.

## Current recommendation — PROVISIONAL

**Tentative preference: A, Python + PySide6 using Qt Widgets.** It matches the document/text-heavy scope and dense desktop UI with one application language and no custom desktop/core process contract. This is a maintainability inference, conditional on developer familiarity and successful Windows deployment/style-fidelity spikes.

**Strongest alternative: E, C#/.NET + WPF.** Its Windows and typed OOXML fit is particularly compelling. Prefer E over A if .NET is the team's handover standard, Qt distribution constraints are unacceptable, or the same-fixture spike shows materially less effort with the Open XML SDK.

B remains credible if web/TS skill dominates; C needs demonstrated Python-only requirements plus a strong web UI reason; D needs a concrete footprint or team-expertise benefit. Do not run five full implementations. First ask about skills/IT constraints, then validate A and E on the same tiny fixture and packaging probes. The owner chooses the final stack only after reviewing that evidence.
