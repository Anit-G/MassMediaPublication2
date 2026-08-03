from __future__ import annotations
import time
from typing import Optional

from Workers.BaseWorker import BaseWorker
import Utils.Central_Logger as log
import Utils.Config_vars as config
from VideoGen.UpMonYoutube import UpMonYouTube


class UploadWorker(BaseWorker):
    """Worker that continuously consumes upload tasks."""

    def __init__(
        self,
        uploader: UpMonYouTube,
        category: str,
        poll_interval: Optional[float] = None,
    ):
        super().__init__(worker_tag=f"UploadWorker[{category}]", poll_interval=poll_interval)
        self.uploader = uploader
        self.category = category

    def get_next_item(self):
        retries = self.uploader._dbops.get_stage_retries("FULL_VIDEO_UPLOAD")
        category_retries = [r for r in retries if len(r) >= 4 and r[3] == self.category]
        if category_retries:
            return ("retry", category_retries[0])

        res = self.uploader._dbops.get_next_action_category(self.category, "PROCESSING", "FULL_VIDEO_UPLOAD")
        if res is not None:
            return ("normal", res)
        return None

    def process_item(self, item) -> None:
        item_type, data = item
        if item_type == "retry":
            log.INFO(f"{self.worker_tag}: processing upload retries for category={self.category}")
            if hasattr(self.uploader, 'upload_chapter_retries'):
                self.uploader.upload_chapter_retries()
            elif hasattr(self.uploader, 'upload_single_video_retries'):
                self.uploader.upload_single_video_retries()
        else:
            log.INFO(f"{self.worker_tag}: processing upload for category={self.category}")
            self.uploader.upload_single_video(self.category, upload_shorts=config.GENERATE_SHORTS)
