# Technology-neutral delivery roadmap

Status: DRAFT FOR REVIEW. Milestones describe outcomes, not weekly commitments or framework tasks. Available time is approximately eight hours/week; schedule estimates follow stack selection and spikes.

| Milestone | User-visible outcome | Acceptance criteria | Major unknowns / gate |
|---|---|---|---|
| 0 Product definition and prototype | Engineer can walk through import, exception review and baseline edits using clearly labelled mock data | Six requested documents plus runnable clickable prototype; unresolved policies visible; no production engine | Review UX/product; approve bounded spikes; then explicitly choose production stack before implementation planning |
| 1 Real DOCX ingestion | Engineer opens a supported local document and inspects text, formatting and source locations | Paragraph/table/run fixtures match labelled content; effective strike and source mapping verified; unsupported input explicit; original unchanged | Styles, document parts, nested tables, actual input corpus and scale limits |
| 2 Deterministic verification | Engineer sees explainable function findings against enabled baseline data | Approved exact/normalization/alias/strike policies reproducible; evidence complete; ambiguity not silently forced into missing | Occurrence precedence, partial strike, function-term definition and false matches |
| 3 End-to-end document checking | Import → run → summary → selected result → expected/actual/context works offline | Counts/filters/search consistent; failures distinct from missing; UI remains responsive; same input/baseline rules reproduce results | Performance, incomplete-document policy, reviewer understanding |
| 4 Checklist management | Engineer maintains and locally saves the baseline | Add/edit/disable/delete/category/aliases/notes; validation; edits invalidate current results; reload preserves baseline | Baseline ownership, order applicability, overlap rules, storage location and backup needs |
| 5 Historical-document validation | Engineer can judge reliability on real orders | Sanitized labelled corpus; report precision/recall, false positives/negatives, strike accuracy, unresolved rate and review-time change; owner agrees release thresholds | Representative sampling and ambiguous ground truth; review effort |
| 6 Windows packaging and pilot | Pilot users install and check local documents on managed Windows PCs | Offline install/launch and local checking without dev tools; agreed privilege model; upgrade/uninstall and data preservation checked; pilot issues recorded | IT policy, signing, endpoint protection, support owner and release method |

Packaging feasibility is checked early by S3 even though production packaging/pilot is Milestone 6. Milestone 2 uses baseline data; Milestone 4 adds the full editing/persistence experience, not a hardcoded checklist workaround. A simple expected/actual comparison belongs in Milestone 3; fuzzy matching and enhanced diff remain separate candidates.

After the MVP pilot: assess whether enhanced diff, fuzzy candidates, report export, manual confirmation or preview improvements actually reduce review effort. AI, document editing and team synchronization require new product decisions. No recurring infrastructure, IPC implementation sequence, database selection or framework-specific work breakdown is implied.
