from __future__ import annotations

from worker.adapters.sharepoint.base import SharePointAdapter
from worker.models import Job


class JobQueue:
    """Thin, queue-shaped view over a SharePointAdapter's job list."""

    def __init__(self, sharepoint: SharePointAdapter):
        self.sharepoint = sharepoint

    def has_pending(self) -> bool:
        return bool(self.sharepoint.get_pending_jobs())

    def peek_pending(self) -> list[Job]:
        return self.sharepoint.get_pending_jobs()
