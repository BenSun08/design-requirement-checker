# Design Requirement Checker — 内部演示状态

[English source](../docs/demo-readiness.md)

本文件为同名英文文档的对应中文版本；字段、状态、路径与命令保留原技术标识。

**状态日期：** 2026-09-23 · **分支基准：** `main` 提交 `96bfe48`（PR #8 已合并，CI 绿色）

## 里程碑

**v0.1 内部演示（Internal Demo）。** 本里程碑的含义是：一个稳定、可用的内部
演示。它明确**不**意味着：生产就绪（Production Ready）、发布已验证（Release
Validated）或试点批准（Pilot Approved）。

## 已实现的演示能力

以下各项均存在于 `src/design_requirement_checker/` 生产源码中，并由仓库测试
套件覆盖：

- **DOCX 导入**：python-docx 1.2.0 ＋ 针对性 OOXML/lxml 访问
  （`docx_adapter.py`）；绝不修改源 `.docx`。
- **段落／表格来源定位**：快照内稳定坐标。
- **有效删除线解释**：沿完整样式链解析（run → 字符样式 → 段落样式 → 默认
  样式 → docDefaults）；未知格式保持未知。
- **COMPLETE / LIMITED 覆盖**：已知不支持结构（修订、文本框、域代码、脚注／
  尾注引用、智能标记、`w:altChunk`、被排除的页眉／页脚内容、嵌套／无效超
  链接）强制 LIMITED 而非静默消失。
- **确定性匹配**（`matching.py`）：精确／规范化（经 S6 验证的 N1–N3 白名
  单）／别名检测，带原文可追溯性；仅向前要求范围关联，带显式不确定性原因。
- **证据**：保留所有合格出现（按来源顺序）；`primary_evidence_id` 仅是初始
  UI 选择辅助。
- **结果**：`CONFIGURED`／`MISSING`／`STRUCK_OUT` 三状态加独立
  `UNRESOLVED` 决议（状态未设置）；描述比较 `SAME`／`DIFFERENT`／
  `NOT_COMPARED` 为独立正交维度。
- **多证据查看与源上下文查看**（Qt 审查工作区 `ui/main_window.py`）：汇总
  计数、优先级排序、筛选（全部/已配置/未配置/已划除/待人工核查/仅异常）、
  搜索、详情面板（预期与实际、匹配方式、原因、重建的前/当前/后块上下文）。
- **后台导入与核查**：脱离 UI 线程运行，协作式取消（`threading.Event`）与
  过期结果抑制（操作代数 token）。
- **本地基准管理**（`ui/checklist_dialog.py`、`ui/item_editor_dialog.py`）：
  新增／编辑／禁用／确认删除；重复 code 拒绝；重复名称／重叠检测短语提示；
  稳定 `item_id`／`alias_id`。
- **原子 JSON 持久化**（`baseline_store.py`）：`QStandardPaths.AppDataLocation /
  baseline.json`、`schemaVersion = 1`、双临时文件原子保存、`baseline.json.bak`
  备份恢复、严格校验、加载与保存两条路径上的不兼容 schema 防护。
- **Windows PyInstaller onedir 构建**：手动触发的 `build-windows.yml`
  工作流产出 `dist/DesignRequirementChecker/DesignRequirementChecker.exe`。

## 演示证据

- **源代码级 CI**：GitHub Actions 在 `macos-latest / Python 3.13` 与
  `windows-latest / Python 3.13` 上运行完整测试／lint／格式／类型套件；
  `main` 提交 `96bfe48` 为绿色。
- **Windows PyInstaller 工作流**：`build-windows.yml` 存在并构建＋上传
  onedir 产物（手动触发）。
- **用户手动冒烟检查**：用户下载了 Windows 可执行产物并在公司电脑上成功
  运行。此项仅记录为**演示冒烟检查**。该次运行的操作系统版本、管理员状态、
  网络状态、终端策略状态与 Python 存在与否均未单独记录，不得推断。

## 延期验证（DEFERRED FOR DEMO MILESTONE）

以下各项**不是**当前内部演示里程碑的要求，但在声称生产／试点就绪之前仍是
前置条件。

**正式任务 6 证据 — 延期：**

- 真实／脱敏、独立标注的历史语料
- 实测精确率／召回率
- 实测删除线准确率
- 实测比较准确率
- 实测待核查／覆盖率
- 实测审查时间变化
- 发布阈值批准

`validation/` 下的任务 6 评测工具保留在仓库中供未来使用；其未产生任何实测
指标（所有指标 NOT MEASURED，分母 0）。

**正式任务 7 / S3 验证 — 延期：**

- 干净 Windows 10 验证
- 干净 Windows 11 验证
- 标准用户／免提权验证矩阵
- 未安装 Python 电脑测试
- 公司 Python 3.8 保持不变共存矩阵
- 完全离线干净电脑测试
- 企业终端防护／策略验证
- 应用替换／升级后数据保留验证
- 正式错误日志位置验证

**既有手动验证缺口 — 延期：**

- 正式 Windows DPI 矩阵
- 正式中文输入验证矩阵
- 正式长描述布局矩阵

## 演示限制

- 尚无实测历史精确率／召回率。
- 无正式生产发布阈值。
- 无干净电脑部署矩阵。
- 无报告导出（V0.2 候选）。
- 无模糊或语义匹配（按设计仅确定性规则）。
- 不支持的 Word 结构产生 LIMITED 覆盖提示而非结果。
- 不自动跨段落或表格单元格拼接要求文本。
- 无自动工程验收：工具呈现证据与不确定性，由人工审查者决定。

## 最终演示状态

| 领域 | 状态 |
|---|---|
| DOCX 摄取 | PASS |
| 确定性核查 | PASS |
| Qt 审查工作区 | PASS |
| 基准管理 | PASS |
| 本地持久化 | PASS |
| 源代码级 macOS CI | PASS |
| 源代码级 Windows CI | PASS |
| Windows 便携构建工作流 | AVAILABLE |
| 用户手动 Windows 演示冒烟测试 | PASS — 用户报告 |
| 历史实测验证 | DEFERRED |
| 干净电脑 Win10/11 验证 | DEFERRED |
| 免提权／离线正式验证 | DEFERRED |
| 发布阈值 | DEFERRED |
| 报告导出 | OUT OF SCOPE / V0.2 |

`PASS` 仅用于确有证据之处（测试套件、CI 运行或用户报告的手动运行）。本表
任何一项都不声称部署认证。
