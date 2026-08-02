import time
from abc import ABC, abstractmethod
from typing import Optional

import Utils.Central_Logger as log
import Utils.Config_vars as config


class BaseWorker(ABC):
    """Shared base class for all pipeline workers."""

    def __init__(self, worker_tag: str, poll_interval: Optional[float] = None):
        self.poll_interval = poll_interval if poll_interval is not None else config.STATE_CHECK_INTERVAL_SECONDS
        self.stop_requested = False
        self.worker_tag = worker_tag

    def run(self) -> None:
        log.INFO(f"{self.worker_tag}: started")
        try:
            while not self.stop_requested:
                next_item = self.get_next_item()
                if next_item is None:
                    log.INFO(f"{self.worker_tag}: no pending work, sleeping {self.poll_interval}s")
                    time.sleep(self.poll_interval)
                    continue

                self.process_item(next_item)
        except Exception as exc:
            log.ERROR(f"{self.worker_tag}: unexpected error: {exc}")
        finally:
            log.INFO(f"{self.worker_tag}: stopped")

    def stop(self) -> None:
        self.stop_requested = True

    @abstractmethod
    def get_next_item(self):
        """Return the next work item for the worker or None if there is none."""
        ...

    @abstractmethod
    def process_item(self, item) -> None:
        """Process a single work item."""
        ...
