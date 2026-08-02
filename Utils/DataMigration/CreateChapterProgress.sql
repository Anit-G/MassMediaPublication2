CREATE TABLE IF NOT EXISTS CHAPTER_PROGRESS (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ebook_no INTEGER NOT NULL,
    voice_code INTEGER NOT NULL,
    chapter_idx INTEGER NOT NULL,
    category TEXT NOT NULL,
    
    -- Audio Generation Stage
    audio_status TEXT DEFAULT 'NOT_STARTED' CHECK(audio_status IN (
        'NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'AUDIO_ARCHIVED', 'DELETED'
    )),
    audio_path TEXT,
    audio_generated_timestamp DATETIME,
    
    -- Video Generation Stage
    video_status TEXT DEFAULT 'NOT_STARTED' CHECK(video_status IN (
        'NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'VIDEO_ARCHIVED', 'DELETED'
    )),
    video_path TEXT,
    video_generated_timestamp DATETIME,
    waveform_path TEXT,
    
    -- Upload Stage
    upload_status TEXT DEFAULT 'NOT_STARTED' CHECK(upload_status IN (
        'NOT_STARTED', 'UPLOADING', 'COMPLETED', 'FAILED', 'PAUSED_QUOTA_EXCEEDED', 'MANUAL_REVIEW_NEEDED', 'DELETED'
    )),
    youtube_url TEXT,
    upload_generated_timestamp DATETIME,
    
    -- Retry and Error Tracking
    retry_count INTEGER DEFAULT 0,
    next_retry_timestamp DATETIME,
    error_message TEXT,
    error_type TEXT CHECK(error_type IN ('TRANSIENT', 'PERMANENT', 'API_QUOTA', 'UNKNOWN')) DEFAULT 'UNKNOWN',
    
    -- Metadata
    created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_status_change_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(ebook_no, voice_code, chapter_idx, category),
    FOREIGN KEY(ebook_no) REFERENCES books(ebook_no)
);