import time
from typing import Optional

from Workers.BaseWorker import BaseWorker
import Utils.Central_Logger as log
import Utils.Config_vars as config
from Utils.DB_Operations import DBOps, Status
from VideoGen.UpMonYoutube import UpMonYouTube
from googleapiclient.errors import HttpError


class UploadWorker():
    """Worker that uploads completed chapter videos to YouTube."""

    def __init__(
        self,
        uploader: UpMonYouTube,
        category: str,
        poll_interval: Optional[float] = None,
    ):
        self.uploader = uploader
        self.worker_tag=f"UploadWorker[{category}]"
        self.category = category

    def run(self) -> None:
        log.INFO(f"{self.worker_tag}: processing upload.")
        try:
            upload_result = self.uploader.upload_single_video(self.category, upload_shorts=config.GENERATE_SHORTS)

            if not upload_result:
                log.INFO(f"{self.worker_tag}: no sections available for upload")
                return
            log.INFO(f"{self.worker_tag}: upload completed for chapter")

        except Exception as exc:
            error_msg = str(exc)
            log.ERROR(f"{self.worker_tag}: upload exception for chapter: {error_msg}")
        
        for _ in range(config.RETRY_MAX_ATTEMPTS):
            self.run_retries()
        
        return
            
    def run_retries(self) -> None:
        log.INFO(f"{self.worker_tag}: Start retry for category {self.category}")
        self.uploader.upload_single_video_retries