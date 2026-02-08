from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("pot")
    logger.setLevel(log_level)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    has_stream_handler = any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers)
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        has_same_file_handler = any(
            isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None) == str(file_path.resolve())
            for handler in logger.handlers
        )
        if not has_same_file_handler:
            file_handler = logging.FileHandler(file_path, mode="a", encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    for handler in logger.handlers:
        handler.setLevel(log_level)

    return logger
