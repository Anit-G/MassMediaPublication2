from __future__ import annotations
import time
from typing import Optional

from Workers.BaseWorker import BaseWorker
import Utils.Central_Logger as log
import Utils.Config_vars as config
from TTS.TTS import TTS


class AudioGenWorker(BaseWorker):
    """Worker that continuously consumes audio generation work."""

    def __init__(
        self,
        tts: TTS,
        category: str,
        poll_interval: Optional[float] = None,
    ):
        super().__init__(worker_tag=f"AudioGenWorker[{category}]", poll_interval=poll_interval)
        self.tts = tts
        self.category = category

    def get_next_item(self):
        retries = self.tts._dbops.get_stage_retries("AUDIO_GEN")
        category_retries = [r for r in retries if len(r) >= 4 and r[3] == self.category]
        if category_retries:
            return ("retry", category_retries[0])

        content_res = self.tts.get_books_content(self.category)
        if content_res:
            return ("normal", content_res)
        return None

    def process_item(self, item) -> None:
        item_type, data = item
        if item_type == "retry":
            ebook_no, voice_code, chapter_idx, _ = data
            log.INFO(f"{self.worker_tag}: processing retry for book={ebook_no}, chapter={chapter_idx}, voice={voice_code}")
            self.tts.generate_chapter_audio_retries()
        else:
            log.INFO(f"{self.worker_tag}: processing normal audio generation for category={self.category}")
            self.tts.generate_chapter_audio_for_worker(self.category, use_short=config.GENERATE_SHORTS)
