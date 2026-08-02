DELETE FROM CHAPTER_PROGRESS;
DELETE FROM sqlite_sequence WHERE name = 'CHAPTER_PROGRESS';

INSERT INTO CHAPTER_PROGRESS (
    ebook_no, 
    voice_code, 
    chapter_idx, 
    category,
    audio_status, 
    audio_path, 
    audio_generated_timestamp,
    video_status, 
    video_path, 
    waveform_path, 
    video_generated_timestamp,
    upload_status, 
    youtube_url, 
    upload_generated_timestamp,
    retry_count, 
    next_retry_timestamp, 
    error_message, 
    error_type,
    created_timestamp, 
    last_status_change_timestamp
)
SELECT 
    el.ebook_no,
    el.voice_code,
    el.section_no as chapter_idx,
    -- Get category from ebook_list
    (SELECT category FROM ebook_list WHERE ebook_no = el.ebook_no LIMIT 1) as category,
    
    -- Audio Status: If rel_path exists, it was generated
    CASE 
        WHEN el.rel_path IS NOT NULL AND LENGTH(TRIM(el.rel_path)) > 0 THEN 'COMPLETED'
        ELSE 'NOT_STARTED'
    END as audio_status,
    
    -- Audio Path: Use rel_path from ebook_lib
    el.rel_path as audio_path,
    
    -- Audio Generated Timestamp: Not in old schema, use current time as approximation
    CASE WHEN el.rel_path IS NOT NULL THEN CURRENT_TIMESTAMP ELSE NULL END as audio_generated_timestamp,
    
    -- Video Status: Map from vid_status field
    'NOT_STARTED' as video_status,
    
    -- Video Path: Not stored in old schema, set NULL
    NULL as video_path,
    
    -- Waveform Path: Not in old schema, set NULL
    NULL as waveform_path,
    
    -- Video Generated Timestamp: Not in old schema
    CASE WHEN el.vid_status = 'GENERATED' THEN CURRENT_TIMESTAMP ELSE NULL END as video_generated_timestamp,
    
    -- Upload Status: Not explicitly tracked in old schema
    -- Infer from ebook_list status if FULL_VIDEO_UPLOADED
    CASE el.vid_status
        WHEN 'UPLOADED' THEN 'COMPLETED'
        ELSE 'NOT_STARTED'
    END as upload_status,
    
    -- YouTube URL: Not in old schema
    NULL as youtube_url,
    
    -- Upload Timestamp: Not in old schema
    NULL as upload_generated_timestamp,
    
    -- Retry tracking: Not in old schema, initialize to 0
    0 as retry_count,
    NULL as next_retry_timestamp,
    NULL as error_message,
    NULL as error_type,
    
    CURRENT_TIMESTAMP as created_timestamp,
    CURRENT_TIMESTAMP as last_status_change_timestamp
    
FROM ebook_lib el
WHERE NOT EXISTS (
    -- Avoid duplicates
    SELECT 1 FROM CHAPTER_PROGRESS cp 
    WHERE cp.ebook_no = el.ebook_no 
    AND cp.voice_code = el.voice_code 
    AND cp.chapter_idx = el.section_no
);

-- Log migration result
SELECT 
    'PHASE 2 Complete' as phase,
    COUNT(*) as chapter_progress_rows_inserted
FROM CHAPTER_PROGRESS;