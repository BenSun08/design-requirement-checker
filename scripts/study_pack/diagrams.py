"""Reviewed conceptual flows, distinct from inferred static call relationships."""

DIAGRAMS = {
    "01-overview/architecture.svg": """flowchart TB
    UI["PySide6 UI: MainWindow and workers"] --> APP["Application use cases"]
    APP --> MATCH["Pure matching engine"]
    APP --> ADAPTER["DOCX adapter: package and OOXML"]
    APP --> STORE["Baseline store: local JSON"]
    APP --> DOMAIN["Frozen domain values"]
    MATCH --> DOMAIN
    ADAPTER --> DOMAIN
    STORE --> DOMAIN
    UI --> DOMAIN
    UI -. "path and schema-error coupling" .-> STORE
    """,
    "assets/startup.svg": """flowchart TD
    ENTRY["__main__.main"] --> QT["QApplication: create or reuse"]
    QT --> STYLE["Application name and local Qt style"]
    STYLE --> PATH["default_path: AppDataLocation"]
    PATH --> LOAD["load_baseline_from"]
    LOAD --> WINDOW["MainWindow with items and baseline ID"]
    WINDOW --> STATE["apply_baseline_load: map source token"]
    STATE --> SHOW["show window"] --> LOOP["app.exec event loop"]
    """,
    "assets/docx-import.svg": """flowchart TD
    USER["User selects DOCX"] --> START["MainWindow._start_import: new generation"]
    START --> WIRE["ImportWorker moved to QThread"]
    WIRE --> RUN["thread.started signal runs worker"]
    RUN --> APP["application.import_document"]
    APP --> READ["docx_adapter.read_document: read bytes once"]
    READ --> VALUE["Immutable Document or ImportFailure"]
    VALUE --> SIGNAL["finished signal with generation"]
    SIGNAL --> GUARD["Reject stale generation or closing window"]
    GUARD --> VIEW["Current outcome updates GUI"]
    """,
    "assets/verification.svg": """flowchart TD
    WINDOW["MainWindow._on_run_clicked"] --> TOKEN["start_verification: invalidate old results"]
    TOKEN --> WORKER["VerificationWorker: document, items, Event, generation"]
    WORKER --> APP["application.verify_document: enabled items only"]
    APP --> MATCH["matching.verify"]
    MATCH --> CHECK["Event check before each item/block candidate search"]
    CHECK --> CLASSIFY["Associate spans, keep evidence, classify"]
    CLASSIFY --> OUTCOME["COMPLETED with CheckResult tuple"]
    CHECK -. "cancelled" .-> CANCEL["CANCELLED with empty results"]
    OUTCOME --> SIGNAL["Worker finished signal"]
    CANCEL --> SIGNAL
    SIGNAL --> GUARD["Current generation AND current document ID"]
    GUARD --> VIEW["Update result view or cancellation state"]
    """,
    "assets/baseline-persistence.svg": """flowchart TD
    CAND["Editable candidate baseline"] --> VALIDATE
    VALIDATE["Validation, warnings and damaged-primary confirmation"]
    VALIDATE --> NEW["temp-new: UTF-8 JSON, flush, fsync"]
    NEW --> CHECK["Inspect existing primary schema and validity"]
    CHECK -- "valid primary" --> COPY["Copy primary to temp-backup; flush and fsync"]
    COPY --> BAK["os.replace: install backup"]
    BAK --> INSTALL["os.replace: install new primary"]
    CHECK -- "missing or corrupt primary" --> INSTALL
    CHECK -- "unsupported schema" --> STOP["Abort; preserve original data"]
    INSTALL --> PUBLISH["set_check_items: publish and invalidate results"]
    """,
    "assets/qt-threading.svg": """flowchart TD
    GUI["GUI thread owns widgets"] --> WORKER["QObject worker moved to QThread"]
    WORKER --> RUN["QThread.started runs worker"]
    GUI -. "verification cancellation" .-> EVENT["threading.Event.set"]
    EVENT -. "matching checkpoints" .-> RUN
    RUN --> SIGNAL["finished or failed signal"]
    SIGNAL --> GUARD["GUI callback checks generation and document"]
    SIGNAL --> QUIT["DirectConnection: thread.quit"]
    QUIT --> FINISHED["QThread.finished"]
    FINISHED --> RETIRE["Join final termination; release owned worker and thread"]
    RETIRE --> RETRY["If closing: QTimer.singleShot retries close"]
    """,
    "assets/shutdown.svg": """flowchart TD
    CLOSE["closeEvent"] --> CANCEL["Set verification cancellation Event"]
    CANCEL --> QUIT["Request quit on every owned thread"]
    QUIT --> RUNNING{"Any owned thread still running?"}
    RUNNING -- "yes" --> IGNORE["Ignore close; return to event loop"]
    IGNORE --> FINISH["Wait asynchronously for QThread.finished"]
    FINISH --> CLEAN["Retire exact thread and worker by identity"]
    CLEAN --> TIMER["Last thread: schedule close with QTimer"]
    TIMER --> CLOSE
    RUNNING -- "no" --> ACCEPT["Accept close"]
    """,
}
