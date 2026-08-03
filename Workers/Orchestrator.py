from __future__ import annotations
import signal
import threading
import time
import os
from typing import Dict, List, Optional

import Utils.Central_Logger as log
import Utils.Config_vars as config
from Utils.DB_Operations import DBOps
from TTS.TTS import TTS
from VideoGen.VideoGenerator import VideoGen
from VideoGen.UpMonYoutube import UpMonYouTube
from .AudioGenWorker import AudioGenWorker
from .UploadWorker import UploadWorker
from .VideoGenWorker import VideoGenWorker


class WorkerOrchestrator:
    """Coordinated pipeline orchestrator for audio, video, and upload workers."""

    def __init__(
        self,
        poll_interval: Optional[float] = None,
        audio_runs: int = 1,
        video_runs: int = 1,
        upload_runs: int = 1
    ):
        self.db_manager = DBOps()
        self.categories = self._load_categories()
        self.poll_interval = poll_interval if poll_interval is not None else config.STATE_CHECK_INTERVAL_SECONDS
        self.tts = TTS(dist_weight=0.35, mixer=7)
        self.video_gen = VideoGen()
        
        self.audio_runs = audio_runs
        self.video_runs = video_runs
        self.upload_runs = upload_runs
        
        self.workers: List = []
        self.threads: List[threading.Thread] = []

    def _load_categories(self) -> List[str]:
        try:
            self.db_manager._cursor.execute("SELECT DISTINCT category FROM YOUTUBE_MAP")
            rows = self.db_manager._cursor.fetchall()
            return [row[0] for row in rows if row]
        except Exception as e:
            log.ERROR(f"Orchestrator: error loading categories: {e}")
            return ["cat(RS)", "cat(MS)", "cat(WE)", "cat(LM)"]

    def _get_voice_codes(self, category: str) -> List[int]:
        return self.db_manager.get_voice_codes(category)

    def start(self) -> None:
        log.INFO("Orchestrator: starting pipeline worker threads")
        
        for _ in range(self.audio_runs):
            self._start_audio_workers()
        for _ in range(self.video_runs):
            self._start_video_workers()
        for _ in range(self.upload_runs):
            self._start_upload_workers()

    def _start_audio_workers(self) -> None:
        if not config.ENABLE_AUDIO_GEN_WORKER:
            log.INFO("Orchestrator: audio generation workers are disabled")
            return

        for category in self.categories:
            worker = AudioGenWorker(self.tts, category, poll_interval=self.poll_interval)
            t = threading.Thread(target=worker.run, daemon=True, name=f"AudioWorker-{category}")
            self.workers.append(worker)
            self.threads.append(t)
            t.start()
            log.INFO(f"Orchestrator: audio worker thread started for category={category}")

    def _start_video_workers(self) -> None:
        if not config.ENABLE_VIDEO_GEN_WORKER:
            log.INFO("Orchestrator: video generation workers are disabled")
            return

        for category in self.categories:
            worker = VideoGenWorker(self.video_gen, category, poll_interval=self.poll_interval)
            t = threading.Thread(target=worker.run, daemon=True, name=f"VideoWorker-{category}")
            self.workers.append(worker)
            self.threads.append(t)
            t.start()
            log.INFO(f"Orchestrator: video worker thread started for category={category}")

    def _start_upload_workers(self) -> None:
        if not config.ENABLE_UPLOAD_WORKER:
            log.INFO("Orchestrator: upload workers are disabled")
            return

        for category in self.categories:
            uploader = UpMonYouTube(category)
            worker = UploadWorker(uploader, category, poll_interval=self.poll_interval)
            t = threading.Thread(target=worker.run, daemon=True, name=f"UploadWorker-{category}")
            self.workers.append(worker)
            self.threads.append(t)
            t.start()
            log.INFO(f"Orchestrator: upload worker thread started for category={category}")

    def stop(self) -> None:
        log.INFO("Orchestrator: stopping pipeline cleanly")
        for worker in self.workers:
            if hasattr(worker, 'stop'):
                worker.stop()
        
        for t in self.threads:
            if t.is_alive():
                t.join(timeout=2.0)
        log.INFO("Orchestrator: pipeline stopped")
