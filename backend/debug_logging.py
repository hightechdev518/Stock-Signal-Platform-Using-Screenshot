"""Pipeline debug logging to backend/debug.log (console + file)."""

import logging
from pathlib import Path

_LOG_PATH = Path(__file__).resolve().parent / "debug.log"
_configured = False


def setup_debug_logging() -> None:
    global _configured
    if _configured:
        return
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(_LOG_PATH),
        level=logging.DEBUG,
        format="%(asctime)s %(message)s",
        force=True,
    )
    for noisy in ("pytesseract", "urllib3", "yfinance", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def pipeline_log(message: str) -> None:
    """Write to debug.log and stdout for visible tracing."""
    setup_debug_logging()
    logging.info(message)
    print(message, flush=True)
