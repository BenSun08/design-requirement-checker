# Design Requirement Checker — 实施计划

**2026-09-11 框架初始化记录**

用户已单独批准基本目录与桌面框架初始化；当前仓库已包含 Python 包、启动入口、
最小 Qt Widgets 窗口及启动检查。详见 [验证记录](../docs/skeleton-verification.md)。
本次未完成下文 Task 1 技术验证或 Task 2 真实 DOCX 纵向切片；下文关于源码尚未
创建的描述属于初始化之前的规划状态。

**2026-09-18 执行记录：** Task 1 的 S1/S2 实验已执行（macOS、合成夹具），
见 [technical-spikes.md](../docs/technical-spikes.md)。Task 2 首个 DOCX 纵向切片
已于同日执行：领域值模型、经 S1/S2 验证的 python-docx 1.2.0 ＋针对性 OOXML
适配器、导入协调与最小 Qt 文档视图，测试先行。同日修复切片修复了评审发现的
摄取／覆盖缺陷：提取超链接包裹的 run（此前静默丢失）、检测首页／偶数页页眉
页脚变体及仅含表格的页眉／页脚内容、已知不支持结构（域代码、脚注／尾注引用、
`w:altChunk`、智能标记、嵌套超链接）强制 LIMITED 而非静默 COMPLETE、默认段落
样式从 `w:default="1"` 标记解析而非假定 "Normal" id、读取失败带独立类别
（file-access-error / invalid-or-unreadable-document / unexpected-parser-error），
且预览保留空白（`white-space: pre-wrap`）。匹配、基准持久化、后台执行与
Windows 验证仍属后续任务。

**2026-09-19 执行记录：** Task 1 的 S6（确定性规则与规模验证）已作为
有限实验在 macOS 开发机上执行，见 [technical-spikes.md](../docs/technical-spikes.md)。
以隔离实验代码（`tests/s6_probe.py`、`tests/test_spike_s6_rules.py`、
`tests/test_spike_s6_scale.py`）中的手写标签测试证据确立了：精确规范化
白名单（批准 N1–N3，显式拒绝 R1–R7）、原文 ↔ 规范化偏移映射、带显式
不确定性原因（`requirement-span-association-uncertain`、
`no-associated-requirement-content`）的仅向前要求范围关联规则、基于要求
范围的删除线评估、已确认真值表（CONFIGURED / STRUCK_OUT / MISSING /
UNRESOLVED 且状态未设置）、重复／冲突证据行为、作为独立维度的描述比较、
核查级与配置级歧义之分、规模可行性（3,000 块 × 100 条目 ≈ 1.1 s；瞬时
峰值 ≈ 0.13 MB）、每（CheckItem, 块）取消检查点与确定性。未编写生产
匹配代码；`matching.py` 仍为占位符，Task 3 仍是待执行的独立切片。

**2026-09-20 执行记录：** Task 3（确定性核查）已作为一个有限的生产切片执行。
生产领域模型（CheckItem、CheckItemAlias、CheckResult、CheckStatus、
Resolution、ComparisonState、MatchType、StrikeCoverage、MatchEvidence）与
纯匹配引擎现已精确实现经 S6 验证的契约：带原文偏移可追溯性的 N1–N3
规范化白名单（R1–R7 被拒绝变换保留为负向测试）、仅基于已配置短语的
精确／规范化／别名检测、带 S6 不确定性原因的仅向前要求范围关联、基于
要求范围的删除线覆盖、已确认真值表（UNRESOLVED 保持状态未设置）、
保留的重复／冲突／歧义证据、独立的 SAME/DIFFERENT/NOT_COMPARED 比较、
每（CheckItem, 块）取消检查点与确定性排序。`application.py` 提供带显式
完成／取消生命周期的 `verify_document`；取消的运行绝不产生已完成的结果集。
245 项测试通过，包含合成 DOCX → 摄取 → 核查的组合测试；未引入模糊／语义
匹配、置信度分数、第四种状态，未提前实现 Task 4 UI 或 Task 5 持久化。

**2026-09-21 修复：** Task 3 取消检查点语义已修复。检查点现在紧接在每个
（CheckItem, 块）候选搜索之前执行，而不是在匹配工作之前成批触发；跨条目
歧义与要求范围关联仍在该块所有候选收集完毕后运行。未更改任何匹配策略。
246 项测试通过。

**2026-09-21 执行记录：** Task 4（Qt 审查工作区）已在分支
`task4-qt-review-workspace` 上以 13 个可审查子任务执行。MainWindow 现拥有
显式 `UiState` 生命周期（EMPTY / IMPORTING / READY / VERIFYING / COMPLETED /
CANCELLED / FAILED）驱动操作可用性，并以单调递增的操作代数 token 使过期
worker 结果失效。DOCX 导入与 `verify_document` 通过小型 QObject worker 在
专用 QThread 上脱离 UI 线程运行；取消使用现有 application 回调。工作区外壳
为 QSplitter（结果列表＋详情），上方为标题／工具栏、汇总＋搜索条与持久
状态／页脚。完成的运行显示汇总计数（total = configured + missing +
struck_out + unresolved；DIFFERENT 正交）与优先级排序
（UNRESOLVED → MISSING → STRUCK_OUT → CONFIGURED+DIFFERENT → 其余
CONFIGURED）。筛选（全部/已配置/未配置/已划除/待人工核查/仅异常）与搜索
（code/name/category/expected/description）基于缓存结果集操作，不重新计算
核查。详情面板呈现状态、比较状态、预期/实际、匹配方式、审查原因
（UNRESOLVED 原因 token 仅在 UI 层映射为中文）、按状态呈现
（MISSING 显示限定范围的提示且不虚构证据；STRUCK_OUT 显示删除线样式与
文字状态；NOT_COMPARED 显示可读原因）、多证据选择器，以及重建的前/当前/
后块源文本上下文并高亮要求范围。LIMITED 覆盖显示持久的"检查范围受限"
提示，在筛选与详情导航后仍然可见。支持键盘导航（Up/Down/Enter、Ctrl+F）。
matching.py 与 domain.py 保持无 Qt；CheckItems 通过构造函数注入
（`Sequence[CheckItem]`，默认空 → 尚未加载检查项，运行禁用）。未引入持久化、
清单编辑器、Task 5、HTTP/sidecar 或通用任务框架。317 项测试通过
（test_ui.py 96 项）；ruff check、ruff format --check、mypy（严格）、
pip check 与 git diff --check 本地全部通过。此前关闭已启动后台线程的
窗口期间出现的间歇段错误已解决：`_stop_worker` 现在保留所有尚未真正
结束的 QThread 的所有权（绝不销毁仍在运行的线程），在退出前设置核查
取消事件，且 `_finish_operation` 仅在当前线程/工人引用仍指向本次完成
的操作时才清除它们。

[English source](../docs/implementation-plan.md)

本文件为同名英文文档的对应中文版本；字段、状态、路径与命令保留原技术标识。

**状态：**用户确认后更新；规划文档，不构成执行授权。
**目标：**交付可在 Windows 10/11 x64 由无管理员／安装权限普通用户使用的本地 DOCX 核查工具。
**技术栈：Python + PySide6 / Qt Widgets，用户已选定。** DOCX 库、本地存储、依赖版本与打包工具须在所选栈内验证。
**架构：**一个本地桌面进程。Python 应用／领域／适配器独立于 Qt 展示；后台执行保持响应，不设 sidecar、HTTP 服务、QML 或内嵌 Web。
**规格：**[product-spec.md](product-spec.md)、[domain-model.md](domain-model.md)、[ux-spec.md](ux-spec.md)。
**投入：**约八小时／周，单开发者流程。

**平台边界：**macOS 和 Windows 是开发及 CI 平台；生产运行环境仍为
Windows 10/11 x64，Windows 产物只在 Windows 构建。首次使用 PyInstaller
onedir 便携目录，不支持从 macOS 交叉编译 Windows 程序。

本修订取代旧八周计划中的选栈任务，记录已确认规则及任务／验收边界，不把未经验证的库 API、版本、Windows 分发方式当作定案。本次不创建生产源文件。执行前审查实验依据并授权一个有限切片，再据已验证依赖展开精确接口和命令。

## 当前状态与全局约束

- 当前生产代码是桌面框架，并保留历史浏览器模拟；macOS／Windows 开发共用一套 Python 源码。两者都不构成 Python 解析器或 Windows 部署证据。
- Windows 10/11 x64，无管理员／安装权限，不要求用户安装 Python/Qt/Office。具体 Windows 构建及运行时兼容属于 S3。
- 首次分发、解压／安装、首次启动和核查完全离线，原件不变。目标电脑不依赖在线引导安装器、pip install、激活或依赖下载。
- GitHub Actions 在 macOS 和 Windows 使用 Python 3.13 验证；Windows-only 手动工作流生成 PyInstaller onedir 候选包。CI 构建是 S3 输入，不代表 S3 完成。
- 后续基准／配置／日志的持久化路径由平台适配器通过 Qt `QStandardPaths` 取得；领域层和应用层保持 OS 无关，不在可执行文件目录写运行数据。
- 一套本地基准；id/code/name/detectionPhrase 必填，expectedDescription 可选，aliases/category/notes/enabled 明确。不自动提词、不建订单模板框架。
- 三个 CheckStatus 加独立 UNRESOLVED，后者 status 为空。正常／删除线并存、部分／未知格式、身份歧义、有效关键值冲突待人工核查。
- 保留所有合格出现；单处明确功能参数变化可为 CONFIGURED + DIFFERENT；没有预期／不支持比较为 NOT_COMPARED。
- 正文／表格／单元格段落，只重建段内 run。不支持范围标 LIMITED，区别于失败和 MISSING。
- MVP 不含模糊／AI、编辑、Word 自动化、自动更新基础设施、插件或共享服务。

## 执行门槛

| 门槛 | 状态／要求 |
|---|---|
| A 产品规则 | 用户已确认 1–7，不重复询问相同规则；用夹具验证转换和要求范围细节 |
| B 技术栈 | 已关闭：选择 Python + PySide6 Qt Widgets；不比较决赛候选、不自动转用其他框架 |
| C 技术就绪 | 已有跨平台 CI 和初始 PyInstaller onedir 配置；S1/S2/S3/S6 仍待验证，CI 产物不证明干净电脑离线部署 |
| D 执行授权 | 本次不执行实验或生产代码；下个有限工作包需要授权 |
| E 试点 | 标注夹具／历史验证和无管理员 Windows 部署通过，用户同意发布阈值 |

## 建议的源文件职责

以下是计划路径，并非已有文件。保持小模块结构，只有实际职责增长时才拆分。

| 建议路径 | 职责 |
|---|---|
| `src/design_requirement_checker/domain.py` | Python 值模型、不变量、结果／覆盖概念；不导入 Qt／文件系统 |
| `src/design_requirement_checker/matching.py` | 纯短语／别名／规范化、证据汇总、分类 |
| `src/design_requirement_checker/application.py` | 导入／核查／取消协调、基准快照、结果失效 |
| `src/design_requirement_checker/docx_adapter.py` | 已选 Python OOXML 读取、run／样式／来源映射、范围提示 |
| `src/design_requirement_checker/baseline_store.py` | 用户可写位置的一套基准加载／保存／恢复 |
| `src/design_requirement_checker/ui/main_window.py` | Qt Widgets 导入和分栏审查 |
| `src/design_requirement_checker/ui/checklist_dialog.py` | 基准编辑／校验、detectionPhrase 字段 |
| `src/design_requirement_checker/__main__.py` | 只负责启动／组装 |
| `tests/fixtures/`, `tests/test_domain.py`, `tests/test_matching.py`, `tests/test_docx_adapter.py` | 独立期望输出和确定性测试 |
| `tests/test_application.py`, `tests/test_baseline_store.py`, `tests/test_ui.py` | 失效／取消、保存／恢复及重点 Qt 交互 |
| `pyproject.toml`、`.github/workflows/`、`packaging/windows/` | 共享开发／CI 依赖、测试／质量命令、Windows-only PyInstaller onedir 打包 |

不建通用 repository、协议框架或内部插件系统。公共契约遵循领域规格，库专用对象不能逃出适配器。持久化保存基准数据，不保存模拟源码夹具。提出目录结构不代表授权搭建。

## 任务 1 — 验证证据与 Windows 可行性

**产物：**合成夹具、独立标签、有限实验记录；执行之后才能把真实结果写入 technical-spikes.md。

- [ ] 确定获准的开发／构建环境，保留公司 Python 3.8；记录是否允许隔离的新解释器，在安装前验证候选依赖兼容性。
- [ ] 准备正常／表格／混合 run／全文／部分／继承删除线／冲突夹具及脱敏样本。
- [x] 执行 S1/S2，确定 Python DOCX 访问方式和来源／覆盖行为。已于 2026-09-18 在 macOS 开发机上用合成夹具和独立标签执行；证据与限制记录于 [technical-spikes.md](../docs/technical-spikes.md)。选定 python-docx 1.2.0 ＋ 针对性 OOXML/XML 访问；保留未知格式；合并单元格／修订／排除结构的风险已显式化。Windows/S3 与真实文档证据仍待补。
- [ ] 在两类 Windows 上以普通用户执行 S3，优先便携分发并记录策略限制。
- [x] 执行 S6，验证转换白名单、具体短语、要求范围、性能／取消限制。已于 2026-09-19 在 macOS 开发机上用合成夹具和独立标签执行；证据见 [technical-spikes.md](../docs/technical-spikes.md)：精确规范化白名单（批准 N1–N3，带反向测试拒绝 R1–R7）、原文 ↔ 规范化偏移映射、带显式不确定性原因的仅向前要求范围关联、基于要求范围的删除线真值表、冲突／歧义行为、比较独立性、规模可行性（3,000 块／100 条目 ≈ 1.1 s）、每（条目, 块）取消检查点与确定性，以及与真实 Task 2 摄取输出的组合验证。Windows/S3 与真实文档证据仍待补。
- [ ] 验证单基准存储／恢复，选择用户可写位置／格式。
- [ ] 记录版本、失败、不支持特性、下个切片；不能从文档审查宣称实验通过。

**验收：**每个约定用例有实际期望／观察对照或明确差距。无管理员失败阻塞部署就绪。S4 IPC 撤销，S5 往返编辑延期。超过时间上限就报告并重排，不能暗中长成生产引擎。

## 任务 2 — 首个纵向切片：打开并查看真实 DOCX

**文件：**domain.py、docx_adapter.py、application.py、ui/main_window.py、__main__.py；tests/test_domain.py、tests/test_docx_adapter.py、tests/test_application.py 及夹具。依据任务 1 在此切片中建立包／测试配置。

**输入：**本地文件选择、不可变字节。**输出：**带段落块、原始 run／有效删除线、快照稳定位置和范围提示的 Document，或明确失败。

- [x] 编写段落文本、表格／单元格来源、拆分 run、样式继承及不支持／损坏文件断言。2026-09-18 完成于 tests/test_domain.py、tests/test_docx_adapter.py、tests/test_application.py 与 tests/test_ui.py，期望标签手写并复用实验夹具工厂。修复（同日）新增夹具：超链接包裹的 run、页眉／页脚变体（含仅表格内容）、自定义默认段落样式、不支持结构（域代码、脚注／尾注引用、`w:altChunk`、智能标记）及密码保护文档的 OLE 复合文件容器。加密／密码保护 DOCX 的处理在该容器格式失败路径之外仍未验证——见剩余验证事项。
- [x] 实现前证明缺失／错误行为导致测试失败。四个新测试模块在实现前均收集失败（ImportError），见 Task 2 运行记录。
- [x] 在已确认范围内实现最小提取及领域校验，不跨段落／单元格匹配。domain.py（带校验的值模型）、docx_adapter.py（由已验证的实验探测移植的 python-docx 1.2.0 ＋针对性 OOXML/XML 访问）、application.py（import_document → Document 或 ImportFailure）。
- [x] 最小 Qt Widgets 窗口显示文件名、块与格式，解析留在 widgets 外。ui/main_window.py 渲染文件名、覆盖警告与带删除线标记的文本块；仅调用应用层用例（导入延迟到首次使用，启动组装不加载文档适配器）。
- [x] 检查原件不变、位置可重现、LIMITED／失败区别于成功空内容。由 test_docx_adapter（前后 sha256、重复读取稳定性）与 test_ui（LIMITED 警告、显式失败、空文档可区分）断言。
- [x] 执行针对性及已配置全项目检查，审查有限 diff，更新限制。87 项测试通过；ruff check、ruff format --check、mypy（strict）、pip check、git diff --check 全部通过。已知限制：导入期间解析在 UI 线程执行（后台执行属任务 4）；Windows 与真实文档验证待补。修复重新运行全部检查：100 项测试通过，其余检查同样通过；Windows PyInstaller 工作流在修复切片中未触发，待手动运行。

**验收：**真实输入→真实块→可见来源成立，暂不做匹配。未知格式不默认为正常；不支持内容不会无提示消失。

## 任务 3 — 确定性核查

**文件：**matching.py、domain.py、application.py；tests/test_matching.py 及标注夹具。

**输入：**Document 快照、启用 CheckItem 快照、规则版本。**输出：**每个启用项一个 CheckResult，包含全部证据、resolution/status、比较状态和原因；coverage 在运行层。

- [x] 添加精确 detectionPhrase、保守规范化、明确别名、原文偏移映射测试。tests/test_matching.py 覆盖精确／缺失／宽泛／相邻／仅名称检测、S6 N1/N2/N3 白名单与原文范围映射、被拒绝变换（R1–R7）负向测试，以及别名身份／证据保留。
- [x] 添加真值表：一致正常→CONFIGURED；合格出现全部全文划线→STRUCK_OUT；范围内没有→MISSING；部分／未知／混合／冲突／歧义→UNRESOLVED。参数化真值表测试加专门的删除线、冲突与歧义测试；UNRESOLVED 保持状态未设置（CheckResult 领域不变量强制）。
- [x] 测试具体延时短语的 2s/3s、宽泛词歧义、空预期、别名不意味着描述等价。已确认示例解析为 CONFIGURED + DIFFERENT（绝非 MISSING）；不确定关联以 S6 原因令牌产生 NOT_COMPARED。
- [x] 只实现可独立测试的支持规则；保留原文和每次出现，不因排序丢掉冲突。matching.py 实现 S6 契约（带偏移映射的规范化、仅向前要求范围、范围级删除线覆盖、分类、独立比较）；每次出现按来源顺序保留，歧义证据带标记保留。
- [x] 相同输入／基准／规则重复核查，比较规范结果数据，排除偶然运行元数据。确定性测试在匹配层与应用层断言重复运行结果相等且来源顺序稳定。
- [x] 执行针对性／全项目检查，为误匹配加回归。245 项测试通过；ruff check、ruff format --check、mypy（strict）、pip check、git diff --check 全部通过。Task 2 摄取测试保持绿色；一项组合测试运行合成 DOCX → read_document → verify_document。

**验收：**功能检测、置信度、比较分开；没有模糊／语义兜底。不确定的关联或不支持比较可见，不假定正确。结果模型任何位置均无置信度分数（由测试断言）。取消按每（CheckItem, 块）检查；取消的运行返回显式 CANCELLED 结果且无结果集，绝不产生已完成的全 MISSING 报告。禁用条目不产生结果。规则版本 `task3-v1` 记录于每个 CheckResult。

## 任务 4 — Qt 审查工作区

**文件：**ui/main_window.py、application.py；tests/test_ui.py、tests/test_application.py。

- [x] 实现导入／运行／进度／取消、汇总、状态／待核查筛选、仅异常和搜索。导入与核查在后台 QThread 运行；不确定进度与取消按钮已接线；汇总计数、六个筛选与搜索已实现。
- [x] 列表／详情支持预期／实际、全部出现位置、删除线范围、相邻上下文。多证据选择器、预期/实际、匹配方式、审查原因与带范围高亮的前/当前/后块重建上下文均已就位。
- [x] 持续显示 LIMITED，MISSING 文案限定范围；失败／取消不冒充完成。"检查范围受限"提示在筛选与详情导航后仍可见；MISSING 文案限定于已检查范围。
- [x] 文档／基准变化使结果失效，阻止过期后台结果成为当前结果。操作代数 token 加文档 id 匹配门控 worker 完成；取消运行不显示最终计数。
- [x] widgets 留在 UI 线程，测试取消／生命周期；用最简单的已验证后台方式，不设核心服务器。worker 仅发出信号；UI 在 UI 线程应用结果。
- [ ] 在 Windows 验证键盘／焦点、中文、长描述、DPI，并查看目标尺寸截图。键盘导航与焦点已在 macOS 测试；Windows DPI/截图检查仍待执行。

**验收：**已配置＋差异与冲突待核查可区分；总计为三个状态加待核查；描述差异单独计数；缺失不虚构证据。浏览器仅作布局参考。

## 任务 5 — 基准管理与持久化

**前置证据：** 持久化验证实验已于（初次 2026-09-20，原子保存契约修正 2026-09-22）执行——见 `docs-zh/technical-spikes.md`。**选定格式：JSON 文件**（UTF-8、双临时文件原子保存：temp-new+fsync → copy primary→temp-backup+fsync → os.replace(temp-backup→.bak) → os.replace(temp-new→primary)——新 primary 安装前永不移动旧 primary；`.bak` 与 primary 同目录、`QStandardPaths.AppDataLocation/baseline.json`、严格 schema 校验、`schemaVersion = 1`、稳定 `item_id`／`alias_id`、加载时显式 `(data, source)` 返回元组）。56 项实验测试在 macOS 通过；同一套测试在 Windows CI 上作为门禁。

**文件：**baseline_store.py、application.py、__main__.py、ui/checklist_dialog.py、ui/item_editor_dialog.py、ui/main_window.py；tests/test_baseline_store.py、tests/test_checklist_ui.py、tests/test_ui.py、tests/test_startup.py。

- [x] 在 `src/baseline_store.py` 实现 JSON 加载／保存／重启，遵循 `docs-zh/technical-spikes.md` 中已验证的契约（保存算法、恢复策略、严格校验、失败语义）。双临时文件原子保存（新 primary 安装成功前永不移动旧 primary）、`.bak` 备份恢复（`source="backup"`）、严格 `schemaVersion = 1` 校验、`UnsupportedBaselineSchemaError` 在加载（不静默回退）与保存（拒绝覆盖更新版本的基准文件）两条路径上都区分兼容性失败与损坏数据，并拒绝空 `baseline_id`。保存→重启→加载往返保持相同 `baselineId`／`item_id`／`alias_id`。
- [x] 新增／编辑 code/name/detectionPhrase/category/expectedDescription/aliases/notes/enabled；拒绝重复 code，提示重复名称／重叠短语。ItemEditorDialog 强制必填字段、允许空 `expectedDescription`、编辑时保持稳定 `item_id`，并按出现次数保留别名 `alias_id`／`notes`（重复别名文本各自保留身份）。`validate_baseline` 将重复 code 作为错误拒绝，重复名称／重叠检测短语作为警告且须显式确认后才继续保存。
- [x] 提供禁用和确认删除，ID 稳定，允许空 expectedDescription。禁用／重新启用与删除（显式确认）只改动对话框工作副本；启用状态在编辑／保存／重启后保持。
- [x] 保存一套基准，使结果失效，重启重新加载；无订单／客户模板或同步。启动时从 `BaselineLoadResult.source` 显式记录基准状态（`normal`／`no-baseline`／`backup`／`load-error`／`unsupported-schema`）——绝不从错误字符串推断；保存失败保持对话框打开且候选内容完整，当前基准与结果不变；基准变更会提升操作代号，过期核查结果被丢弃。
- [ ] 结合分发格式检查免提权备份／替换。

**验收：**不用改源码即可维护基准；当前启用项决定核查；失败不默默丢编辑或损坏保存数据。

## 任务 6 — 历史验证与发布就绪

**产物：**脱敏标注语料、实测报告、回归夹具、已知限制。

- [ ] 独立于检测输出标注，包含歧义和不支持用例。
- [ ] 测精确率／召回率、误报／漏报、删除线准确率、待核查率、范围／不支持率、审查时间及分母。
- [ ] 把差异归类为提取、匹配、规范化、配置、规则或范围问题。
- [ ] 以回归测试修复约定的高影响问题，不为任意日期压缩验证。
- [ ] 声称就绪前与用户约定发布阈值和试点范围。

## 任务 7 — 无管理员 Windows 分发与试点

**产物：**已验证 PyInstaller onedir 便携包、发布说明、数据位置／替换说明、试点清单。Windows-only CI 提供候选包，是否可部署由 S3 验证。

- [ ] 在干净 Windows 10/11 x64 无管理员／安装权限、无开发运行时环境重复部署。
- [ ] 验证启动、选择／拖放、离线核查、基准持久化、中文／长路径、DPI、错误日志位置。
- [ ] 替换／升级／移除不默默删除基准；主动数据删除另行说明。
- [ ] 记录 IT／终端防护，不靠关闭控制或提权通过。
- [ ] 断网、无缓存前置依赖，测试离线传入、解压／安装、首次启动；分别测试 Python 3.8 保持不变和未安装 Python；目标机无下载、pip install 或在线激活。
- [ ] 获发布授权后才交付试点说明／限制，不自动发布、合并或打标签。

**验收：**普通用户能在两类 OS 用选定分发包；无需安装 Python/Qt；离线核查通过；替换后保留数据。不支持的 OS 构建／执行策略是明确阻塞，不能隐藏为例外。

## 进度与审查节奏

旧八周安排只是最初参考，不是可靠承诺。任务 1 的实验合计可能超过一个八小时工作周，后续切片在测量后估算，不能把全部保真／打包未知压进一周。每次工作结束交付可审查成果或明确差距。分支／PR 聚焦，更新测试和文档；合并／发布另需授权。

## 验证与完成定义

包配置已锁定 test/lint/type-check 工具，CI 在 macOS 和 Windows 执行。运行重点单元、夹具、小范围应用／Qt 测试后，再运行全套配置检查与 `git diff --check`。通过 CI 矩阵、浏览器模拟或生成 PyInstaller 产物都不能替代真实 DOCX 或干净 Windows 测试。

切片完成需要验收证据、明确失败／范围限制、文档行为一致、相关回归通过。试点还需历史指标／阈值和两类 OS 无管理员部署依据。AI、增强 fuzzy/diff、导出、人工验收、Word 集成与团队功能仍单独决策。

## 下一项授权决定

本次关闭技术选择并记录规则。任务 1 的 S1/S2 已执行并记录证据（2026-09-18，macOS；见
[technical-spikes.md](../docs/technical-spikes.md)）；任务 2（首个 DOCX 纵向切片）已于
同日经用户授权执行：在 macOS 开发机上"真实输入→真实块→可见来源"端到端成立。任务 1
的 S6（确定性规则与规模验证）已于 2026-09-19 执行并记录证据：Task 3 所需的确定性
规则已确立，无需发明产品策略。任务 3（确定性核查）已于 2026-09-20 经用户授权执行：
生产匹配引擎精确实现经 S6 验证的契约，245 项测试通过，含真实摄取组合测试。任务 4
（Qt 审查工作区）已于 2026-09-21 经用户授权以 13 个可审查子任务执行：完整审查
工作区（后台导入/核查、取消、过期结果抑制、汇总计数、排序、筛选、搜索、结果
详情、多证据、源上下文、LIMITED 提示、键盘导航）已实现，317 项测试通过且本地
全部质量门禁为绿。任务 5（基准管理与持久化）已于 2026-09-23 经用户授权在
分支 `task5-baseline-management` 上以可审查子任务加一轮修复实现：JSON 基准
存储（双临时文件原子保存、备份恢复、严格校验、加载与保存两条路径上的
不兼容 schema 防护）、清单管理与编辑工作区（稳定 item／alias 身份）、显式
启动恢复状态（no-baseline／backup／load-error／unsupported-schema）、保存
失败时保留候选编辑、结果失效与过期核查抑制。任务 1 剩余实验（S3）仍待
执行，需各自的授权及 Windows／样本访问；打包格式下的备份／替换验证与
干净机器／免提权部署证据仍留给任务 7 —— macOS／Windows 的 GitHub Actions
CI 为源代码级证据，不等于干净机器部署证据。建议的下个工作包为任务 6
（历史验证），等待明确执行授权。不重新开放技术栈，不自动开始下一个切片。

## 已确认的 Python 3.8 与完全离线环境

用户说明：公司电脑目前安装 **Python 3.8**，能否升级未知。这是现有环境事实，不表示已经选择应用／构建运行时版本。保留该安装及其 PATH／文件关联，不作修改。目标仍为 **Windows 10 和 Windows 11 x64**，使用者**没有管理员／安装权限**。**首次分发、解压／安装、首次启动和正常核查必须完全离线。**

计划的自包含包须携带经过验证的 Python／Qt／原生依赖，不调用电脑中的 `python`，不要求目标机执行 `pip install`、在线激活或下载。S3 必须断网、无缓存前置依赖，分别验证与现有 Python 3.8 共存且不改动它，以及未安装 Python 的干净电脑。目前没有分发包通过这些检查。

开发／构建环境是否可用仍是独立未决项：确认能否在不改变公司安装的条件下，使用获准的隔离／较新解释器及 Windows 构建机。不能认为 Python 3.8 的 `venv` 会升级解释器。如果唯一允许的构建／运行时就是 3.8，应先评估准确兼容依赖组合及维护影响，不能悄悄锁定旧包或改变技术栈。完全离线交付不代表已经确认构建机本身能否联网；需要单独记录，并在必要时准备离线构建依赖。
