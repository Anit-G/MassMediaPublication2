# Actionable Refactoring Plan: Step-by-Step

## PHASE 1: Database Schema & State Management (Steps 1-10)

### Step 1: Analyze Current Database Structure
**Objective:** Understand existing schema before modifications
- [ ] Open DB_Operations.py
- [ ] Document all current tables: column names, types, relationships
- [ ] Review `book_metadata.db3` schema using SQLite browser
- [ ] Identify which tables will be extended vs. newly created
- [ ] Check for existing foreign key constraints
- [ ] Document current insert/update/query methods used
- **Deliverable:** `docs/CURRENT_DB_SCHEMA.md`

### Step 2: Design New Database Tables
**Objective:** Define exact schema for state tracking
- [ ] Create `PROCESSING_STATE` table definition:
  ```
  - ebook_no (INTEGER, FK)
  - voice_code (INTEGER, FK)
  - category (TEXT, FK)
  - current_chapter_idx (INTEGER)
  - stage (TEXT: IDLE, AUDIO_GEN, VIDEO_GEN, UPLOAD, COMPLETE)
  - last_updated_timestamp (DATETIME)
  - error_log (TEXT)
  ```
- [ ] Create `CHAPTER_PROGRESS` table definition:
  ```
  - id (PRIMARY KEY)
  - ebook_no, voice_code, chapter_idx, category (FKs)
  - audio_status (NOT_STARTED, GENERATING, COMPLETED, FAILED)
  - audio_path (TEXT, nullable)
  - audio_generated_timestamp (DATETIME)
  - video_status, video_path, video_generated_timestamp (same pattern)
  - waveform_path (TEXT, nullable)
  - upload_status, youtube_url, upload_generated_timestamp (same pattern)
  - retry_count (INTEGER, default=0)
  - next_retry_timestamp (DATETIME, nullable)
  - error_message (TEXT, nullable)
  ```
- [ ] Create `SHORTS_PROGRESS` table (similar structure for shorts)
- [ ] Define all indexes (ebook_no, voice_code, chapter_idx for fast queries)
- **Deliverable:** `docs/NEW_DB_SCHEMA.sql`

### Step 4: Implement State Query Methods (Part A)
**Objective:** Create DB helper methods for reading state
- [ ] Edit the file: `Utils/DB_Operations.py`
- [ ] Implement method: `get_next_action(ebook_no, voice_code, category)`:
  ```
  - Query PROCESSING_STATE for this ebook/voice/category
  - Get current_chapter_idx
  - Query CHAPTER_PROGRESS for next action needed
  - Return (stage, chapter_idx, action_type)
  ```
- [ ] Implement method: `get_chapter_state(ebook_no, voice_code, chapter_idx)`:
  ```
  - Query CHAPTER_PROGRESS
  - Return dict with all status fields
  ```
- [ ] Implement method: `get_all_sync_status(ebook_no, voice_code, category)`:
  ```
  - Count chapters by status for each stage
  - Return dict with audio/video/upload progress counts
  ```
- [ ] Implement method: `can_start_video_gen(ebook_no, voice_code, chapter_idx)`:
  ```
  - Check audio_status == COMPLETED
  - Check audio_path exists and is readable
  - Check waveform_path not deleted
  - Return boolean
  ```
- [ ] Implement method: `can_start_upload(ebook_no, voice_code, chapter_idx)`:
  ```
  - Check video_status == COMPLETED
  - Check video_path exists
  - Check upload_status != COMPLETED (no duplicate)
  - Return boolean
  ```

### Step 5: Implement State Update Methods (Part B)
**Objective:** Create DB helper methods for writing state atomically
- [ ] In `Utils/DB_Operations.py`, implement: `update_chapter_status()`:
  ```
  def update_chapter_status(ebook_no, voice_code, chapter_idx, stage, status, **kwargs):
      - Use SQL transaction (BEGIN/COMMIT/ROLLBACK)
      - Update CHAPTER_PROGRESS.(stage_status) = status
      - If status == COMPLETED: update timestamp
      - If status == FAILED: update error_message, retry_count, next_retry_timestamp
      - If updating file paths: validate paths exist
      - Return success/failure
      - Log all updates for auditability
  ```
- [ ] Implement: `update_processing_state()`:
  ```
  def update_processing_state(ebook_no, voice_code, category, new_stage, new_chapter_idx):
      - Update PROCESSING_STATE.stage = new_stage
      - Update PROCESSING_STATE.current_chapter_idx = new_chapter_idx
      - Update PROCESSING_STATE.last_updated_timestamp = now()
      - Use transaction
  ```
- [ ] Implement: `mark_chapter_retry()`:
  ```
  def mark_chapter_retry(ebook_no, voice_code, chapter_idx, stage, error_msg):
      - Increment retry_count
      - Calculate next_retry_timestamp with exponential backoff
      - Set status to (stage_status = FAILED, with next_retry_timestamp)
      - If retry_count >= MAX_RETRIES: status = MANUAL_REVIEW_NEEDED
  ```
- [ ] Implement: `get_pending_retries()`:
  ```
  - Query CHAPTER_PROGRESS where status=FAILED and next_retry_timestamp <= now()
  - Return list of (ebook_no, voice_code, chapter_idx, stage)
  ```

### Step 10: Create Configuration for State Management
**Objective:** Centralize state-related configuration
- [ ] Open Config_vars.py
- [ ] Add section:
  ```
  # State Management
  DB_SCHEMA_VERSION = 2
  STATE_CHECK_INTERVAL_SECONDS = 5
  RETRY_MAX_ATTEMPTS = 3
  RETRY_BACKOFF_FACTOR = 2  # exponential: 30s, 60s, 120s
  RETRY_BASE_DELAY_SECONDS = 30
  
  # Pipeline Control
  ENABLE_AUDIO_GEN_WORKER = True
  ENABLE_VIDEO_GEN_WORKER = True
  ENABLE_UPLOAD_WORKER = True
  WORKER_THREAD_COUNT = 3
  
  # Storage Policies
  DELETE_AUDIO_AFTER_VIDEO = False  # Start conservative
  DELETE_VIDEO_AFTER_UPLOAD = False
  RETENTION_DAYS_AUDIO = 30
  RETENTION_DAYS_VIDEO = 90
  ARCHIVE_TO_CLOUD = False
  ```
- [ ] Document all new config options in `docs/CONFIG.md`
- **Deliverable:** Updated Config_vars.py

---

## PHASE 2: Worker Architecture (Steps 11-20)

### Step 11: Refactor TTS Module for Single-Chapter Processing
**Objective:** Convert TTS from batch to single-chapter mode
- [ ] Open TTS.py
- [ ] Current method: `run_tts_on_book(ebook_no, voice_code, category)` processes all chapters
- [ ] Create new method: `generate_chapter_audio()`:
  ```
  def generate_chapter_audio(ebook_no, voice_code, chapter_idx, category):
      - Load book JSON for ebook_no
      - Extract chapter[chapter_idx] (header + content)
      - Generate header audio → {ebook_no}_{voice_code}_{idx}_headsection.wav
      - Generate chapter audio → {ebook_no}_{voice_code}_{idx}_chapsection.wav
      - (Don't generate shorts yet)
      - Return (header_audio_path, chapter_audio_path)
  ```
- [ ] Keep old batch method for backward compatibility (deprecated)
- [ ] Move shorts generation to separate method: `generate_chapter_shorts_audio()`:
  ```
  def generate_chapter_shorts_audio(ebook_no, voice_code, chapter_idx, category, use_short=True):
      - Load chapter content
      - Split by sentences
      - Create batches (≤ 3min)
      - Generate shorts in folder: {ebook_no}_{voice_code}_{idx}_Shorts/
      - Return list of short audio paths
  ```
- [ ] Add parameter to control which sections to generate (header, chapter, shorts separately)
- **Deliverable:** Refactored TTS.py

### Step 12: Create AudioGenWorker Class
**Objective:** Standalone worker that generates audio one chapter at a time
- [ ] Create file: `Workers/AudioGenWorker.py`
- [ ] Class structure:
  ```
  class AudioGenWorker:
      def __init__(self, db_manager, config, ebook_no, voice_code, category):
          self.db_manager = db_manager
          self.config = config
          self.ebook_no = ebook_no
          self.voice_code = voice_code
          self.category = category
          self.logger = setup_logger(f"AudioGen_{ebook_no}_{voice_code}")
      
      def run(self):
          - Main loop that continuously finds next work
          - Calls process_next_chapter()
          - Sleeps between iterations
      
      def get_next_chapter_to_process(self):
          - Query: WHERE audio_status = NOT_STARTED
          - Order by chapter_idx ASC
          - Return chapter_idx (or None if done)
      
      def process_chapter(self, chapter_idx):
          - Try:
              - generate audio
          - Except:
              - Call mark_chapter_retry()
              - Log error
      
      def should_stop(self):
          - Check: all chapters audio_status = COMPLETED
          - Return boolean
  ```
- [ ] Add thread-safe logging
- [ ] Add graceful shutdown mechanism
- **Deliverable:** `Workers/AudioGenWorker.py`

### Step 13: Create VideoGenWorker Class
**Objective:** Standalone worker that generates video one chapter at a time
- [ ] Create file: `Workers/VideoGenWorker.py`
- [ ] Class structure (similar to AudioGenWorker):
  ```
  class VideoGenWorker:
      def __init__(self, db_manager, config, ebook_no, voice_code, category):
          # similar setup
      
      def run(self):
          - Main loop
      
      def get_next_chapter_to_process(self):
          - Query: WHERE audio_status = COMPLETED AND video_status = NOT_STARTED
          - Order by chapter_idx ASC
          - Return chapter_idx (or None)
      
      def process_chapter(self, chapter_idx):
          - Update DB: video_status = GENERATING
          - Get audio_path from DB
          - Verify audio file exists (readable)
          - Try:
              - Call VideoGen.generate_chapter_video()
              - Get back (video_path, waveform_path)
              - Update DB: video_status = COMPLETED, video_path, waveform_path, timestamp
              - IF config.DELETE_AUDIO_AFTER_VIDEO:
                  - Delete audio file
                  - Update DB: audio_status = AUDIO_ARCHIVED
          - Except:
              - Call mark_chapter_retry()
  ```
- [ ] Ensure it polls for audio availability (doesn't fail if audio not ready yet)
- **Deliverable:** `Workers/VideoGenWorker.py`

### Step 14: Create UploadWorker Class
**Objective:** Standalone worker that uploads video one chapter at a time
- [ ] Create file: `Workers/UploadWorker.py`
- [ ] Class structure:
  ```
  class UploadWorker:
      def __init__(self, db_manager, config, ebook_no, voice_code, category):
          # similar setup
          self.youtube_uploader = UpMonYouTube()  # existing uploader
      
      def run(self):
          - Main loop
      
      def get_next_chapter_to_process(self):
          - Query: WHERE video_status = COMPLETED AND upload_status = NOT_STARTED
          - Order by chapter_idx ASC
          - Return chapter_idx (or None)
      
      def process_chapter(self, chapter_idx):
          - Update DB: upload_status = UPLOADING
          - Get video_path from DB
          - Verify video file exists
          - Try:
              - Call youtube_uploader.upload_single_video(video_path)
              - Get youtube_url back
              - Update DB: upload_status = COMPLETED, youtube_url, timestamp
              - IF config.DELETE_VIDEO_AFTER_UPLOAD:
                  - Delete video file
                  - Update DB: video_status = VIDEO_ARCHIVED
          - Except (network timeout):
              - Call mark_chapter_retry() with exponential backoff
          - Except (API quota):
              - Update DB: upload_status = PAUSED_QUOTA_EXCEEDED
              - Stop worker (manual recovery needed)
  ```
- [ ] Handle YouTube API errors gracefully
- **Deliverable:** `Workers/UploadWorker.py`

### Step 15: Create Worker Orchestrator
**Objective:** Manage all three workers as coordinated pipeline
- [ ] Create file: `Workers/Orchestrator.py`
- [ ] Class structure:
  ```
  class PipelineOrchestrator:
      def __init__(self, db_manager, config):
          self.db_manager = db_manager
          self.config = config
          self.workers = {}  # {worker_type: [worker1, worker2, ...]}
          self.threads = {}  # {worker_id: thread}
          self.logger = setup_logger("Orchestrator")
      
      def initialize_workers(self, book_configs):
          # book_configs = [(ebook_no, voice_code, category), ...]
          - For each config:
              - IF ENABLE_AUDIO_GEN_WORKER: create AudioGenWorker
              - IF ENABLE_VIDEO_GEN_WORKER: create VideoGenWorker
              - IF ENABLE_UPLOAD_WORKER: create UploadWorker
              - Store in self.workers
      
      def start_all_workers(self):
          - For each worker in self.workers:
              - Create thread: thread = Thread(target=worker.run, daemon=True)
              - Store in self.threads
              - thread.start()
              - Log: "Started {worker_type}_{ebook_no}_{voice_code}"
      
      def monitor_workers(self):
          - Main monitoring loop:
              - Every 10 seconds:
                  - For each worker: get_all_sync_status()
                  - Print sync status
                  - IF any worker failed: alert & log
                  - IF all workers stopped: break
      
      def shutdown_gracefully(self):
          - Set stop_flag on all workers
          - Wait for threads with timeout (30s)
          - Force kill if timeout
          - Save state to DB
      
      def resume_from_checkpoint(self):
          - Query PROCESSING_STATE for all active books
          - Load worker state from DB
          - Resume from current_chapter_idx
  ```
- [ ] Add signal handlers (SIGTERM, Ctrl+C)
- **Deliverable:** `Workers/Orchestrator.py`

### Step 16: Refactor VideoGen Module
**Objective:** Separate single-chapter video generation from batch
- [ ] Open VideoGenerator.py
- [ ] Current method: `video_gen_book()` processes all chapters
- [ ] Create new method: `generate_chapter_video()`:
  ```
  def generate_chapter_video(ebook_no, voice_code, chapter_idx, audio_path, category):
      - Load book metadata (BGM, BGP, BGV, title, author)
      - Call __generate_waveform(audio_path) → waveform_path
      - Call __generate_video(audio_path, waveform_path, ...) → video_path
      - Return (video_path, waveform_path)
  ```
- [ ] Keep batch method for backward compatibility
- [ ] Ensure single-chapter can be called independently
- **Deliverable:** Refactored VideoGenerator.py

### Step 17: Refactor UpMonYouTube for Single-Chapter Uploads
**Objective:** Decouple upload logic from batch processing
- [ ] Open UpMonYoutube.py
- [ ] Current method: `upload_single_video()` (may already exist)
- [ ] Ensure it returns: `youtube_url`
- [ ] Create helper: `get_video_metadata()`:
  ```
  def get_video_metadata(ebook_no, voice_code, chapter_idx, category):
      - Load from DB: title, author, description template
      - Render metadata for this specific chapter
      - Return (title, description, tags, category)
  ```
- [ ] Update upload method to use consistent metadata
- **Deliverable:** Updated UpMonYoutube.py

### Step 18: Create Worker Base Class
**Objective:** Share common logic across all workers
- [ ] Create file: `Workers/BaseWorker.py`
- [ ] Abstract class:
  ```
  class BaseWorker(ABC):
      def __init__(self, db_manager, config, ebook_no, voice_code, category):
          self.db_manager = db_manager
          self.config = config
          self.ebook_no = ebook_no
          self.voice_code = voice_code
          self.category = category
          self.stop_flag = False
          self.logger = self._setup_logger()
      
      @abstractmethod
      def get_next_chapter_to_process(self):
          pass
      
      @abstractmethod
      def process_chapter(self, chapter_idx):
          pass
      
      def run(self):
          while not self.stop_flag:
              chapter_idx = self.get_next_chapter_to_process()
              if chapter_idx is None:
                  self.logger.info("No more chapters. Sleeping...")
                  time.sleep(self.config.STATE_CHECK_INTERVAL_SECONDS)
                  continue
              
              self.logger.info(f"Processing chapter {chapter_idx}")
              self.process_chapter(chapter_idx)
      
      def stop(self):
          self.stop_flag = True
      
      def _setup_logger(self):
          - Return logger with worker-specific name/file
  ```
- [ ] Have AudioGenWorker, VideoGenWorker, UploadWorker inherit from this
- **Deliverable:** `Workers/BaseWorker.py`

### Step 19: Add Worker Initialization
**Objective:** Create entry point for starting workers
- [ ] Create file: `main_pipeline.py` (or add to existing entry point)
- [ ] Function:
  ```
  def main():
      - Parse CLI args: ebook_no, voice_codes, categories
      - Initialize DB (call init_database())
      - Load config
      - Create Orchestrator
      - Load book configs from DB or args
      - Register workers with Orchestrator
      - Start all workers
      - Call monitor_workers() (blocking) until Ctrl+C
      - Gracefully shutdown
  ```
- [ ] Add CLI arg parser:
  ```
  --ebook-no 1
  --voice-codes 3,7,13
  --categories fiction
  --workers audio,video,upload (or subset)
  --mode fresh (or resume)
  ```
- **Deliverable:** `main_pipeline.py` + updated CLI interface

### Step 20: Write Worker Integration Tests
**Objective:** Verify workers coordinate correctly
- [ ] Create file: `Tests/test_workers.py`
- [ ] Test cases:
  ```
  - test_audio_gen_worker_single_chapter()
  - test_video_gen_worker_waits_for_audio()
  - test_upload_worker_waits_for_video()
  - test_workers_coordinate_correctly()
  - test_worker_retry_logic()
  - test_worker_graceful_shutdown()
  - test_chapter_state_consistency_during_processing()
  ```
- [ ] Use mock/stub for TTS, VideoGen, YouTube upload
- **Deliverable:** `Tests/test_workers.py`

---

## PHASE 3: Error Handling & Recovery (Steps 21-25)

### Step 21: Implement Retry Logic with Exponential Backoff
**Objective:** Automatic recovery from transient failures
- [ ] Create file: `Utils/RetryManager.py`
- [ ] Function:
  ```
  def calculate_next_retry_time(retry_count, base_delay=30, factor=2):
      - delay = base_delay * (factor ^ retry_count)
      - Add jitter: delay += random(1, delay * 0.1)
      - Cap at max: min(delay, 7200)  # max 2 hours
      - Return now() + delay
  
  def should_retry(chapter_status):
      - Check: status.retry_count < MAX_RETRIES
      - Check: status.next_retry_timestamp <= now()
      - Check: status.error_type is retryable (not INVALID_INPUT)
      - Return boolean
  ```
- [ ] Update workers to call this before retrying
- **Deliverable:** `Utils/RetryManager.py`

### Step 24: Add Health Check Endpoint
**Objective:** Monitor worker health externally
- [ ] Create file: `Utils/HealthChecker.py`
- [ ] Function:
  ```
  def get_system_health():
      - Disk space check
      - DB connection check
      - Worker active status
      - Failed chapters count
      - Pending retry count
      - Return HealthReport object
  
  def endpoint_health_json():
      - GET /health
      - Return JSON with all metrics
  ```
- [ ] Optional: Add simple HTTP server in orchestrator
- **Deliverable:** `Utils/HealthChecker.py`

---

## PHASE 4: Cleanup & Storage Management (Steps 26-30)

### Step 26: Implement File Retention Policies
**Objective:** Automatic cleanup based on lifecycle stage
- [ ] Create file: `Utils/StorageManager.py`
- [ ] Function:
  ```
  def cleanup_audio_files():
      - Query: chapters where audio_status = AUDIO_ARCHIVED
      - Check: file modified time > RETENTION_DAYS_AUDIO
      - IF config.DELETE_AUDIO_AFTER_VIDEO:
          - Delete audio file
          - Update DB: audio_path = NULL, audio_status = DELETED
          - Log deletion
  
  def cleanup_waveform_files():
      - Query: chapters where video_status = COMPLETED
      - Check: waveform created > 7 days ago (safety buffer)
      - Delete waveform file
      - Update DB: waveform_path = NULL
      - Log deletion
  
  def cleanup_video_files():
      - Query: chapters where upload_status = COMPLETED
      - Check: video modified time > RETENTION_DAYS_VIDEO
      - IF config.DELETE_VIDEO_AFTER_UPLOAD:
          - Delete video file
          - Update DB: video_path = NULL, video_status = DELETED
          - Log deletion
  ```
- [ ] Call this in a scheduled background task (hourly)
- **Deliverable:** `Utils/StorageManager.py`

### Step 30: Create Storage Management Tests
**Objective:** Verify cleanup doesn't corrupt data
- [ ] Create file: `Tests/test_storage_mgmt.py`
- [ ] Test cases:
  ```
  - test_audio_cleanup_after_retention_period()
  - test_waveform_cleanup_after_video_gen()
  - test_video_cleanup_after_upload()
  - test_cleanup_respects_config_flags()
  - test_cleanup_doesnt_delete_recent_files()
  - test_storage_report_accuracy()
  ```
- **Deliverable:** `Tests/test_storage_mgmt.py`

---

## Final Checklist

### Code Quality
- [ ] All code has docstrings
- [ ] All public methods have type hints
- [ ] All config values are documented
- [ ] No hardcoded paths (all in config)
- [ ] All threads use daemon=False (except background tasks)

### Testing
- [ ] Run full test suite: `pytest Tests/`
- [ ] Run coverage: `pytest --cov=. Tests/`
- [ ] Run E2E test with real small book
- [ ] Test restart/resume scenario
- [ ] Test error recovery (retry logic)

### Documentation
- [ ] All new files have comments
- [ ] All complex logic has inline comments
- [ ] README updated
- [ ] Configuration guide updated
- [ ] All docs pass spell check

### Performance
- [ ] Profiling shows no obvious bottlenecks
- [ ] Database queries are indexed
- [ ] No memory leaks (test with 1000+ chapters)
- [ ] Storage cleanup working correctly

### Deployment
- [ ] Migration script tested on copy of real DB
- [ ] Backward compatibility verified
- [ ] Deprecation warnings logged but don't break
- [ ] Fresh install works from scratch
- [ ] Resume from checkpoint works
