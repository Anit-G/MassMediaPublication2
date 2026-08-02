CREATE TABLE IF NOT EXISTS PROCESSING_STATE (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ebook_no INTEGER NOT NULL,
    voice_code INTEGER NOT NULL,
    category TEXT NOT NULL,
    current_chapter_idx INTEGER DEFAULT 0,
    stage TEXT NOT NULL CHECK(stage IN ('IDLE', 'AUDIO_GEN', 'VIDEO_GEN', 'UPLOAD', 'COMPLETE')),
    last_updated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    error_log TEXT,
    created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ebook_no, voice_code, category),
    FOREIGN KEY(ebook_no) REFERENCES books(ebook_no)
);