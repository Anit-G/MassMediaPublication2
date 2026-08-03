from __future__ import annotations
import time
from typing import Optional

from Workers.BaseWorker import BaseWorker
import Utils.Central_Logger as log
import Utils.Config_vars as config
from VideoGen.VideoGenerator import VideoGen


class VideoGenWorker(BaseWorker):
    """Worker that continuously consumes video generation work."""

    def __init__(
        self,
        video_gen: VideoGen,
        category: str,
        poll_interval: Optional[float] = None,
    ):
        super().__init__(worker_tag=f"VideoGenWorker[{category}]", poll_interval=poll_interval)
        self.video_gen = video_gen
        self.category = category

    def get_next_item(self):
        retries = self.video_gen._dbops.get_stage_retries("VIDEO_GEN")
        category_retries = [r for r in retries if len(r) >= 4 and r[3] == self.category]
        if category_retries:
            return ("retry", category_retries[0])

        res = self.video_gen._dbops.get_next_action_category(self.category, "PROCESSING", "VIDEO_GEN")
        if res is not None:
            return ("normal", res)
        return None

    def process_item(self, item) -> None:
        item_type, data = item
        if item_type == "retry":
            log.INFO(f"{self.worker_tag}: processing video retries for category={self.category}")
            self.video_gen.generate_chapter_video_retries()
        else:
            log.INFO(f"{self.worker_tag}: processing video generation for category={self.category}")
            self.video_gen.generate_chapter_video(self.category, use_short=config.GENERATE_SHORTS)
