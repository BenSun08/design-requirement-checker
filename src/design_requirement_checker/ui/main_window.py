"""Minimal desktop workspace with explicitly unavailable future operations."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("设计需求核查工具")
        self.resize(1100, 720)
        self.setMinimumSize(760, 480)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        title = QLabel("设计需求核查工具")
        font = title.font()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        notice = QLabel("基本框架已就绪。文档读取、自动核查和检查项管理尚未实现。")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        actions = QHBoxLayout()
        for text in ("导入 DOCX（待实现）", "开始核查（待实现）", "检查项管理（待实现）"):
            button = QPushButton(text)
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)

        workspace = QSplitter(Qt.Orientation.Horizontal)
        for heading, message in (
            ("检查项", "尚未加载检查项。\n后续将在此显示本地基线中的核查项目。"),
            ("证据与对比", "尚无核查结果。\n后续将在此显示原文位置、格式和预期描述对比。"),
        ):
            panel = QGroupBox(heading)
            panel_layout = QVBoxLayout(panel)
            label = QLabel(message)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignTop)
            panel_layout.addWidget(label)
            panel_layout.addStretch()
            workspace.addWidget(panel)
        workspace.setChildrenCollapsible(False)
        workspace.setSizes([400, 600])
        layout.addWidget(workspace, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("框架初始化 · 尚未执行文档核查")
