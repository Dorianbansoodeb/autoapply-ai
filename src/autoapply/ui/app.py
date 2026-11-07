"""Thin PySide6 UI. Engine work runs in a worker; Playwright stays off the GUI thread."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from autoapply.engine.protocol import Engine


def main() -> None:
    try:
        from PySide6.QtCore import QObject, Qt, Signal, Slot
        from PySide6.QtWidgets import (
            QApplication,
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPlainTextEdit,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is required for the GUI: uv add pyside6", file=sys.stderr)
        raise SystemExit(1) from None

    class Bridge(QObject):
        finished = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self.engine = Engine()

        @Slot(dict)
        def run_cmd(self, message: dict) -> None:
            async def _go() -> None:
                result = await self.engine.handle(message)
                import json

                self.finished.emit(json.dumps(result, indent=2))

            asyncio.run(_go())

    class Window(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("AutoApply AI — assisted mode (you click Submit)")
            self.bridge = Bridge()
            self.bridge.finished.connect(self._on_result)

            root = QWidget()
            layout = QVBoxLayout(root)
            layout.addWidget(
                QLabel(
                    "Local-first. The model never drives the browser. "
                    "Auto-submit stays off until a site earns it."
                )
            )
            self.resume = QLineEdit()
            self.job = QLineEdit()
            self.url = QLineEdit("http://127.0.0.1:8765/")
            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            layout.addLayout(self._row("Resume", self.resume, self._pick_resume))
            layout.addLayout(self._row("Job file", self.job, self._pick_job))
            url_row = QHBoxLayout()
            url_row.addWidget(QLabel("Apply URL"))
            url_row.addWidget(self.url)
            layout.addLayout(url_row)
            buttons = QHBoxLayout()
            for title, slot in (
                ("Import resume", self._import),
                ("Verify facts", self._verify),
                ("Build documents", self._docs),
                ("Fill form", self._fill),
            ):
                btn = QPushButton(title)
                btn.clicked.connect(slot)
                buttons.addWidget(btn)
            layout.addLayout(buttons)
            layout.addWidget(self.log)
            self.setCentralWidget(root)
            self.resize(720, 480)

        def _row(self, label, edit, picker):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(edit)
            btn = QPushButton("Browse")
            btn.clicked.connect(picker)
            row.addWidget(btn)
            return row

        def _pick_resume(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Resume", "", "Documents (*.pdf *.docx *.txt)")
            if path:
                self.resume.setText(path)

        def _pick_job(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Job", "", "Text (*.txt *.json)")
            if path:
                self.job.setText(path)

        def _import(self) -> None:
            self.bridge.run_cmd({"cmd": "profile.import", "path": self.resume.text()})

        def _verify(self) -> None:
            self.bridge.run_cmd({"cmd": "profile.verify"})

        def _docs(self) -> None:
            self.bridge.run_cmd({"cmd": "docs.build", "job": self.job.text()})

        def _fill(self) -> None:
            self.bridge.run_cmd(
                {
                    "cmd": "fill",
                    "url": self.url.text(),
                    "resume": self.resume.text() or None,
                    "headed": True,
                }
            )

        def _on_result(self, text: str) -> None:
            self.log.appendPlainText(text)

    app = QApplication(sys.argv)
    window = Window()
    window.show()
    raise SystemExit(app.exec())
