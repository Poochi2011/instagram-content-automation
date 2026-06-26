"""Generic QThread worker for running blocking calls (scraping, OCR) off the UI thread."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class CallableWorker(QThread):
    """Runs fn(*args, **kwargs) on a background thread and emits finished/failed."""

    def __init__(self, fn: Callable, *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.signals.finished.emit(result)
        except Exception as exc:  # surface any failure to the UI instead of crashing the thread
            self.signals.failed.emit(str(exc))
