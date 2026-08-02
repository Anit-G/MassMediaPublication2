User: do you understand how tts audio generation works and how video generation and how video uploading flow works as written to in this codebase. I want you to map it out for each around mainly the fact that entire books is converted to shorts .wav files and full length audio wav files for all chapters in the book.json that was scrapped and same audios are converted to full length videos and written to disk which means a lot of disk usage. 

Workspace: Collecting workspace information# MassMediaPublication Workflow Analysis

I'll map out the three main flows: TTS audio generation, video generation, and uploading.

## 1. TTS Audio Generation Flow

**Entry Point:** `TTS.__call__` (voice_codes, category)

```
Book JSON (book_{ebook_no}.json)
    ↓
For each voice_code in voice_codes:
    ↓
[__run_tts_on_book] processes each chapter:
    ├─ Split chapter into:
    │  ├─ Header (chapter title)
    │  └─ Content (chapter body)
    │
    ├─ Generate header audio:
    │  └─ {ebook_no}_{voice_code}_{idx}_headsection.wav
    │
    ├─ Generate chapter audio:
    │  └─ {ebook_no}_{voice_code}_{idx}_chapsection.wav
    │
    └─ IF use_short=True:
       └─ [__generate_shorts_aud]:
          ├─ Split chapter content by sentences
          ├─ Create batches (≤3min YouTube limit)
          └─ Generate shorts:
             └─ {ebook_no}_{voice_code}_{idx}_Shorts/short_00.wav
                                                      short_01.wav
                                                      ... (multiple)
```

**Storage:** `./Data/AudFiles/Book_{ebook_no}/`

**Key Detail:** Each voice gets **independent** audio files for the same chapter content.

---

## 2. Video Generation Flow

**Entry Point:** [`VideoGen.video_gen_book`](VideoGen/VideoGenerator.py) → iterates via [`video_compiler`](VideoGen/VideoGenerator.py)

### For Each Chapter Section (Main Video):

```
Audio file: {ebook_no}_{voice_code}_{idx}_chapsection.wav
    ↓
[__concatenate_aud] - only for FULL_VIDEO:
    └─ Concatenate ALL chapter audios → {ebook_no}_{voice_code}_FULL.mp3
    
Template lookup: book_{ebook_no}
    ├─ BGM: background music file
    ├─ BGP: background picture/video
    └─ BGV: alternative background video
    
[__generate_waveform]:
    ├─ Input: chapter audio
    ├─ Process: 28 frequency bands, bandpass filtering
    └─ Output: {ebook_no}_{voice_code}_{idx}_waveform.mp4
    
[__generate_video] or [__generate_full_video]:
    ├─ Combine:
    │  ├─ Background video (BGP or BGV)
    │  ├─ Waveform visualization
    │  ├─ Dialog audio (normalized)
    │  └─ BGM (30% volume)
    │
    └─ Output: {ebook_no}_{voice_code}_{idx}_videosection.mp4
              (or FULL_{ebook_no}_{voice_code}_videosection.mp4)
```

**Storage:** `./Data/OutputVideos/Book_{ebook_no}/`

### For Shorts (if enabled):

```
Shorts audio files: {ebook_no}_{voice_code}_{idx}_Shorts/short_*.wav
    ↓
For each short_XX.wav:
    ├─ [__generate_waveform]
    └─ [__generate_video]
         └─ Output: {signature}_videoshort_{idx}.mp4
```

---

## 3. Upload Flow

**Entry Point:** `UpMonYouTube.upload_single_video`

```
Get next section to upload: get_section_to_upload(ebook_no, voice_code)
    ↓
Upload Main Video:
    ├─ File: {ebook_no}_{voice_code}_{idx}_videosection.mp4
    ├─ Title: "{Book Title} Chapter #{section_no} by {narrator}"
    ├─ Description: templated with book/author/music info
    ├─ Thumbnail: book_{ebook_no}.jpg
    └─ Status → "UPLOADED"
    
Upload Shorts (if no_shorts > 0):
    ├─ For each short_{idx}.mp4
    ├─ Title: "{Book Title} Ch {section} Short #{idx+1} by {narrator}"
    └─ Status → "UPLOADED"
    
Get next section → Loop until all chapters done
    ↓
If all sections uploaded:
    └─ [full_video_compiler]:
       ├─ [__concatenate_aud]: Merge all chapter audios
       ├─ [__generate_full_video]: Create full-length video
       └─ [upload_full_video]: Upload as "[Full Book Release]"
```

---

## Disk Usage Analysis

### Per Book with N chapters and M voice codes:

| Component | Files | Size Impact |
|-----------|-------|-------------|
| **Chapter Audio** | N × M × 2 (head + chap) | ~40-100MB per chapter |
| **Shorts Audio** | N × M × S (S=avg shorts/chapter) | ~20-50MB per chapter |
| **Waveform Videos** | N × M + (N × M × S) | ~100-300MB per chapter |
| **Main Videos** | N × M | ~500MB-2GB per chapter |
| **Full Video** | M | ~2-5GB per full video |
| **TOTAL** | ≈ 2N×M + S×M | **~10-20GB per book** |

### Optimization Issues:

1. **Waveform files** kept by default (`RETAIN_WF = True` in Config_vars.py)
2. **All audio formats** (.wav for TTS, .mp3 for concatenation, .wav for shorts)
3. **Multiple voice renderings** of same content (no deduplication)
4. **Full video separately generated** even though chapters already uploaded

### Specific Example from codebase:

Book 11 ("Alice in Wonderland") with multiple voices shows this duplication in book_metadata.db3:
- Voice 3, 7, 13, 17, 18, 23, 24, 27 all have identical chapter sections
- Each storing separate audio files (all from same book text)

---

## Key Data Flow Points

1. **JSON → Audio:** [`TTS.run_tts_on_book`](TTS/TTS.py) reads from `./Data/JSONLib/book_{ebook_no}.json`
2. **Audio → Metadata:** `DBOps.insert_aud` stores file paths in book_metadata.db3
3. **Metadata → Video:** `VideoGen.video_gen_book` queries DB for audio paths
4. **Video → Upload:** `UpMonYouTube` reads output video paths and uploads sequentially

This creates significant disk I/O and storage overhead, especially with the choice to retain waveform files.

User: I want to plan out the refactoring of the code such that I generate 1 chapter's audio and then generate the video for that chapter and that is per category. The thing to take care of is tracking of generation progress like at any given run of the program it should be keenly aware of what has been generated for audio and video and upload and what needs to be generated next even if each of those steps is out of sync. Suppose ebook no 1 is in question and audio gen is on chapter 5 while video gen is on chapter 3 and upload has only uploaded till 1. Every step should know where it is and what is next for generation/action. DON'T write any code only do PLANNING.

GitHub Copilot: # Refactoring Plan: Sequential Per-Chapter Processing with State Tracking

## Current Architecture Problems

1. **Batch Processing:** All chapters generated for one voice before moving to next voice
2. **Decoupled States:** No real-time awareness of cross-step progress
3. **Storage Bloat:** All audio/waveforms kept before any video generation
4. **Sync Issues:** Audio gen, video gen, and upload can be wildly out of sync with no coordination

---

## Proposed Architecture: Pipeline with State Tracking

### 1. State Management Layer

#### Single Source of Truth: Enhanced Database Schema

```
book_metadata.db3 (restructure):

PROCESSING_STATE table:
├─ ebook_no (PK)
├─ voice_code (PK)
├─ category (PK)
├─ current_chapter_idx
├─ stage (enum: IDLE, AUDIO_GEN, VIDEO_GEN, UPLOAD, COMPLETE)
├─ last_updated_timestamp
├─ error_log (for rollback/retry logic)

CHAPTER_PROGRESS table:
├─ ebook_no (FK)
├─ voice_code (FK)
├─ chapter_idx (PK)
├─ category (FK)
├─ audio_status (enum: NOT_STARTED, GENERATING, COMPLETED, FAILED)
├─ audio_path (nullable)
├─ audio_generated_timestamp
├─ video_status (enum: NOT_STARTED, GENERATING, COMPLETED, FAILED)
├─ video_path (nullable)
├─ waveform_path (nullable - delete after video gen)
├─ video_generated_timestamp
├─ upload_status (enum: NOT_STARTED, UPLOADING, COMPLETED, FAILED)
├─ youtube_url (nullable)
├─ upload_generated_timestamp

SHORTS_PROGRESS table:
├─ ebook_no (FK)
├─ voice_code (FK)
├─ chapter_idx (FK)
├─ short_idx (PK)
├─ category (FK)
├─ audio_status
├─ video_status
├─ upload_status
└─ youtube_url
```

#### State Query Methods:
```
get_next_action(ebook_no, voice_code, category):
    → Returns (stage, chapter_idx, action_type)
    
get_chapter_state(ebook_no, voice_code, chapter_idx):
    → Returns complete state dict for that chapter
    
get_all_sync_status(ebook_no, voice_code, category):
    → Returns (audio_progress, video_progress, upload_progress)
    
can_start_video_gen(ebook_no, voice_code, chapter_idx):
    → Checks if audio_status == COMPLETED AND waveform not deleted
    
can_start_upload(ebook_no, voice_code, chapter_idx):
    → Checks if video_status == COMPLETED AND not already uploaded
```

---

### 2. Processing Pipeline Architecture

#### Three Independent Worker Threads/Processes

```
ARCHITECTURE:

┌──────────────────────────────────────────────────┐
│         Main Orchestrator (State Watcher)        │
│  - Monitors PROCESSING_STATE & CHAPTER_PROGRESS │
│  - Detects completion/failures                   │
│  - Triggers cleanup & next steps                 │
└──────────────────────────────────────────────────┘
         ↓           ↓           ↓
    ┌────────────┬────────────┬────────────┐
    │  WORKER 1  │  WORKER 2  │  WORKER 3  │
    │ AUDIO_GEN  │ VIDEO_GEN  │   UPLOAD   │
    └────────────┴────────────┴────────────┘
         ↓           ↓           ↓
    ┌────────────┬────────────┬────────────┐
    │   Query:   │   Query:   │   Query:   │
    │ next audio │ next video │ next bulk  │
    │   to gen   │   to gen   │   to send  │
    └────────────┴────────────┴────────────┘
         ↓           ↓           ↓
┌──────────────────────────────────────────────────┐
│         CHAPTER_PROGRESS (Shared State)          │
│  Lock-protected writes, concurrent reads         │
└──────────────────────────────────────────────────┘
```

#### Worker Logic Pattern:

**AUDIO_GEN Worker:**
```
while True:
    next_task = get_next_unstarted_audio(ebook_no, voice_code)
    if none:
        sleep(check_interval)
        continue
    
    update_status(chapter, AUDIO_GEN, "GENERATING")
    
    try:
        generate_chapter_audio(chapter)
        update_status(chapter, AUDIO_GEN, "COMPLETED", audio_path)
        
        # DO NOT DELETE - video gen needs it
        # DO NOT proceed to next chapter yet if video gen needs it
        
    except Exception as e:
        update_status(chapter, AUDIO_GEN, "FAILED", error=e)
        update_schedule_retry(chapter)
```

**VIDEO_GEN Worker:**
```
while True:
    next_task = get_next_ready_video(ebook_no, voice_code)
    # next_ready = audio_status==COMPLETED AND video_status==NOT_STARTED
    
    if none:
        sleep(check_interval)
        continue
    
    update_status(chapter, VIDEO_GEN, "GENERATING")
    
    try:
        generate_chapter_video(chapter, audio_path)
        update_status(chapter, VIDEO_GEN, "COMPLETED", video_path, waveform_path)
        
        # NOW safe to delete audio file (if configured)
        if DELETE_AUDIO_AFTER_VIDEO:
            delete_file(audio_path)
            update_status(chapter, audio_status="AUDIO_ARCHIVED")
        
        # NOW safe to delete waveform after a retention period
        
    except Exception as e:
        update_status(chapter, VIDEO_GEN, "FAILED", error=e)
```

**UPLOAD Worker:**
```
while True:
    next_task = get_next_ready_upload(ebook_no, voice_code)
    # next_ready = video_status==COMPLETED AND upload_status==NOT_STARTED
    
    if none:
        sleep(check_interval)
        continue
    
    update_status(chapter, UPLOAD, "UPLOADING")
    
    try:
        youtube_url = upload_to_youtube(video_path)
        update_status(chapter, UPLOAD, "COMPLETED", youtube_url)
        
        # NOW safe to delete video file (if configured)
        if DELETE_VIDEO_AFTER_UPLOAD:
            delete_file(video_path)
            update_status(chapter, video_status="VIDEO_ARCHIVED")
            
    except Exception as e:
        update_status(chapter, UPLOAD, "FAILED", error=e)
        # Retry logic with exponential backoff
```

---

### 3. State Tracking Details

#### Per-Process State Awareness

**Example Query Scenarios:**

```
SCENARIO 1: Program restart after crash
├─ Load all PROCESSING_STATE rows
├─ For ebook_no=1, voice_code=7, category="fiction"
├─ Query: WHERE ebook_no=1 AND voice_code=7 AND category="fiction"
├─ Find: audio_gen stopped at ch 5, video_gen at ch 3, upload at ch 1
├─ Actions:
│  ├─ AUDIO_GEN: Resume from ch 6 (ch 5 may be partial)
│  ├─ VIDEO_GEN: Check ch 3 status - if audio exists, continue; else wait
│  └─ UPLOAD: Check ch 1 status - if video uploading failed, retry
└─ Result: Each worker picks up exactly where it left off

SCENARIO 2: Uneven progress
├─ Audio ch 5 complete, Video ch 3 complete, Upload ch 1 complete
├─ AUDIO_GEN: Tries to start ch 6 → success
├─ VIDEO_GEN: Tries to start ch 4 → checks if ch 4 audio ready
│  ├─ If audio ch 4 done → proceed
│  ├─ If audio ch 4 not done → sleep & retry
│  └─ If audio ch 4 failed → log & wait for manual intervention
├─ UPLOAD: Tries to start ch 2 → checks if ch 2 video ready
└─ Result: Natural pipeline flow, no blocking

SCENARIO 3: Selective regeneration
├─ User wants to re-generate video for ch 3 (remix audio)
├─ Set: chapter_progress[ch3].video_status = "NOT_STARTED"
├─ VIDEO_GEN worker detects & regenerates
├─ Audio file NOT deleted (was already used)
└─ Result: Seamless re-processing of single chapter
```

---

### 4. Data Flow Redesign

#### Old Flow (Batch):
```
TTS all chapters → All audios on disk → VideoGen all videos → All videos on disk → Upload
```

#### New Flow (Sequential + Pipelined):

```
For each chapter:
    ┌─────────────────────────────────────┐
    │ AUDIO_GEN (Chapter N)               │
    │ - Generate chapter audio            │
    │ - Update CHAPTER_PROGRESS.audio     │
    │ - Keep file accessible              │
    └─────────────────────────────────────┘
                    ↓
    ┌─────────────────────────────────────┐
    │ VIDEO_GEN (Chapter N)               │
    │ - Poll for audio completion         │
    │ - Read audio file → generate video  │
    │ - Update CHAPTER_PROGRESS.video     │
    │ - Optionally delete audio (config)  │
    └─────────────────────────────────────┘
                    ↓
    ┌─────────────────────────────────────┐
    │ UPLOAD (Chapter N)                  │
    │ - Poll for video completion         │
    │ - Read video → upload to YouTube    │
    │ - Update CHAPTER_PROGRESS.upload    │
    │ - Optionally delete video (config)  │
    └─────────────────────────────────────┘

Concurrently: Ch 1 uploading, Ch 2 generating video, Ch 3 generating audio
```

---

### 5. Error Handling & Recovery

#### Failure States:

```
AUDIO_GEN Failures:
├─ TTS API down → Retry with exponential backoff (30s, 60s, 120s...)
├─ Incomplete audio → Mark AUDIO_GEN="FAILED", log error details
├─ Disk full → Alert & pause pipeline
└─ Recovery: Manual fix → Set status back to "NOT_STARTED"

VIDEO_GEN Failures:
├─ Audio path corrupted → Mark VIDEO_GEN="FAILED"
├─ BGM/BGP missing → Alert & pause
├─ FFMPEG crash → Retry same chapter
└─ Recovery: Delete corrupted video files, retry

UPLOAD Failures:
├─ Network timeout → Retry with backoff
├─ YouTube API quota exceeded → Pause & notify
├─ Video already exists → Mark UPLOAD="COMPLETED" with URL
└─ Recovery: Manual retry or skip
```

#### Retry Strategy:

```
CHAPTER_PROGRESS enhancements:
├─ retry_count (int, increment each failure)
├─ max_retries (config, default=3)
├─ last_error_timestamp
├─ next_retry_timestamp (exponential backoff)
├─ error_message (detailed log)

Retry Logic:
├─ On failure: increment retry_count
├─ Calculate: next_retry = now + (backoff_factor ^ retry_count)
├─ If retry_count >= max_retries: mark MANUAL_REVIEW_NEEDED
└─ Worker sleeps until next_retry_timestamp
```

---

### 6. Monitoring & Observability

#### Real-time Status Dashboard Queries:

```
PROCESSING_STATUS view:
├─ ebook_no | voice_code | category | stage | current_ch | total_ch | % complete
├─ Audio Progress: ch 5/12 complete (42%)
├─ Video Progress: ch 3/12 complete (25%)
├─ Upload Progress: ch 1/12 complete (8%)
└─ Estimated time remaining (based on avg times)

FAILURE DASHBOARD:
├─ Failed chapters: ch 7 (audio), ch 11 (video), ch 2 (upload)
├─ Retry status: ch 7 waiting (retry in 2m), ch 11 (retry in 5m)
├─ Manual interventions needed: ch 2 (API quota exceeded)

DISK USAGE:
├─ Current audio files: 2.3GB
├─ Current video files: 156MB
├─ Retention policy: audio=1 month, video=2 months after upload
└─ Projected space needed: 45GB
```

#### Logging:

```
NEW LOG STRUCTURE:

book_1_voice_7_processing.log:
├─ [2026-04-26 10:15:32] [AUDIO_GEN] ch_1 STARTED
├─ [2026-04-26 10:15:52] [AUDIO_GEN] ch_1 COMPLETED (20.3s)
├─ [2026-04-26 10:16:15] [VIDEO_GEN] ch_1 STARTED
├─ [2026-04-26 10:16:55] [VIDEO_GEN] ch_1 COMPLETED (40.2s)
├─ [2026-04-26 10:17:10] [UPLOAD] ch_1 STARTED
├─ [2026-04-26 10:18:00] [UPLOAD] ch_1 COMPLETED → https://youtu.be/xxx
├─ [2026-04-26 10:18:05] [CLEANUP] ch_1 audio deleted (archived state)
└─ [2026-04-26 10:20:00] [AUDIO_GEN] ch_2 STARTED
```

---

### 7. Configuration für Pipeline Control

#### New Config Section:

```
PIPELINE_CONFIG:
├─ ENABLE_WORKERS: [AUDIO_GEN, VIDEO_GEN, UPLOAD]
├─ WORKER_COUNT: (1:sequential, 3:parallel for different ebooks)
├─ CHECK_INTERVAL: 5 seconds (poll for next task)
├─ RETRY_MAX_ATTEMPTS: 3
├─ BACKOFF_STRATEGY: exponential (30s, 60s, 120s)

STORAGE_CONFIG:
├─ DELETE_AUDIO_AFTER_VIDEO: True (frees space immediately)
├─ DELETE_VIDEO_AFTER_UPLOAD: True (but keep for X days)
├─ RETENTION_DAYS_AUDIO: 30
├─ RETENTION_DAYS_VIDEO: 90 (safety buffer before final delete)
├─ ARCHIVE_TO_CLOUD: optional (S3, Google Cloud)

RESUME_CONFIG:
├─ RESUME_FROM_STATE: True (read DB on startup)
├─ CHECKPOINT_INTERVAL: every 10 chapters
├─ LOG_LEVEL: DEBUG | INFO | WARNING
```

---

### 8. Implementation Phases

#### Phase 1: Database & State Management
- [ ] Design & implement `PROCESSING_STATE` table
- [ ] Design & implement `CHAPTER_PROGRESS` table
- [ ] Create state query methods (`get_next_action`, etc.)
- [ ] Migration script for existing data

#### Phase 2: Worker Architecture
- [ ] Refactor TTS module → `AudioGenWorker` (single chapter at a time)
- [ ] Refactor VideoGen → `VideoGenWorker` (polls for ready audio)
- [ ] Create `UploadWorker` (polls for ready video)
- [ ] Implement thread/process orchestration

#### Phase 3: State Synchronization
- [ ] Implement thread-safe DB writes (locks/transactions)
- [ ] Implement retry logic with exponential backoff
- [ ] Implement error recovery mechanisms
- [ ] Add logging to all state transitions

#### Phase 4: Monitoring & Observability
- [ ] Build status dashboard queries
- [ ] Create monitoring logs
- [ ] Add metrics collection (timing, success rates)
- [ ] Build CLI tool to inspect/manually adjust state

#### Phase 5: Cleanup & Optimization
- [ ] Implement file retention policies
- [ ] Archive old waveforms
- [ ] Optional cloud storage integration

---

### 9. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **DB as Source of Truth** | Single restart point; avoids file-system state confusion |
| **Polling vs Events** | Simpler to implement; tolerates DB delays; supports state inspection |
| **Per-worker responsibility** | Clear separation; easy to debug; can be parallelized later |
| **Audio not deleted immediately** | Video gen needs it; allows re-use if video fails |
| **Shorts processed after chapters** | Lower priority; after video gen proves audio quality |
| **SQL transactions for state** | Prevents partial updates; rollback on worker crash |
| **Config-driven cleanup** | Flexibility for different storage scenarios |

---

### 10. Example: Processing Scenario Step-By-Step

```
INITIAL STATE:
ebook_no=1, voice_code=7, 12 chapters, 3 categories

STARTUP (after previous crash):
├─ Load PROCESSING_STATE: found ebook_1_voice_7
│  └─ stage=AUDIO_GEN, current_chapter=5
├─ Load CHAPTER_PROGRESS:
│  ├─ Chapters 1-4: COMPLETED (all stages)
│  ├─ Chapter 5: audio=GENERATING (incomplete - resume)
│  ├─ Chapters 6-12: NOT_STARTED
├─ Orchestrator assigns tasks:
│  ├─ AUDIO_GEN: Resume ch 5 (may be partial - delete & regenerate)
│  ├─ VIDEO_GEN: Wait until ch 5 audio ready, then start ch 1
│  └─ UPLOAD: Start ch 1 immediately (video should be ready from previous run)

T+0s: STARTUP COMPLETE
├─ AUDIO_GEN picks up: ch 5 audio (generate from scratch)
├─ VIDEO_GEN is idle (ch 1 video ready, checking before upload)
└─ UPLOAD: ch 1 video → YouTube (already done? check status)

T+25s: ch 5 audio complete
├─ AUDIO_GEN updates: ch 5 audio_status = COMPLETED
├─ AUDIO_GEN moves to: ch 6 audio generation
├─ VIDEO_GEN detects: ch 5 audio ready → starts ch 5 video gen

T+35s: UPLOAD completes ch 1
├─ UPLOAD updates: ch 1 upload_status = COMPLETED
├─ UPLOAD deletes: ch 1 video file (if configured)
├─ UPLOAD moves to: ch 2 video (already generated? poll)

T+65s: ch 6 audio complete, ch 5 video complete
├─ AUDIO_GEN: ch 7 audio generation
├─ VIDEO_GEN: ch 6 video generation
├─ UPLOAD: waiting (ch 2 video not ready yet)

T+95s: ch 2 video ready (from previous run)
├─ UPLOAD: ch 2 upload starts
├─ Other workers continue...

...continues until all chapters processed
```

---

## Summary: What Changes

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Processing** | Batch all → all → all | Sequential chapter pipeline |
| **State** | File existence based | DB-driven with explicit status |
| **Sync** | Hard to track | Easy to query at any time |
| **Restart** | Unclear what's done | Deterministic from DB |
| **Disk Usage** | All audio+video on disk | Streaming cleanup based on stage |
| **Errors** | Manual fix | Automatic retry with backoff |
| **Parallelization** | Hard | Natural (workers work independently) |

This design allows you to run the program, see exact progress across all stages, stop & restart anytime, and have efficient disk usage through automatic cleanup at each pipeline stage.