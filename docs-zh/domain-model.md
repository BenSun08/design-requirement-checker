# 技术中立的领域模型

[English source](../docs/domain-model.md)

本文件为同名英文文档的对应中文版本；字段、状态、路径与命令保留原技术标识。

状态：已与用户确认的产品规则及 Python + PySide6 / Qt Widgets 对齐。领域概念保持独立于 UI；Qt 对象仅属于展示层。权威规则见 product-spec.md，待验证事项见 technical-spikes.md。

## 领域概念

| 概念 | 字段／含义 |
|---|---|
| CheckItem | id（稳定标识）、code（唯一）、name（规范显示名称）、detectionPhrase（必填、工程师维护的匹配短语）、category、expectedDescription（可选）、aliases[]、enabled、notes |
| CheckItemAlias | id、text、notes；从属一个 CheckItem，是 detectionPhrase 的替代形式；保留实际命中的别名，不自动证明描述等价 |
| Document | id、filename、contentFingerprint、blocks[]、ingestionState、supportedScope、coverage（COMPLETE/LIMITED）、warnings；表示不可变输入快照 |
| DocumentBlock | id、type（正文段落／单元格内段落）、text（重建的原始文本）、runs[]、location；不跨单元格连接 |
| TextRun | text、startOffset、endOffset、effectiveStrike（true/false/unknown）、可选格式元数据和格式来源；适配器可保留 OOXML 直接／样式属性 |
| DocumentLocation | documentId、blockId、blockType、part、paragraphIndex，以及可选 tableIndex/rowIndex/cellIndex、祖先表格路径 |
| CheckResult | 检查项快照、documentId、resolution（RESOLVED/UNRESOLVED）、status（CheckStatus 或空）、evidence[]、primaryEvidenceId、comparisonState、reviewReasons[]、ruleRevision |
| CheckStatus | CONFIGURED、MISSING、STRUCK_OUT；描述文档证据，不表示置信度或验收 |
| MatchType | 初期 EXACT、NORMALIZED、ALIAS；FUZZY、MANUAL、SEMANTIC 留待单独批准 |
| MatchEvidence | id、文档／块身份、locations[]、rawText、matchedSpan(s)、requirementSpan(s)、matchedTerm、适用时 aliasId、matchType、transformations[]、可选 score、strikeCoverage、explanation |

一次核查归集文档身份、启用项基准快照、规则版本、生命周期（ready/running/completed/failed/cancelled）和结果。失败／取消不是已完成的未配置报告。MVP 不要求保存核查历史。核查还包括独立于完成／失败状态的 coverage 与 coverageReasons；COMPLETE 只针对声明的 MVP 范围，不代表所有 Word 特性。受限核查可以有结果，但计数和未发现声明必须限定于已检查范围。

## 不变量与语义

- 不用规范化文本替换原文。通过规范化映射，让匹配范围对应回原始块偏移。
- 概念偏移以 Unicode code point 计数，使用半开区间 [start,end)。适配器显式转换 UTF-16/code-unit 偏移，不能假定不同运行时计数相同。
- 内部坐标从 0 开始，UI 从 1 开始。paragraphIndex 相对所属正文／单元格。位置只在对应快照内稳定，文档编辑后不承诺保持。
- 单元格可有多个段落块；嵌套表格需要祖先坐标，不能只用平面的 tableIndex。合并单元格的原点约定须验证。
- 每条证据具有非空范围和可解析来源。保留多个候选。MISSING 没有被接受的证据；未来可单独展示被拒绝候选。
- effectiveStrike 根据实际格式、继承和覆盖解析；unknown 不能默认为 false。修订删除是另一种文档特性。
- strikeCoverage 为 NONE/FULL/PARTIAL/UNKNOWN，作用于匹配要求范围，不是整个段落。全部合格出现位置均为 FULL 才允许 STRUCK_OUT；PARTIAL/UNKNOWN、正常／划线并存、关键值冲突为 UNRESOLVED。还要检查关联要求范围，避免匹配短语正常却忽略被删的限定条件。
- RESOLVED 必须有且只有一个 CheckStatus；UNRESOLVED 没有 CheckStatus。该约定已确认，UI 为“待人工核查”，既不是第四个 CheckStatus，也不是置信度。
- 预期描述比较与功能检测独立。允许 CONFIGURED + DIFFERENT。空 expectedDescription 对应 NOT_COMPARED。
- 可选 score = {kind, value, scale, algorithm}；不存在不等于零。exact/alias 不表示经校准的置信度。
- 完成核查时，三个已判定状态计数加待人工核查等于启用项数。禁用项排除；筛选只改变显示行。
- 修改基准使结果失效，旧证据不能绑定到新预期内容。

## 检测与证据边界

- name 是显示标签，detectionPhrase 独立定义检测文本；code/name/detectionPhrase 必填。不从 name 自动提取短语。
- EXACT 字面比较 detectionPhrase；NORMALIZED 使用批准的转换；ALIAS 记录替代短语及转换。宽泛关联词不能证明更具体功能。
- matchedSpan(s) 指原始检测文字；requirementSpan(s) 指用于删除线和描述比较的关联要求。MVP 中范围均限于一个段落（包括单元格内段落）。S6 验证关联边界，不确定时明确提示，不能默默扩大到整段或整张表。
- 多次出现按原文顺序保留。主证据只为显示方便，没有权威优先级。正常／删除线并存、部分／未知格式、有效关键值冲突先判 UNRESOLVED。
- 保守规范化保留原始偏移、数值、单位、否定和条件；不跨段落／单元格连接。转换白名单须验证，不暗含任意去标点。
- 工程师维护一套本地基准，启用项决定下次核查。禁用项仍保存但不参与。不引入订单模板或共享基准层级。

## 示例

生产示例（不修改历史模拟夹具）：DR-006 的 name 为 `2门控制延时`，detectionPhrase 为 `2门控制增加开关门延时`，expectedDescription 为 `2门控制增加开关门延时2s功能`。

正常段落 `2门控制增加开关门延时3s功能` 包含该 detectionPhrase。结果为 RESOLVED、CONFIGURED、DIFFERENT，matchType 为 EXACT，没有 score。证据分别记录检测范围和关联要求范围。位置为 tableIndex 2、rowIndex 6、cellIndex 1、paragraphIndex 0；UI 为表3／行7／单元格2／段1，比较显示 `2s → 3s`。

若同时存在正常的 `2s` 与 `3s` 要求，则 UNRESOLVED 并展示两处。正常与全文删除线并存同样待核查。单处要求部分划线也待核查。空 expectedDescription 为 NOT_COMPARED；别名命中不自动表示描述相等。

旧浏览器夹具中较宽泛的 `2门控制` 解释，不是批准的生产检测规则；该差距记录在 prototype-verification.md。

## 概念边界

展示层呈现输入和证据；应用／用例层协调导入、核查和基准编辑；领域层负责匹配／分类规则及不变量；文档／持久化适配器读取 OOXML、保存基准。领域层不依赖 UI、Office、网络或文件系统。这些边界可存在于同一进程模块中，不意味着需要服务、通用 repository、插件或 IPC。

## 映射到所选技术栈

领域与应用契约使用 Python 值；Qt Widgets 和 signals 将其适配为展示。DOCX／持久化依赖留在适配器中。应用为单一本地桌面进程；后台工作不能从 UI 线程之外更新 widgets。不计划独立核心服务、HTTP 服务器、QML 或内嵌 Web 前端。存储格式、具体类及依赖版本属于验证产物，不是新增领域实体。所有可变数据都必须位于普通 Windows 用户可写、且在程序安装目录之外的位置。

## 已确认的 Python 3.8 与完全离线环境

用户说明：公司电脑目前安装 **Python 3.8**，能否升级未知。这是现有环境事实，不表示已经选择应用／构建运行时版本。保留该安装及其 PATH／文件关联，不作修改。目标仍为 **Windows 10 和 Windows 11 x64**，使用者**没有管理员／安装权限**。**首次分发、解压／安装、首次启动和正常核查必须完全离线。**

计划的自包含包须携带经过验证的 Python／Qt／原生依赖，不调用电脑中的 `python`，不要求目标机执行 `pip install`、在线激活或下载。S3 必须断网、无缓存前置依赖，分别验证与现有 Python 3.8 共存且不改动它，以及未安装 Python 的干净电脑。目前没有分发包通过这些检查。

开发／构建环境是否可用仍是独立未决项：确认能否在不改变公司安装的条件下，使用获准的隔离／较新解释器及 Windows 构建机。不能认为 Python 3.8 的 `venv` 会升级解释器。如果唯一允许的构建／运行时就是 3.8，应先评估准确兼容依赖组合及维护影响，不能悄悄锁定旧包或改变技术栈。完全离线交付不代表已经确认构建机本身能否联网；需要单独记录，并在必要时准备离线构建依赖。
