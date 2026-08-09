import logging
from collections import deque

from app.config.settings import settings

memory_log_handler: "MemoryLogHandler | None" = None


class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 500) -> None:
        super().__init__()
        self.capacity = capacity
        self.buffer: deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append(self.format(record))
        except Exception:
            self.handleError(record)

    def recent(self, lines: int = 30) -> str:
        return "\n".join(list(self.buffer)[-lines:])


def setup_logging() -> None:
    global memory_log_handler
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
    )

    if memory_log_handler is None:
        memory_log_handler = MemoryLogHandler()
        memory_log_handler.setFormatter(formatter)
        root.addHandler(memory_log_handler)

    for handler in list(root.handlers):
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, MemoryLogHandler
        ):
            return

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)
