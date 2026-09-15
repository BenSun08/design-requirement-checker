# Design Requirement Checker
## Architecture, Python/Qt, Dependencies, and Windows Deployment Guide

## 1. The most important answer first

For the final company deployment:

**You do not need to install Python 3.13 on the company computer just to run the application.**

Your intended deployment model is:

```text
Your development environment
        │
        │ Python 3.13
        │ PySide6
        │ your Python source code
        │
        ▼
Windows build environment
GitHub Actions / Windows PC
        │
        │ PyInstaller
        ▼
Portable Windows package
        │
        ├── DesignRequirementChecker.exe
        ├── private Python 3.13 runtime
        ├── PySide6 / Qt libraries
        ├── required Python libraries
        └── your application code
        │
        ▼
Company Windows PC
        │
        └── Double-click EXE
```

PyInstaller analyzes the program and collects the Python interpreter, imported Python modules, native libraries, and application code into the distribution. Users of the packaged application do **not** need Python installed separately.

Therefore, keep these environments conceptually separate:

| Environment | Python 3.13 installation required? |
|---|---:|
| Your Mac for development | Yes |
| A Windows PC used to develop/debug source | Yes, or an equivalent isolated interpreter |
| GitHub Actions Windows builder | Automatically provided by CI |
| Company PC that only runs the final application | **No** |
| Company PC that must edit/debug Python source | Yes, or an equivalent development runtime |

This distinction is central to the architecture of this project.

---

## 2. What kind of application are you building?

This repository is building a **native desktop application** rather than a website.

The selected technology stack is:

```text
Python
   │
   ▼
PySide6
   │
   ▼
Qt 6
   │
   ▼
Windows / macOS native desktop window
```

Qt is a large cross-platform C++ GUI framework.

PySide6 is the official Qt binding for Python. It lets Python code call Qt APIs, so instead of writing a traditional Qt application in C++, you write Python.

For example:

```python
from PySide6.QtWidgets import QPushButton
```

roughly means:

> Give my Python program access to Qt's push-button widget.

The application can therefore use standard desktop components such as:

- windows
- buttons
- text boxes
- lists
- tables
- dialogs
- menus
- splitters
- file pickers
- progress bars

without implementing them from scratch.

---

## 3. How a Qt Python application starts

The most useful file for understanding this is:

```text
src/design_requirement_checker/__main__.py
```

Your current startup code creates a `QApplication`, creates `MainWindow`, calls `show()`, and finally starts Qt's event loop with `app.exec()`.

Conceptually:

```text
python -m design_requirement_checker
             │
             ▼
         __main__.py
             │
             ▼
       QApplication
             │
             ▼
         MainWindow
             │
             ▼
        window.show()
             │
             ▼
          app.exec()
             │
             ▼
       Qt event loop
```

### QApplication

`QApplication` represents the running GUI application.

Normally you create one `QApplication` per desktop process.

It manages things such as:

- mouse events
- keyboard events
- drawing
- windows
- timers
- application lifecycle

### MainWindow

Your application then creates:

```python
window = MainWindow()
```

`MainWindow` subclasses Qt's:

```python
QMainWindow
```

which represents a normal desktop application window.

### show()

Calling:

```python
window.show()
```

tells Qt that the window should become visible.

### app.exec()

This is especially important for someone coming from normal Python scripts.

A command-line Python program normally executes:

```text
line 1
line 2
line 3
exit
```

A GUI program cannot work like that.

It needs to remain alive waiting for:

```text
user clicks button
user moves window
user selects DOCX
timer fires
background work completes
user closes application
```

Therefore:

```python
app.exec()
```

starts the **event loop**.

Think of it approximately as:

```python
while application_is_running:
    event = wait_for_next_event()
    dispatch_event(event)
```

Qt implements this loop for you.

---

## 4. What your current window actually contains

The current:

```text
src/design_requirement_checker/ui/main_window.py
```

is still a skeleton.

It builds a `QMainWindow` containing labels, layouts, buttons, and a horizontal splitter. The DOCX import, checking, and checklist-management buttons are intentionally disabled because the corresponding functionality has not yet been implemented.

The basic hierarchy is approximately:

```text
QMainWindow
│
└── QWidget
    │
    └── QVBoxLayout
        │
        ├── QLabel
        │      "设计需求核查工具"
        │
        ├── QLabel
        │      initialization notice
        │
        ├── QHBoxLayout
        │   ├── QPushButton
        │   ├── QPushButton
        │   └── QPushButton
        │
        └── QSplitter
            ├── "检查项"
            └── "证据与对比"
```

This introduces another important Qt concept.

## Widgets and layouts

A **widget** is a visible UI component:

```text
QLabel
QPushButton
QTableView
QLineEdit
QMainWindow
```

A **layout** decides where widgets go:

```text
QVBoxLayout
QHBoxLayout
QGridLayout
```

For example:

```python
layout = QVBoxLayout()

layout.addWidget(title)
layout.addWidget(button)
layout.addWidget(table)
```

means the controls are arranged vertically.

You normally do **not** manually calculate pixel positions for every control. Qt layouts handle resizing for you.

---

## 5. Another Qt concept you will soon encounter: signals and slots

Although the skeleton does not yet make much use of them, this will become fundamental.

Suppose there is a button:

```python
button = QPushButton("导入 DOCX")
```

You want this Python function to run when it is clicked:

```python
def import_docx():
    ...
```

Qt uses signals and slots:

```python
button.clicked.connect(import_docx)
```

Conceptually:

```text
QPushButton
    │
    │ emits
    ▼
 clicked signal
    │
    ▼
import_docx()
```

This is the normal event-driven programming model of Qt.

You do not repeatedly ask:

```python
is_button_clicked()
```

Qt tells you when the click happens.

---

## 6. The intended repository architecture

The architecture is intentionally more structured than:

```text
main.py
└── 5,000 lines of everything
```

The planned architecture is approximately:

```text
                  Presentation
                       │
                       ▼
             ui/main_window.py
                       │
                       ▼
                  Application
                       │
                       ▼
                application.py
                 /           \
                ▼             ▼
             Domain        Matching
            domain.py      matching.py
                ▲             ▲
                 \           /
                  \         /
                  Adapters
                 /        \
                ▼          ▼
       docx_adapter.py  baseline_store.py
```

The implementation plan defines a single local desktop process and keeps the application/domain/adapters independent of the Qt presentation layer.

This separation is important.

---

## 7. Presentation layer

Files such as:

```text
src/design_requirement_checker/ui/main_window.py
```

belong to the **presentation layer**.

Its responsibility is:

```text
show information
collect user input
display progress
display errors
display comparison results
```

It should not contain the core checking algorithm.

For example, this would be poor architecture:

```python
def on_check_clicked():
    docx = zipfile.ZipFile(...)
    ...
    perform_matching(...)
    ...
    update_database(...)
```

all inside a button handler.

Instead:

```text
button click
     │
     ▼
application service
     │
     ▼
domain / matching / adapters
     │
     ▼
result
     │
     ▼
UI displays result
```

---

## 8. Application layer

The planned:

```text
application.py
```

will coordinate use cases such as:

```text
Import document
Run verification
Cancel verification
Load baseline
Save baseline
Invalidate old results
```

The file is currently only a placeholder; no orchestration or background processing has been implemented yet.

You can think of it as the conductor.

For example:

```text
UI:
"Please check this document."

          │
          ▼

Application:
1. Ask DOCX adapter to read document
2. Load checklist
3. Run matching
4. Generate results
5. Return results

          │
          ▼

UI:
Display results
```

---

## 9. Domain layer

The planned:

```text
domain.py
```

contains the fundamental concepts of your business problem.

The repository explicitly says this file should contain UI-independent Python value models and invariant validation, with **no Qt or filesystem dependencies**.

Eventually you might have concepts resembling:

```python
CheckItem
Document
Evidence
CheckResult
CheckStatus
ComparisonStatus
SourceLocation
```

These represent your engineering domain.

The important architectural rule is:

```text
domain.py
```

should not care whether its caller is:

```text
Qt
CLI
unit test
future API
```

That makes the business logic much easier to test.

---

## 10. Matching layer

The planned:

```text
matching.py
```

will eventually contain deterministic matching logic such as:

```text
detection phrase matching
aliases
normalization
evidence classification
configured / missing / struck-out decisions
description comparison
```

At present none of this has been implemented; the module remains a placeholder pending fixture validation.

Keeping this independent from Qt means you can write:

```python
result = check(document, checklist)
```

inside a unit test without opening any window.

That is a major advantage.

---

## 11. DOCX adapter

The planned:

```text
docx_adapter.py
```

will handle the complicated boundary between a `.docx` file and your clean Python domain objects.

The repository reserves it for:

```text
OOXML ingestion
source mapping
formatting interpretation
coverage warnings
```

but the actual DOCX implementation library has not yet been selected or validated.

Conceptually:

```text
customer.docx
     │
     ▼
docx_adapter.py
     │
     ▼
clean Python representation
     │
     ├── paragraph
     ├── text runs
     ├── tables
     ├── strike-through information
     └── source locations
```

Other layers should ideally not have to understand raw OOXML XML structures.

---

## 12. Baseline store

Another adapter is:

```text
baseline_store.py
```

Its planned job is:

```text
load checklist baseline
save checklist baseline
recover from interrupted/corrupted writes
```

Persistence is not yet implemented. The current file explicitly states that runtime data is not written beside the application.

Eventually, the architecture could look like:

```text
Windows

%APPDATA%
└── DesignRequirementChecker
    ├── baseline.json
    ├── settings.json
    └── logs/
```

rather than:

```text
Program directory
├── DesignRequirementChecker.exe
├── baseline.json       ← avoid
└── logs/               ← avoid
```

Qt's `QStandardPaths` is intended to help applications obtain appropriate platform-specific user data locations.

---

## 13. Current implementation status

It is important not to confuse **architecture already designed** with **features already implemented**.

Right now the real production application is primarily:

```text
startup
+
minimal Qt window
+
testing infrastructure
+
cross-platform development configuration
+
Windows packaging infrastructure
```

DOCX ingestion, matching, and persistence are still pending.

So the project is currently closer to:

```text
Infrastructure foundation
████████████████████

Qt UI skeleton
██████████░░░░░░░░░░

DOCX engine
░░░░░░░░░░░░░░░░░░

Matching engine
░░░░░░░░░░░░░░░░░░

Persistence
░░░░░░░░░░░░░░░░░░
```

rather than a nearly finished application.

---

## 14. Understanding `pyproject.toml`

This is probably the most important configuration file for the Python project:

```text
pyproject.toml
```

Your current configuration contains several different categories of dependencies.

### 14.1 Build-system dependencies

```toml
[build-system]
requires = [
    "setuptools==84.0.0",
    "wheel==0.48.0"
]

build-backend = "setuptools.build_meta"
```

These are used to understand/build/install the Python project itself.

Think:

```text
repository
   │
   ▼
setuptools
   │
   ▼
installable Python package
```

They are not your application's GUI dependencies.

---

## 15. Python requirement

Your repository currently states:

```toml
requires-python = ">=3.13,<3.14"
```

This means the **development/build environment for this project** expects Python 3.13.

It does not mean:

> every company PC must install Python 3.13.

That distinction comes later during packaging.

---

## 16. Runtime dependencies

Currently:

```toml
dependencies = [
    "PySide6==6.11.2"
]
```

This means your direct application runtime dependency is currently just PySide6.

However, PySide6 has its own dependencies, including packages such as:

```text
PySide6
├── PySide6-Essentials
├── PySide6-Addons
└── Shiboken6
```

You do not manually list every Qt DLL in `pyproject.toml`.

`pip` resolves package dependencies during development.

Later, PyInstaller collects the runtime components required by the application.

---

## 17. Development dependencies

Your repository defines:

```toml
dev = [
    "pytest==9.1.1",
    "ruff==0.16.6",
    "mypy==2.3.1"
]
```

These are **not application features**.

They are engineering tools.

### pytest

Used to test code.

For example:

```text
input DOCX
    ↓
checker
    ↓
expected result?
```

or:

```text
start Qt application
    ↓
window appears?
    ↓
PASS / FAIL
```

### Ruff

Used for:

```text
linting
format validation
code-quality checks
```

It detects issues such as unused imports and malformed code style.

### mypy

Used for static type checking.

For example:

```python
def check(path: str) -> CheckResult:
```

Mypy can catch certain cases where another piece of code incorrectly calls:

```python
check(123)
```

before the application is executed.

---

## 18. Windows build dependency

The repository now has:

```toml
build-windows = [
    "pyinstaller==6.22.3; sys_platform == 'win32'"
]
```

The condition:

```text
sys_platform == 'win32'
```

means PyInstaller is installed through this extra only when running on Windows.

This is useful because:

```text
macOS development
does not need
Windows PyInstaller packaging
```

while:

```text
Windows build
does need
PyInstaller
```

---

## 19. Why `pip install -e ".[dev]"`?

When you run:

```bash
python -m pip install -e ".[dev]"
```

there are several pieces here.

### `.`

Install the project in the current directory.

### `-e`

Editable install.

Instead of copying a frozen copy of your project into `site-packages`, Python continues to use your working source.

Therefore:

```text
edit code
   ↓
press Run again
   ↓
new code executes
```

without reinstalling your project every time.

### `[dev]`

Also install the optional development tools:

```text
pytest
ruff
mypy
```

On the Windows packaging environment:

```bash
python -m pip install -e ".[dev,build-windows]"
```

adds PyInstaller as well.

---

## 20. What `project.gui-scripts` does

Your configuration contains:

```toml
[project.gui-scripts]
design-requirement-checker =
    "design_requirement_checker.__main__:main"
```

This defines an application entry point.

Conceptually:

```text
design-requirement-checker
        │
        ▼
design_requirement_checker.__main__
        │
        ▼
main()
```

This is cleaner than treating some arbitrary `.py` file as an executable script.

---

## 21. Why the project uses `src/`

The repository has:

```text
src/
└── design_requirement_checker/
```

This is called a **src layout**.

`pyproject.toml` tells setuptools:

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

So Python package source lives under:

```text
src/
```

rather than directly at repository root.

A simplified repository structure is therefore:

```text
design-requirement-checker/
│
├── src/
│   └── design_requirement_checker/
│       ├── __main__.py
│       ├── domain.py
│       ├── application.py
│       ├── matching.py
│       ├── docx_adapter.py
│       ├── baseline_store.py
│       └── ui/
│
├── tests/
│
├── packaging/
│   └── windows/
│
├── .github/
│   └── workflows/
│
├── pyproject.toml
└── README.md
```

This separation makes it less likely that tests accidentally import source merely because the repository root happens to be on Python's path.

---

## 22. How debugging works

The repository now contains:

```text
.vscode/launch.json
```

The important configuration is:

```json
"module": "design_requirement_checker"
```

That tells VS Code/Cursor:

```text
debug:

python -m design_requirement_checker
```

rather than:

```text
python some/random/path/main.py
```

This is good because exactly the same debug configuration works on:

```text
macOS
Windows
```

provided your IDE has selected the appropriate `.venv` interpreter.

You can therefore set a breakpoint, press F5, and inspect the program as it starts.

---

## 23. What the startup test does

The project already includes a useful Qt smoke test.

It launches the actual application startup path in another Python process, uses Qt's `offscreen` platform, checks that exactly one main window becomes visible, verifies that unfinished action buttons remain disabled, closes the window, and verifies clean exit.

That gives you a good example of the testing philosophy:

```text
do not only test functions

also test:
real QApplication
+
real MainWindow
+
real event loop
```

without requiring a human to click the window every CI run.

---

## 24. What GitHub Actions CI is doing

Your:

```text
.github/workflows/ci.yml
```

runs on both:

```text
macos-latest
windows-latest
```

using Python 3.13.

For every platform it approximately does:

```text
checkout
   ↓
install Python 3.13
   ↓
pip install project + dev dependencies
   ↓
pytest
   ↓
ruff lint
   ↓
ruff formatting check
   ↓
mypy
   ↓
pip check
```

This answers an important question:

> How can I develop mainly on macOS but know that I have not completely broken Windows?

GitHub provides a fresh Windows runner and tests the code there.

That does not replace real company-PC validation, but it catches many portability problems early.

---

## 25. Windows packaging workflow

Your repository also contains:

```text
.github/workflows/build-windows.yml
```

It runs only on:

```text
windows-latest
```

and installs:

```text
Python 3.13 x64
PySide6
your project
development dependencies
Windows packaging dependencies
```

before running tests and invoking PyInstaller.

The important pipeline is:

```text
GitHub Windows machine
        │
        ▼
Python 3.13
        │
        ▼
pip install .[dev,build-windows]
        │
        ▼
tests
        │
        ▼
PyInstaller
        │
        ▼
dist/DesignRequirementChecker/
        │
        ▼
GitHub artifact
```

That means your personal Mac does **not** need to produce a Windows `.exe`.

And your company computer does **not** need to be the build machine.

---

## 26. Why can't Mac build the Windows EXE?

Because PyInstaller is not a cross-compiler.

The produced bundle is specific to the operating system, Python version, and architecture used for the build.

Therefore:

```text
macOS
   │
   ├── develop ✅
   ├── debug ✅
   ├── test ✅
   └── produce Windows EXE ❌
```

But:

```text
GitHub Windows runner
   │
   └── produce Windows EXE ✅
```

This is exactly why your architecture separates CI from Windows packaging.

---

## 27. What is the `.spec` file?

Your repository has:

```text
packaging/windows/design-requirement-checker.spec
```

This is essentially the **build recipe** for PyInstaller.

It points PyInstaller at:

```text
src/design_requirement_checker/__main__.py
```

and tells it how to build:

```text
Analysis
   ↓
PYZ
   ↓
EXE
   ↓
COLLECT
```

The current configuration produces a `DesignRequirementChecker` application in windowed mode and uses `COLLECT`, which corresponds to one-directory style distribution.

You can think of the spec file as analogous to:

> Here is my executable entry point, here are extra data files, here are DLLs, here are hidden imports, and here is how I want the final package constructed.

Right now it is intentionally minimal.

That is appropriate.

---

## 28. How PyInstaller packages Python 3.13

This directly addresses your biggest concern.

Suppose your Windows build environment contains:

```text
Python 3.13
PySide6
your project
future python-docx
future other libraries
```

PyInstaller analyzes imports recursively and collects the necessary files, including the active Python interpreter.

The resulting folder will conceptually contain something like:

```text
DesignRequirementChecker/
│
├── DesignRequirementChecker.exe
│
└── application-private runtime files
    ├── Python 3.13 runtime
    ├── Python standard-library pieces
    ├── PySide6 Python modules
    ├── Qt DLLs
    ├── Qt platform plugins
    ├── Shiboken
    └── your application modules
```

The exact directory names may differ because PyInstaller controls the bundle structure.

The important point is:

```text
company system Python
```

and:

```text
application private Python
```

are different.

---

## 29. What happens when the company user double-clicks the EXE?

Conceptually:

```text
Double-click
DesignRequirementChecker.exe
         │
         ▼
PyInstaller bootloader
         │
         ▼
locates bundled runtime
         │
         ▼
starts bundled Python interpreter
         │
         ▼
loads your Python modules
         │
         ▼
loads PySide6
         │
         ▼
loads Qt DLLs
         │
         ▼
QApplication
         │
         ▼
MainWindow
```

It is **not** doing:

```text
search PATH
   ↓
find company's Python 3.8
   ↓
pip install PySide6
   ↓
run application
```

That would defeat the purpose of freezing the application.

---

## 30. What happens to the company's existing Python 3.8?

Ideally: nothing.

For example:

```text
Company Windows PC

C:\CompanyTools\Python38\
        │
        └── existing Python 3.8

DesignRequirementChecker\
        │
        ├── DesignRequirementChecker.exe
        └── private bundled Python 3.13 runtime
```

The two are separate.

Your intended architecture is specifically designed not to replace the company's Python 3.8 installation or modify its PATH/file associations.

This is one of the main benefits of the portable bundled approach.

---

## 31. Why use `onedir` first?

PyInstaller supports both:

```text
onedir
```

and:

```text
onefile
```

Your project deliberately uses:

```text
onedir
```

first.

This is easier to debug because the collected dependencies are visible.

Therefore your first company deployment may look like:

```text
DesignRequirementChecker.zip
             │
             ▼
           unzip
             │
             ▼
DesignRequirementChecker/
├── DesignRequirementChecker.exe
└── runtime files...
```

The employee must keep the **whole folder**.

Do not send only:

```text
DesignRequirementChecker.exe
```

because the adjacent runtime components are part of the application.

---

## 32. Does `onedir` still count as a standalone application?

Yes.

Standalone does **not** mean:

> there must only be one file.

It means:

> the application contains the runtime it needs and does not require users to separately install Python/modules.

PyInstaller's one-folder mode is specifically designed for this distribution model.

---

## 33. Could you use one EXE later?

Yes.

Once:

```text
onedir
    ↓
Windows 10 test
    ↓
Windows 11 test
    ↓
company antivirus test
    ↓
offline test
    ↓
real DOCX test
    ↓
all stable
```

you could investigate:

```text
PyInstaller onefile
```

But there is little benefit in making this an early goal for an internal engineering tool.

Reliability is more important than having exactly one physical file.

---

## 34. Alternative: Python's embeddable distribution

There is another technical option.

Python publishes a Windows **embeddable package**, which is a minimal Python distribution designed to be included inside another application.

Conceptually:

```text
MyApplication/
├── python.exe
├── python313.dll
├── python313.zip
├── PySide6/
├── my source
└── launcher
```

However, I would **not recommend replacing PyInstaller with this approach for your current project**.

Why?

You would become responsible for much more deployment plumbing yourself:

```text
Python paths
third-party modules
Qt DLLs
Qt plugins
native dependencies
launcher
isolation
runtime configuration
```

PyInstaller is solving exactly this packaging problem for you.

---

## 35. What if you want to debug directly on the company PC?

This is a different requirement.

If the company PC needs to execute:

```bash
python -m design_requirement_checker
```

rather than the packaged EXE, then it needs access to a compatible Python 3.13 development runtime.

Possible approaches include:

### Preferred for development

Install an approved isolated Python 3.13 environment.

Then:

```text
Python 3.13
   ↓
venv
   ↓
pip install .[dev]
   ↓
VS Code / Cursor
   ↓
debug
```

### Portable/embedded Python

Technically possible, but more complicated for normal development.

### Remote/GitHub build

If the company computer only needs to run the finished application, avoid setting up Python development there altogether.

For your current scenario, this is the cleanest architecture:

```text
Mac
development
    │
    ▼
GitHub
    │
    ▼
Windows CI/build
    │
    ▼
ZIP artifact
    │
    ▼
Company PC
runtime only
```

---

## 36. Recommended environment strategy for your project

Think about three machines rather than one.

```text
1. Mac development machine
───────────────────────────
Python 3.13
PySide6
pytest
ruff
mypy
VS Code / Cursor
Codex

          │ git push
          ▼

2. GitHub Windows build machine
───────────────────────────────
Windows x64
Python 3.13
PySide6
PyInstaller
tests

          │ build artifact
          ▼

3. Company target PC
────────────────────
NO Python 3.13 installation
NO pip
NO PySide6 installation
NO Qt installation
NO development tools

Only:
DesignRequirementChecker/
```

This is a much cleaner software-delivery boundary.

---

## 37. What still has to be validated

A successful GitHub Actions build does **not** yet prove:

```text
"this application will run on every company computer."
```

You will eventually need real deployment tests.

A useful release matrix is:

| Test environment | Must test |
|---|---|
| Windows 10 x64 | Yes |
| Windows 11 x64 | Yes |
| Company Python 3.8 already installed | Yes |
| No Python installed | Yes |
| Network disabled | Yes |
| Standard non-admin user | Yes |
| Chinese Windows paths | Yes |
| Long file paths/names | Yes |
| Company endpoint protection/antivirus | Yes |
| Normal company DOCX files | Yes |

The goal is to prove:

```text
copy ZIP
↓
unzip
↓
double-click
↓
works
```

without:

```text
administrator
internet
Python install
pip install
Qt install
Office automation
```

---

## 38. A useful mental model for dependencies

When you hear "dependency", distinguish these categories.

```text
                         Dependencies
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
       Runtime               Dev                Build
          │                   │                   │
       PySide6              pytest            PyInstaller
       future DOCX          Ruff
       library              mypy
          │
          ▼
   needed by application
```

Then there is another category:

```text
Build-system dependencies
        │
        ├── setuptools
        └── wheel
```

And another:

```text
transitive dependencies
        │
        └── dependencies of your dependencies
```

For example:

```text
your app
   │
   ▼
PySide6
   │
   ├── PySide6-Essentials
   ├── PySide6-Addons
   └── Shiboken6
```

You generally should not manually copy these around during development.

Your package manager and deployment tooling handle them.

---

## 39. Source code versus executable

Another useful concept:

During development:

```text
.py source files
+
Python interpreter
+
installed packages
```

are separate.

For example:

```text
Python 3.13
    │
    ├── executes your .py files
    │
    └── imports PySide6
```

After PyInstaller freezing:

```text
your application source
+
Python interpreter
+
Python libraries
+
Qt libraries
+
native dependencies
```

become one distributable application bundle.

That process is commonly called:

```text
freezing
```

---

## 40. The architecture you should keep in your head

At the code level:

```text
┌───────────────────────────────────────┐
│ UI / PySide6                          │
│ main_window.py                        │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ Application                           │
│ application.py                        │
│ coordinates use cases                 │
└──────────────────┬────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌────────────────┐   ┌────────────────┐
│ Domain         │   │ Matching       │
│ domain.py      │   │ matching.py    │
└────────────────┘   └────────────────┘
         ▲                   ▲
         └─────────┬─────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
┌────────────────┐    ┌─────────────────┐
│ DOCX adapter   │    │ Baseline store  │
│ docx_adapter   │    │ baseline_store  │
└────────────────┘    └─────────────────┘
```

At the deployment level:

```text
SOURCE REPOSITORY
       │
       ▼
Windows Python 3.13 build environment
       │
       ▼
PyInstaller
       │
       ▼
Portable application bundle
       │
       ▼
Company Windows machine
       │
       ▼
No separately installed Python required
```

Those are the two diagrams worth remembering.

---

## 41. What you should learn next

You do **not** need to learn all of Qt before continuing this project.

For this application, learn Qt incrementally in roughly this order:

1. `QApplication` and the event loop
2. `QMainWindow` and `QWidget`
3. layouts
4. common widgets
5. signals and slots
6. dialogs and file selectors
7. model/view widgets such as tables and lists
8. background work and UI-thread rules
9. `QStandardPaths`
10. packaging/resources

Then learn the application architecture alongside implementation:

```text
UI
→ application service
→ domain
→ adapter
→ tests
```

This will be more useful than trying to study the entire Qt framework first.

---

## 42. Recommended deployment decision

For this repository, keep the current direction:

```text
Development:
macOS + Windows
Python 3.13 + venv

CI:
macOS + Windows
Python 3.13

Production build:
Windows x64
Python 3.13
PyInstaller 6.22.3

Initial package:
PyInstaller onedir

Company environment:
no Python installation
no pip
no Qt installation
no admin privileges
offline-capable portable application
```

The one thing I would **not** do is install Python 3.13 on every company computer merely so engineers can run this tool. That would turn an application-deployment problem into an environment-management problem unnecessarily.

The company's existing Python 3.8 should be irrelevant to normal application execution once the standalone Windows bundle has been properly validated.

---

## 43. Short answers to your main questions

**Do I need Python 3.13 on my Mac?**

Yes, if you are developing and debugging the Python source there.

**Do I need Python 3.13 on a Windows development machine?**

Yes, if you want to run/debug the source code there.

**Do I need Python 3.13 on the company user's Windows machine?**

No, not for the intended packaged application.

**Where does Python 3.13 go then?**

Into the PyInstaller application bundle as an application-private runtime.

**Does the company Python 3.8 conflict with the bundled Python 3.13?**

It should not under the intended standalone architecture because your application uses its bundled runtime rather than invoking the system Python. Real company-PC testing is still required.

**Do users need PySide6 installed?**

No. Required PySide6/Qt runtime components should be included in the bundle.

**Do users need pip?**

No.

**Do users need network access?**

The intended runtime design says no; this still needs real offline validation.

**Do users need administrator privileges?**

The intended portable deployment says no; again, this requires verification under your company's endpoint policies.

**Can I develop on Mac and deliver Windows software?**

Yes. Develop/test on Mac, push to GitHub, and build the actual Windows artifact on a Windows GitHub Actions runner.

**Should I switch to Python's embeddable package instead of PyInstaller?**

Not currently. It is technically possible, but PyInstaller already automates much of the dependency collection and freezing that you would otherwise have to manage yourself.

---

## References

- Repository: https://github.com/BenSun08/design-requirement-checker
- Qt for Python / PySide6 documentation: https://doc.qt.io/qtforpython-6/
- PyInstaller documentation: https://pyinstaller.org/en/stable/
- Python 3.13 Windows documentation: https://docs.python.org/3.13/using/windows.html
