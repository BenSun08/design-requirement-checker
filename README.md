# Design Requirement Checker

**Product definition + UX prototype + technology evaluation. Production technology is not selected.**

## Open the prototype

Double-click `prototype/index.html` in a current Edge/Chrome browser. No package installation, build, server, Python, Node, Office or network connection is required for this route. Keep the four files in `prototype/` together.

Optional local preview server, from the project root:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

On Windows with Python already installed, use `py -m http.server 8765 --bind 127.0.0.1`. Open [local preview](http://127.0.0.1:8765/prototype/). Python here is an optional static-file server, not a selected product dependency.

Choose **使用示例文档**, then **开始模拟核查**. Alternatively select/drag one `.docx`; only its name is used. All results and context are fixtures. Baseline edits are session-only and reset on refresh. New or materially edited items have no matching fixture and use an explicitly labelled missing demonstration, not a real document conclusion.

Review `2门控制延时` for `2s → 3s`, `昼行灯状态判断` for deletion formatting, `GAG客户电动导板` for missing evidence, and `侧标志灯功能` for alias evidence. Try filters/search and 检查项管理. No real document parser/matcher, persistence, report export or production installer exists.

## Documents

- [Product specification](docs/product-spec.md): requirements, edge cases, Q1–Q9 and acceptance criteria.
- [Domain model](docs/domain-model.md): technology-neutral concepts and invariants.
- [UX specification](docs/ux-spec.md): workflows, states and review route.
- [Technology options](docs/technology-options.md): five options, ordinal matrix and provisional recommendation with primary references.
- [Technical spikes](docs/technical-spikes.md): bounded proposals, not executed experiments.
- [Delivery roadmap](docs/delivery-roadmap.md): technology-neutral milestones.
- [Prototype verification](docs/prototype-verification.md): observed checks and limitations.

## File boundaries

`prototype/index.html` — markup; `styles.css` — presentation; `mock-data.js` — 11 fixtures; `app.js` — disposable interactions. This is not the production architecture. Production checklist configuration must be data, not fixtures embedded in source.

## Review gate

Review product/UX and ambiguous classification rules; approve specific spikes and provide development/Windows constraints. Select the production stack explicitly after evidence review. A detailed production implementation plan and production implementation require a subsequent instruction.
