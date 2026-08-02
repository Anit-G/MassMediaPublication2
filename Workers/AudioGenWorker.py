import time
from typing import List, Optional, Tuple

import Utils.Config_vars as config
import Utils.Central_Logger as log
from Utils.DB_Operations import DBOps, Status
from TTS.TTS import TTS


class AudioGenWorker:
    """Worker that generates TTS audio for one chapter at a time."""

    def __init__(self, tts: TTS, category: str, poll_interval: float = 5.0):
        self.tts = tts
        self.category = category
        self.worker_tag=f"AudioGenWorker[{category}]"
        self.stop_requested = False

    def run(self) -> None:
        log.INFO(f"{self.worker_tag}: started for category={self.category}")
        try:
            self.tts.generate_chapter_audio_for_worker(
                category=self.category,
                use_short=config.GENERATE_SHORTS,
            )
        except Exception as exc:
            log.ERROR(f"{self.worker_tag}: failed to generate audio for category={self.category} with error: {exc}")

        log.INFO(f"{self.worker_tag}: stopped for category={self.category}")
        
        for _ in range(config.RETRY_MAX_ATTEMPTS):
            self.run_retries()
            
        return

    def run_retries(self) -> None:
        log.INFO(f"{self.worker_tag}: Start retry for category {self.category}")
        # Run Retries 3 times and if all failures raise alert
        self.tts.generate_chapter_audio_retries()
        
    def stop(self) -> None:
        self.stop_requested = True