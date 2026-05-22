import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import time
import logging
from pathlib import Path

_LOG_PATH = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "logs" / "cliniq.log"
_LOG_PATH.parent.mkdir(exist_ok=True)

_logger = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger("cliniq")
    _logger.setLevel(logging.INFO)

    # File handler — structured JSON, one record per line
    fh = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(message)s"))

    # Console handler — human-readable
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    _logger.addHandler(fh)
    _logger.addHandler(ch)
    return _logger


def log_event(
    stage: str,
    data: dict,
    *,
    level: str = "info",
    duration_ms: float | None = None,
) -> None:
    """Emit a structured JSON log line for a pipeline stage."""
    record = {
        "ts": time.time(),
        "stage": stage,
        **data,
    }
    if duration_ms is not None:
        record["duration_ms"] = round(duration_ms, 2)

    logger = _get_logger()
    msg = json.dumps(record, default=str)
    getattr(logger, level, logger.info)(msg)


class StageTimer:
    """Context manager that logs a stage with elapsed time on exit."""

    def __init__(self, stage: str, extra: dict | None = None):
        self.stage = stage
        self.extra = extra or {}
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        log_event(f"{self.stage}.start", self.extra)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (time.perf_counter() - self._start) * 1000
        status = "error" if exc_type else "ok"
        log_event(
            f"{self.stage}.end",
            {**self.extra, "status": status},
            duration_ms=elapsed,
            level="error" if exc_type else "info",
        )
        return False  # don't suppress exceptions
