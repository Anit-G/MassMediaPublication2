import os
import time
from typing import Optional, Tuple

from Workers.BaseWorker import BaseWorker
import Utils.Central_Logger as log
import Utils.Config_vars as config
from Utils.DB_Operations import DBOps, Status
from VideoGen.VideoGenerator import VideoGen


class VideoGenWorker():
    """Worker that generates chapter videos for a single category."""

    def __init__(self, video_gen: VideoGen, category: str, poll_interval: float = 0.1):
        self.worker_tag=f"VideoGenWorker[{category}]"
        self.video_gen = video_gen
        self.category = category

    def run(self) -> None:
        log.INFO(f"{self.worker_tag}: processing ebook for category: {self.category}")
        try:
            result = self.video_gen.generate_chapter_video(self.category, use_short=config.GENERATE_SHORTS)
            if result:
                log.INFO(f"{self.worker_tag}: video generation for chapter completed for category: {self.category}")
            else:
                log.WARNING(f"{self.worker_tag}: video generation for chapter NOT COMPLETED for category: {self.category}")
        except Exception as exc:
            log.ERROR(f"{self.worker_tag}: failed to generate video for ebook for category {self.category}: {exc}")\
        
        for _ in range(config.RETRY_MAX_ATTEMPTS):
            self.run_retries()
        
        return
            
    def run_retries(self) -> None:
        log.INFO(f"{self.worker_tag}: Start retry for category {self.category}")
        self.video_gen.generate_chapter_video_retries()