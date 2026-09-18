# Python + PySide6 / Qt Widgets 技术验证

[English source](../docs/technical-spikes.md)

本文件为同名英文文档的对应中文版本；字段、状态、路径与命令保留原技术标识。

状态：**S1/S2 已于 2026-09-18 在 macOS 开发机上执行——见下方"已执行证据"。S3、S6 与持久化验证仍为已规划、未执行。**用户已选择生产技术栈并确认产品规则 1–7。目标为 Windows 10/11 x64、无管理员／安装权限。本文件规定所选栈内的有限验证，不授权进一步执行实验或生产实现。时间预算为投入上限，不是交付承诺；每周约可投入八小时。

开发和 CI 在 macOS／Windows 共用 Python 3.13／PySide6 源码；生产仍为
Windows 10/11 x64。Windows 包只在 Windows 构建，初始候选格式为
PyInstaller onedir 便携目录。该基础设施缩小 S3 范围，但不算干净电脑部署证据。

## 输入与执行顺序

准备脱敏的代表性 DOCX、独立工程师标注、干净的 Windows 10/11 x64 验证环境、具体 OS 构建版本，以及企业对便携／用户级程序的执行规则。首次分发、解压／安装、首次启动和核查必须完全离线。通过批准的离线渠道传入之前，分发包必须完整；目标电脑不得依赖在线下载或安装软件包。

S1/S2 前记录可用开发／构建解释器、权限、Windows 构建机及候选依赖版本。核对当前上游要求，不能尝试直接往 Python 3.8 安装最新版 PySide6。之后 S1/S2 共用夹具，并在大量 UI 工作之前执行 S3。S6 验证已经批准的规则，不重新询问部分删除线或冲突是否应待核查。不计划平行实现 .NET/Electron/Tauri。

| 实验 | 最小问题／验证 | 验收证据 | 投入上限与影响 |
|---|---|---|---|
| S1 OOXML 保真度 | 评估 Python 文档适配器，初步考虑 python-docx 加针对性的 OOXML 访问。提取正文／表格段落及 run，检查直接／继承删除线、显式 false、basedOn/defaults、双删除线，并单独识别修订。 | 原始文本、范围、有效删除线与格式来源符合独立标注；未知／不支持结构明确；不把 None 转 false；记录库／运行时版本及差距。 | 初始 4–8 h；在 Python 内选择适配方式，不建完整解析器。 |
| S2 来源与覆盖 | 遍历正文／单元格段落和嵌套／合并表格；合并拆分 run；将保守规范化文本映射回原始范围；发现排除的部分／结构。 | 同一快照内所有位置可还原；不跨单元格或段落拼接；明确合并单元格约定；不重复提取；如实表示 COMPLETE/LIMITED。 | 3–5 h，可与 S1 共用夹具；把关可追溯性。 |
| S3 无管理员 Windows 部署 | 在 Windows x64 用固定的 PyInstaller onedir spec 构建最小 Qt Widgets 应用，再在 Windows 10/11 x64 无开发运行时、无提权条件下测试完整便携目录。初始范围不含 installer 或 onefile。 | 普通用户可启动／核查／替换／移除；不依赖 UAC、Program Files、机器级写入；依赖随包；数据通过 Qt `QStandardPaths` 存放在可执行目录之外并保留。记录 OS、Python/Qt/PyInstaller 版本、体积、启动、中文路径／输入、DPI、终端策略。断网传入／部署／首次启动／核查必须通过，不使用缓存前置依赖；分别测试保留 Python 3.8 和未装 Python 的机器，记录 PATH／外部运行时依赖。 | Windows CI 可证明候选包成功构建且包含可执行文件，但 S3 仍需真实 Windows／IT 环境；失败阻塞该分发方式，不自动更换技术栈。 |
| S4 桌面／核心 IPC | 从旧候选比较中撤销。所选架构没有 sidecar 或核心服务器。 | 不引入协议或相关工作；响应性由 S6／Qt 验证。 | 0 h；只有新架构决定后才重启。 |
| S5 未来 DOCX 结构保留 | 延后的参考性实验：打开／保存副本，可选修改一个 run，比较包内部件及 Word 渲染。 | 记录样式／表格／关系的保留与损失；文本相同不等于无损；原件不变。 | 仅另行授权后 2–4 h；编辑仍不在 MVP 时不构成门槛。 |
| S6 确定性规则与规模 | 审查 detectionPhrase/aliases、关联要求范围；测试规范化白名单、冲突／部分删除线、歧义相似短语及代表性体积。 | 具体短语证明目标功能，宽泛词不算。数值／单位／否定保留。单处变化→CONFIGURED + DIFFERENT；有效值冲突、正常／删除线并存、部分／未知格式→UNRESOLVED。空预期／不支持比较→NOT_COMPARED。记录内存／时间／取消。 | 初始 3–5 h；复杂情况显式待核查，不隐藏启发式猜测。 |

## 已执行证据 — S1 与 S2（2026-09-18）

仅在 macOS 开发机上作为一个有限切片执行。不声称任何 Windows 运行时、干净电脑、打包运行时或真实客户文档证据。

环境（取自实际探测运行记录）：

- 操作系统：macOS 26.7（x86_64）；仅为开发平台，不是生产目标。
- Python 3.13.7；python-docx 1.2.0（含 lxml 6.1.3）；PySide6 6.11.2 已安装但探测未使用。
- 探测代码：`tests/docx_probe.py` —— 探索性适配器，刻意与 `src/` 中的生产占位模块隔离。
- 夹具：`tests/fixture_factory.py` 在每次测试会话中生成九个确定性合成文档
  （normal、table、nested-merged、strike-matrix、docdefaults-strike、
  tracked-revisions、excluded-parts、empty、malformed），其中 python-docx
  无法生成的情况使用小而有注释的原始 OOXML 补丁（dstrike、非法 strike 值、
  孤儿 rStyle、docDefaults 删除线、w:ins/w:del、w:sdt、文本框、隐藏的
  vMerge 续接内容）。
- 预期标注手写在 `tests/test_spike_s1_oxml_fidelity.py` 与
  `tests/test_spike_s2_locations_coverage.py` 中，不是复制探测输出。

### S1 — OOXML 保真度：观察结果

| 案例（夹具） | 预期（独立标注） | 观察 | 结论 |
|---|---|---|---|
| 正文段落文本、拆分 run、相邻同格式 run（normal） | 精确文本；连续的半开码点 run 偏移；空段落是零 run 块 | 一致 | 通过 |
| 直接删除线 true／显式 false（strike-matrix） | 来自 run rPr 的 True/False | `run.font.strike` 返回直接值 | 通过 |
| 部分删除线、混合 run（strike-matrix） | 逐 run 为 False/True/False | 一致 | 通过 |
| 经 basedOn 继承的样式删除线（strike-matrix） | True，来源为段落样式 | `run.font.strike` 为 None（API 看不到样式值）；元素级链式解析可行 | 通过——需要针对性 XML |
| 继承样式下显式 false 覆盖（strike-matrix） | False，直接值优先 | 一致 | 通过 |
| docDefaults 删除线（docdefaults-strike） | 经 rPrDefault 为 True；run 显式 false 覆盖 | 经元素级读取 `w:docDefaults` 一致 | 通过——需要针对性 XML |
| 双删除线 `w:dstrike`（strike-matrix） | 可检测；产品分类待定 | `font.double_strike` 为 True；探测保持有效删除线为 unknown，原因为 `double-strike` | 受限／待定问题 |
| 非法 `w:strike w:val="maybe"`（strike-matrix） | unknown，绝不为 false | python-docx 在 `font.strike` 上抛出 `InvalidXmlError`；探测归类为 unknown | 通过——保留 unknown |
| 孤儿 `w:rStyle` 引用（strike-matrix） | unknown | python-docx 的 `run.style` 静默回退到 "Default Paragraph Font"；探测自行检测孤儿引用并报告 unknown | 通过——仅靠 API 不安全 |
| 修订 `w:ins`/`w:del`（tracked-revisions） | 单独／不支持且明确 | `paragraph.runs`/`.text` 静默遗漏 ins/del 内容；探测将块标记为 LIMITED（`tracked-revisions-unsupported`）并排除修订文本 | 按设计受限 |
| 损坏输入（malformed） | 明确失败 | `PackageNotFoundError`；覆盖为 FAILED 并带错误信息、零块 | 通过 |
| 合法的空文档（empty） | COMPLETE、零块、无错误 | 一致；与 FAILED 区分 | 通过 |
| 原始字节不变（全部可读夹具） | 探测前后文件哈希一致 | 一致 | 通过 |

### S2 — 来源与覆盖：观察结果

| 案例（夹具） | 预期 | 观察 | 结论 |
|---|---|---|---|
| 正文段落序号；表格／单元格段落序号；嵌套表祖先路径（normal/table/nested-merged） | 稳定块 id（`body:pN`、`t0r1c1:table-cell:pN`、嵌套 `t0r2c1>t0r0c0:table-cell:p0`），单元格内局部段落序号 | 一致；重复探测结果相同 | 通过 |
| 多段单元格；不跨段／跨单元格拼接（table） | 各自独立的块 | 一致 | 通过 |
| 合并单元格（nested-merged） | gridSpan/vMerge 主单元格在其主网格位置只提取一次 | 朴素 `Table.rows[i].cells` 重复合并单元格（确认重复提取风险）；w:tc 级遍历使每个主单元格恰好提取一次 | 通过——需要针对性 XML |
| 带隐藏文本的 vMerge 续接（nested-merged） | 排除但明确 | 无块；覆盖为 LIMITED `merged-cell-continuation-content-excluded` | 通过 |
| 拆分 run 重建（全部） | 原始文本等于 run 文本拼接；连续半开偏移 | 每个块一致 | 通过 |
| 保守规范化＋原始范围映射（normal） | 仅折叠空白；规范化范围映射回精确原始偏移（"B C" → 原始 "B\tC" 位于 [3,6)） | 一致；折叠空白段映射到整个原始空白段 | 通过——白名单定稿推迟到 S6 |
| 排除结构（excluded-parts） | 页眉／页脚、正文级 `w:sdt` 段落与文本框文本被排除并给出明确 LIMITED 原因 | `doc.paragraphs` 静默遗漏 sdt／文本框内容；探测报告 `header-/footer-content-not-checked`、`content-control-content-excluded`、`textbox-content-excluded` | 通过 |
| 防重复（全部） | 块 id 唯一；合并文本只出现一次 | 一致 | 通过 |
| 覆盖诚实性（全部） | 无原因才 COMPLETE；有原因为 LIMITED；FAILED 与合法空文档区分 | 一致 | 通过 |

### 影响 Task 2 的发现

1. **选定适配策略：python-docx 1.2.0 ＋ 针对性 OOXML/XML 访问**（经
   python-docx 使用 lxml）。对声明的 MVP 范围足够：正文／表格／单元格段落、
   带码点偏移的 run、保留 unknown 的有效删除线、稳定位置、明确的覆盖警告。
   依赖已在 `pyproject.toml` 固定。
2. python-docx API 存在三个静默丢失风险，生产适配器必须补偿：
   `w:ins`/`w:del` 内的 run 不出现在 `paragraph.runs`/`.text`；
   `row.cells` 重复合并单元格；正文级 `w:sdt` 与文本框内容对
   `doc.paragraphs` 不可见。探测通过元素级遍历加明确 LIMITED 原因补偿；
   生产适配器必须同样处理。
3. 有效删除线不能只靠 `run.font.strike`（只有直接值；样式／docDefaults 值
   不可见；孤儿 rStyle 静默回退到默认字符样式）。需要按
   run rPr → 字符样式链 → 段落样式链 → docDefaults → 默认关闭 的顺序解析，
   非法值、孤儿／断链和双删除线保留 unknown。
4. 探测输出中每个 unknown 删除线都带有明确原因（测试断言）；unknown 绝不
   转换为 false。

### Task 2 修复 — 摄取／覆盖率证据（2026-09-18）

作为对 Task 2 切片的有限修复，在同一 macOS 开发环境执行（python-docx
1.2.0、lxml 6.1.3、PySide6 6.11.2、Python 3.13.7）。以下全部观察都由
`tests/fixture_factory.py` 中的手写标注回归夹具与 `tests/test_docx_adapter.py`、
`tests/test_application.py`、`tests/test_ui.py` 中的测试覆盖。

- **超链接包裹的 run 已被提取。** 观察：`paragraph.runs` 遗漏 `w:hyperlink`
  内的 run（python-docx 1.2.0 的 `paragraph.text` 包含它们，但 Task 2 适配器
  从 `paragraph.runs` 重建块文本，"Prefix [hyperlink text] suffix" 因此丢失
  中间 run 及其删除线）。`Paragraph.iter_inner_content()` 按文档顺序产出
  Run|Hyperlink，`Hyperlink.runs` 保留文本与直接删除线，适配器现在以连续
  偏移和已解析的删除线提取超链接 run；链接 URL 本身绝不进入文档文本。
  超链接内再嵌套超链接（无效 OOXML）对所有 run 访问器均不可见，产生
  `nested-hyperlink-content-excluded` 而非静默丢失。
- **页眉／页脚变体已被检测。** 观察：首页／偶数页页眉页脚（`w:titlePg`、
  奇偶页设置）及仅含表格的页眉／页脚内容此前被遗漏。现在全部六种变体都
  检查段落与表格内容；每一侧在所有变体上保持一个稳定 token
  （`header-content-not-checked` / `footer-content-not-checked`），且内容
  绝不进入正文块。读取 linked-to-previous 容器的 `.paragraphs` 会在内存包中
  创建页眉部件，因此适配器在任何内容访问前先检查 `is_linked_to_previous`。
- **已知不支持结构强制 LIMITED。** 观察 `paragraph.runs` 中的静默丢失：
  `w:fldSimple` 缓存结果 run 与 `w:smartTag` 包裹的 run。复杂字段 run
  （`w:fldChar`/`w:instrText`）产生空文本 run，其字段结果（段落直接子级）
  保持提取。适配器现在以稳定 token 检测 `w:instrText`、`w:fldSimple`、
  `w:footnoteReference`、`w:endnoteReference`、`w:smartTag` 与正文级
  `w:altChunk`（`field-code-content-excluded`、
  `footnote-or-endnote-content-excluded`、`smart-tag-content-excluded`、
  `alt-chunk-content-excluded`）；它们都不会产生静默 COMPLETE 结果。不尝试
  字段求值、脚注或 altChunk 提取。
- **默认段落样式从标记解析，而非 id。** 默认段落样式是带
  `w:type="paragraph"` 与 `w:default="1"` 的 `w:style`（随附模板标记的是
  "Normal"；以 `CorpBody` 为默认 id 的夹具正确解析继承删除线）。标记缺失或
  歧义时不虚构默认样式，链回退到 docDefaults。
- **读取失败类别。** `file-access-error`（读取时 OSError）、
  `invalid-or-unreadable-document`（BadZipFile、缺失包部件、无效 XML——包括
  Word 为密码保护文档生成的 OLE 复合文件容器，由确定性
  `build_ole_container` 夹具演练），以及 `unexpected-parser-error`（注入的
  收集 bug 归入自身类别，绝不误标为无效文档）。删除线解析外围的宽泛
  `except Exception` 已移除：`w:strike`/`w:dstrike` 按元素级读取，非法
  ST_OnOff 值归类为带原因的 unknown，不再捕获程序员错误。
- **预览空白。** Qt 富文本引擎会折叠普通 `<p>` 元素中的连续空格
  （"A  B\tC" 渲染为 "A B C"）；run 段落现在使用
  `white-space: pre-wrap`，并经 QTextDocument 往返测试验证。领域文本不变。
- **Windows 构建。** 源码级 CI（macOS + Windows，Python 3.13）覆盖修复
  提交；手动触发的 PyInstaller 工作流（`build-windows.yml`）本切片**未
  运行**，仍待执行（见实施计划）。这不构成 S3 证据。

### 未探测／剩余限制

- 表格样式字符格式、链接样式、`w:rPrChange` 修订格式、隐藏文本
  （`w:vanish`）、批注、块级 `w:customXml`、超大文档。
- 加密／密码保护 DOCX：仅演练了 OLE 容器格式失败路径（显式导入失败）。
  不存在解密能力，也未验证真实 Office 生成的加密文件。
- 仅在 macOS 上使用合成夹具；无脱敏真实客户文档，除 CI 外无 Windows 执行。
  CI 会在 windows-latest 上运行相同测试，但仍不构成 S3 部署证据。
- 规范化白名单刻意最小（仅空白折叠）；标点／全半角映射仍为 S6 输出。
- 投入：S1/S2 在单个有限会话内完成，处于 S1+S2 合并时间预算指引之内；
  本次修复是第二个有限会话。

### 未决问题

- `w:dstrike` 的产品含义：双删除线应算删除格式（struck）还是保持独立的
  unknown？探测当前报告 unknown。
- `w:ins`（修订插入）内的文本是否应包含在提取的块文本中？当前排除并给出
  LIMITED 原因。

**Task 2 状态：已解除阻塞。** 文档访问策略已凭证据确立；Task 2（首个 DOCX
垂直切片）可在此基础上实现，等待明确授权。

## 所选栈内的持久化验证

实现基准持久化前，比较足够支撑一套基准的最小本地格式。验证稳定 ID、必填 detectionPhrase、Unicode、原子保存／恢复、权限失败、schema 标识和重启。使用程序文件之外的用户可写应用数据目录，不建共享数据库服务。用简短决策记录选定格式，初始上限 1–2 h；不增加多基准或版本管理。

## 夹具与证据

起点为 normal.docx、table.docx、strikethrough.docx、partial-strikethrough.docx、mixed-runs.docx、alias-match.docx、missing-function.docx、description-difference.docx。增加继承删除线覆盖、正常／删除线并存、正常值冲突／一致重复、歧义宽泛短语、嵌套／合并表格、跨段要求、修订、排除部分、损坏／受保护及大文件。合成夹具隔离行为，脱敏历史文件验证代表性。

比较实现输出前，独立标注功能身份、要求范围、格式、位置、resolution 和 coverage。受保护／损坏输入须明确失败。限制 ZIP/XML 资源使用，避免拉取外部关系；不因此引入基础设施。

每个执行过的实验记录假设、准确版本／环境、夹具身份、实际输出、逐项 pass/fail/unknown、投入时间和剩余限制。到时间上限停止，报告差距并商定后续。技术栈获准不等于实验通过，未经用户新决定不更换框架。

## 已确认的 Python 3.8 与完全离线环境

用户说明：公司电脑目前安装 **Python 3.8**，能否升级未知。这是现有环境事实，不表示已经选择应用／构建运行时版本。保留该安装及其 PATH／文件关联，不作修改。目标仍为 **Windows 10 和 Windows 11 x64**，使用者**没有管理员／安装权限**。**首次分发、解压／安装、首次启动和正常核查必须完全离线。**

计划的自包含包须携带经过验证的 Python／Qt／原生依赖，不调用电脑中的 `python`，不要求目标机执行 `pip install`、在线激活或下载。S3 必须断网、无缓存前置依赖，分别验证与现有 Python 3.8 共存且不改动它，以及未安装 Python 的干净电脑。目前没有分发包通过这些检查。

开发／构建环境是否可用仍是独立未决项：确认能否在不改变公司安装的条件下，使用获准的隔离／较新解释器及 Windows 构建机。不能认为 Python 3.8 的 `venv` 会升级解释器。如果唯一允许的构建／运行时就是 3.8，应先评估准确兼容依赖组合及维护影响，不能悄悄锁定旧包或改变技术栈。完全离线交付不代表已经确认构建机本身能否联网；需要单独记录，并在必要时准备离线构建依赖。
