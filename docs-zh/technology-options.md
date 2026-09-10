# 生产技术决策与历史备选方案

[English source](../docs/technology-options.md)

本文件为同名英文文档的对应中文版本；字段、状态、路径与命令保留原技术标识。

**用户已决定：Python + PySide6 / Qt Widgets（方案 A）。** Windows 10/11 x64，普通用户无管理员／安装权限。以下比较保留 2026-09-10 的调研基线，作为历史依据，不是开放候选清单或新的验证。没有构建候选引擎或 Windows 包。此决定来自用户明确选择，不代表实验通过。浏览器原型仍可抛弃。

## 历史决策背景与矩阵

项目要求 Windows 桌面、本地离线 DOCX、中文工程文本、高密度审查界面、可解释确定性检查，以及每周约八小时开发。当时开发者熟悉度和企业设备策略未知；用户此后选择 A 并确认无管理员 Windows 目标，剩余策略用于部署验证，不自动重新排名。AI 权重低。所有候选均可在不设服务的情况下区分展示／应用／领域／适配器。

权重为定性顺序：**关键**可否决方案，**高**显著影响可持续交付，**中**用于接近方案的比较，**低**表示可选未来价值。不计算数值总分，因为差异尚不可精确测量。“强”表示可信适配度，不是已验证正确性。

| 标准 | 权重 | A Python + PySide6 | B Electron + TS/Node | C Electron + Python 核心 | D Tauri + Web UI | E C#/.NET + WPF（WinUI 变体） |
|---|---|---|---|---|---|---|
| OOXML 保真与追溯 | 关键 | 可行，需样式解析 | 需底层 XML，适配工作较多 | 同 A 的 Python 风险 | Rust/XML 或 sidecar，不确定性较高 | 强类型 OOXML 访问，仍需解析样式 |
| 每周 8 h 可持续性 | 高 | 熟悉 Python 时强 | 熟悉 Web/Node 时好 | 两运行时及契约负担较大 | 无 Rust 经验时较弱 | 熟悉 C# 时强，否则需学 XAML |
| 密集桌面审查 UX | 高 | Qt Widgets 适合 | 强，需 Web 无障碍工作 | 同 B | Web UX 强 | WPF 控件／绑定适合 |
| 离线 Windows 安装 | 高 | 可行，需冻结／安装验证 | 分发成熟，运行时较大 | 打包两套运行时 | 验证 WebView2 离线可用性 | 适合，需选运行时／自包含形式 |
| 调试／交接 | 高 | 一门应用语言加 Qt 模型 | TS 加主／渲染进程边界 | TS/Python 进程生命周期 | TS/Rust，可能再加 Python | C# 加 XAML、.NET 约定 |
| 确定性单元测试 | 高 | 强 | 强 | 核心强，另测 IPC | 强，另有混合工具链测试 | 强 |
| 体积 | 中 | 携带 Python/Qt，须测量 | 携带 Chromium/Node，基础体积可能最大 | B 再加 Python | 外壳可小，但计入 WebView2 | 依赖运行时／自包含的权衡 |
| Windows/Office 集成 | 中 | 可经适配器 | 可行，额外集成 | 可经 Python | 额外工作 | 生态最直接 |
| 未来 NLP/AI | 低 | 方便调用 Python 库 | TS/API，不要求 AI | 方便调用 Python 库 | Rust/TS/API 或 sidecar | .NET/API，不要求 AI |

各方案均支持本地文件对话框、文件访问、拖放和 Unicode；中文 IME、字体、长路径、DPI 和密集选择交互须在 Windows 验证。未提供实际杀毒误报排名或精确安装体积。

## A — Python + PySide6 / Qt Widgets

**架构：**一个桌面应用，Python 应用／领域／适配器，Qt Widgets 展示；必要时后台处理以维持响应，不设独立服务。该 UI 不需要 QML 或内嵌 Web 引擎。

**优势：**一门主要应用语言，便于文本／夹具处理，有成熟桌面控件；Python 领域无需 UI 即可测试。Qt 提供官方 Python 绑定，部署工具可输出 Windows 可执行文件。[Qt for Python](https://doc.qt.io/qtforpython-6/index.html)、[pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)。

**待验证的 DOCX 策略（未选库）：**考虑 python-docx 处理段落／表格／run，模型不够时补充针对性 OOXML 访问。`Font.strike` 是三态，不能把 `None` 当 false。原型式纯文本提取不够，须验证格式继承和范围映射。[python-docx 文本 API](https://python-docx.readthedocs.io/en/latest/api/text.html)。

**不足／风险：**Qt model/view 和 signals 有学习成本；依赖冻结、插件收集、运行时错误需要桌面测试。高级库支持不等于完整 Word 保真。所用 Qt 组件的打包／许可审查属于实验，不能假设分发没有成本。

**复杂度：**相对较低至中等，前提是熟悉 Python；继承格式可能成为主要工作。**打包：**历史比较设想为冻结目录或可执行文件，再封装安装程序，携带运行时，用户无需装 Python；先人工分发签名版本，更新器以后再决定。当前无管理员／完全离线硬约束以下文为准。**未来：**Python 文本／NLP／文档生成自然扩展，但文档往返保真仍须证明。

## B — Electron + React + TypeScript + Node.js

**架构：**renderer 展示、窄 preload/IPC 边界、main／应用协调及 Node OOXML／领域适配器；CPU 工作可能需要 worker。即使只写 TypeScript，Electron 也已是多进程。[Electron 进程模型](https://www.electronjs.org/docs/latest/tutorial/process-model)。

**优势：**灵活分栏／列表／详情 UI，常见 Web 工具和测试生态，Node 核心可统一应用语言；维护者以 Web 为主时有竞争力。

**DOCX：**用 ZIP/XML 适配器保留 run／样式／来源。纯文本或 HTML 转换器并不自动提供可靠证据模型；Mammoth 聚焦语义 HTML 而非精确样式，raw-text 提取忽略格式。不能未经保真验证就当作完整解析器。[Mammoth 文档](https://github.com/mwilliamson/mammoth.js)。

**不足／风险：**Chromium/Node 体积和更新，renderer/main 调试，文档衍生内容被错误赋权；自定义 OOXML／样式代码可能多于 A/E。文档文字应保持惰性，renderer 隔离，本地文件访问边界收紧。[Electron 安全指导](https://www.electronjs.org/docs/latest/tutorial/security)。

**复杂度：**中，需大量自定义保真处理时提高。**打包：**Electron 包加 Windows 安装程序，可能用 Forge；携带 Chromium/Node 换取一致性，但体积更大。[应用打包](https://www.electronjs.org/docs/latest/tutorial/application-distribution)。**未来：**TS 文本工具和 API 可继续使用；加入 Python sidecar 就变为 C，需新理由，不能悄悄引入。

## C — Electron + React/TypeScript + Python 核心

**架构：**Electron 展示／main，在本地启动 Python 进程处理导入／匹配／持久化，通过有限本地 IPC 通信，无需 HTTP 服务器。基准持久化只有一个拥有者，不能重复实现。

**优势：**Web UI 配合 Python 文档／文本生态，Python 领域独立可测。**DOCX：**同 A 的策略与不确定性；增加进程不会提高解析正确性。

**不足／风险：**两套语言／工具链，打包两运行时；启动／退出、取消、协议错误、请求身份、Unicode、大结果、崩溃恢复、版本兼容。避免把文件路径拼成 shell 命令。进程隔离有助限制故障，但会增加运行维护工作。

**复杂度：**每周八小时背景下相对 A/B/E 高。**打包：**每种架构的 Electron 安装包携带 Python 可执行及依赖，应用／核心原子更新；预计体积最大但未实测。**未来：**只有真实共享核心或不可替代 Python 功能才值得，不能只为假想 AI 选择。

## D — Tauri + React/TypeScript

**架构变体：**①受限原生边界提供文件字节，TS 处理文档；②Rust 文档／领域后端＋Web UI；③Python sidecar＋Rust/Tauri 桥接。三者成本不同，不能共用一个乐观评分。

**优势：**Web 审查界面，外壳可能较小；原生能力受约束，有 Windows 安装工具。**DOCX：**按变体使用 TS ZIP/XML、Rust ZIP/XML 或 A 的 Python 策略，本项目均未验证。

**不足／风险：**即使少写 Rust 也有构建工具链与平台配置；Web／原生调试；离线受管设备需解决 WebView2。Python sidecar 再加第三生态，削弱体积和简洁优势。Tauri 提供 MSI/NSIS 和包括离线形式的 WebView2 安装模式。[Windows 安装](https://v2.tauri.app/distribute/windows-installer/)。外部二进制需平台专用配置和打包。[Sidecar](https://v2.tauri.app/develop/sidecar/)。

**复杂度：**TS/Rust 中至高，加 Python 则高。**打包：**MSI 或 NSIS，明确 WebView2 策略，比较体积时包含离线运行时。**未来：**可以扩展，但当前需求不足以证明额外语言必要；只有体积或团队现有经验显著时考虑。

## E — C# + .NET + WPF / WinUI

**架构：**单个桌面应用，C# 应用／领域／适配器，XAML 展示。WPF 有桌面控件、数据绑定，运行于 Windows。[WPF 概览](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/overview/)。

**优势：**直接适配 Windows 生态，成熟密集数据 UI，强类型 Open XML SDK，企业维护惯例清晰，便于交给 .NET 工程师。

**DOCX：**Open XML SDK 遍历段落／表格／run／包部件，自行保留位置映射与有效格式策略。强类型元素是结构访问，不提供 Word 布局或自动规则判定。Microsoft 文档说明删除线涉及样式层级继承。[文档结构](https://learn.microsoft.com/en-us/office/open-xml/word/how-to-open-and-add-text-to-a-word-processing-document)、[Strike 语义](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.strike?view=openxml-3.0.1)。

**不足／风险：**不熟悉时要学 C#/XAML/绑定；自定义 diff 和 OOXML 语义工作仍存在。WPF 仅 Windows，符合本项目但限制跨平台。**WinUI 变体：**通过 Windows App SDK 提供现代 Windows UI，却增加部署／工具选择；对密集 MVP 相比 WPF 没有明确优势，只有需 Windows App SDK 集成时再验证。[WinUI 3](https://learn.microsoft.com/en-us/windows/apps/winui/winui3/)。

**复杂度：**熟悉 .NET 时低至中，学习时中。**打包：**依赖已管理运行时或较大自包含包，再与 IT 选择安装器／MSIX；单文件可执行本身不是安装器。[.NET 发布](https://learn.microsoft.com/en-us/dotnet/core/deploying/)。**未来：**文档生成／Windows 集成适合，AI 不一定需要 Python；Word COM 若批准，会增加 Office 部署／版本约束。

## 跨方案运行评估

- 在同一 Windows 和夹具上测安装包／安装后大小、冷启动、内存、响应性，不把通用 MB 数字当项目估计。
- 在无开发运行时、无网络、普通权限下测试中文文件名、锁定文件、企业终端防护。
- 历史建议是 IT 接受时人工分发签名安装包；每种栈的自动更新都增加连接、信任、回滚、基准保留工作。
- 杀毒误报与 Windows 信任提示不同。签名有价值，但不保证每种策略都接受，须测试实际组织环境。[Microsoft 签名指导](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control)。
- Codex 可协助各候选，但不能凭此声称效率倍数或免除 OOXML／打包验证。一套工具链和可查看的夹具更便于审查辅助生成内容。

## 已确认决策与影响

**已选：**Python 应用／领域／适配器，PySide6 Qt Widgets 展示，一个本地桌面进程。不采用 Electron、生产 React 前端、Tauri/Rust、C#/.NET、Python sidecar、QML 或内嵌 Web。可按需后台执行，但不意味着独立核心服务。

该选择对应文档／文本工作流、紧凑桌面 UX，以及更少的维护语言和进程。E 是历史最强替代，不是并行实现轨道。严重验证失败必须带证据和有限修复建议报告；更换栈须用户新决定。

### 强制部署约束

- Windows 10/11 x64。具体构建版本须与最终 Python/Qt 组合核对，不声称支持全部历史 Windows 构建。
- 用户无管理员／安装权限。要求提权、安装 Python/Qt 或写机器级配置的方案不符合约束。
- 优先验证自包含便携目录。只有 IT 允许免提权时才考虑用户级安装。便携可执行仍可能受执行策略限制，应与 IT 协调，不能绕过。
- 基准／设置／日志在独立用户可写目录；替换／更新不丢基准，不依赖 Program Files/HKLM 写入或服务。
- 首次分发、解压／安装、首次启动和核查全部离线。完整包携带所需运行依赖；目标电脑不能需要在线引导安装器、pip install、激活或前置组件下载。

### 所选栈内仍需验证

S1/S2：Python DOCX 库、OOXML 访问、有效样式、覆盖与来源映射。S3：准确 Python/PySide6 版本、冻结／打包工具、运行时携带、两类 OS 允许的分发形式。S6：转换白名单、关联要求范围、歧义和规模。本地格式与数据位置需小型持久化验证。这些是未定工程细节，不是未选生产框架。

提议的验证见 [technical-spikes.md](technical-spikes.md)，分阶段计划见 [implementation-plan.md](implementation-plan.md)。本次文档更新不授权实验执行或生产实现。

## 已确认的 Python 3.8 与完全离线环境

用户说明：公司电脑目前安装 **Python 3.8**，能否升级未知。这是现有环境事实，不表示已经选择应用／构建运行时版本。保留该安装及其 PATH／文件关联，不作修改。目标仍为 **Windows 10 和 Windows 11 x64**，使用者**没有管理员／安装权限**。**首次分发、解压／安装、首次启动和正常核查必须完全离线。**

计划的自包含包须携带经过验证的 Python／Qt／原生依赖，不调用电脑中的 `python`，不要求目标机执行 `pip install`、在线激活或下载。S3 必须断网、无缓存前置依赖，分别验证与现有 Python 3.8 共存且不改动它，以及未安装 Python 的干净电脑。目前没有分发包通过这些检查。

开发／构建环境是否可用仍是独立未决项：确认能否在不改变公司安装的条件下，使用获准的隔离／较新解释器及 Windows 构建机。不能认为 Python 3.8 的 `venv` 会升级解释器。如果唯一允许的构建／运行时就是 3.8，应先评估准确兼容依赖组合及维护影响，不能悄悄锁定旧包或改变技术栈。完全离线交付不代表已经确认构建机本身能否联网；需要单独记录，并在必要时准备离线构建依赖。

### 当前运行时兼容性依据

当前 Qt for Python 入门页要求 Python 3.10+，因此不能假设其中安装最新版的路径兼容 Python 3.8。这不等于已确定每个历史 PySide6 版本的完整兼容范围。[Qt for Python 要求](https://doc.qt.io/qtforpython-6/gettingstarted.html)。

Python 3.8 于 2024-10-07 结束上游支持。因此如果选择旧运行时路径，需要明确评估维护影响；本文件不改变公司既有安装。[Python 版本状态](https://devguide.python.org/versions/)。

PyInstaller 文档说明它会携带构建时的解释器和依赖，使最终用户无需安装 Python。这支持研究应用私有运行时，但不代表本项目分发包已经可用。PyInstaller 仍是评估中的打包选项，未被选定；输出与 OS／解释器／架构相关，Windows 分发包必须据此验证。[PyInstaller 工作方式](https://pyinstaller.org/en/stable/operating-mode.html)。
