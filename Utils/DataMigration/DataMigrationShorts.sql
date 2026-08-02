DELETE FROM SHORTS_PROGRESS;
DELETE FROM sqlite_sequence WHERE name = 'SHORTS_PROGRESS';

INSERT INTO SHORTS_PROGRESS (
    ebook_no, 
    voice_code, 
    chapter_idx, 
    short_idx, 
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
    youtube_shorts_url,
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
    -- Generate short indices (1 to no_shorts)
    seq.short_idx,
    -- Get category from ebook_list
    (SELECT category FROM ebook_list WHERE ebook_no = el.ebook_no LIMIT 1) as category,
    
    -- For shorts, inherit audio status from chapter if it was generated
    CASE 
        WHEN el.no_words > 0 THEN 'COMPLETED'
        ELSE 'NOT_STARTED'
    END as audio_status,
    
    -- ADJUSTED AUDIO PATH
    -- 1. Take rel_path and remove '_chapsection.wav'
    -- 2. Append '_Shorts/short_'
    -- 3. Use (seq.short_idx - 1) to start at 00
    CASE 
        WHEN el.no_words > 0 AND el.rel_path IS NOT NULL
        THEN REPLACE(el.rel_path, '_chapsection.wav', '') || '_Shorts/short_' || PRINTF('%02d', seq.short_idx - 1) || '.wav'
        ELSE NULL 
    END as audio_path,
    
    -- Audio generated timestamp
    CASE 
        WHEN el.rel_path IS NOT NULL AND LENGTH(TRIM(el.rel_path)) > 0
        THEN CURRENT_TIMESTAMP 
        ELSE NULL 
    END as audio_generated_timestamp,
    
    -- Video status: If chapter video was generated, shorts inherit that state
    CASE 
        WHEN el.vid_status = 'GENERATED' THEN 'COMPLETED'
        ELSE 'NOT_STARTED'
    END as video_status,
    
    -- Video path: Not in old schema
    NULL as video_path,
    
    -- Waveform path: Not in old schema
    NULL as waveform_path,
    
    -- Video timestamp
    CASE WHEN el.vid_status = 'GENERATED' THEN CURRENT_TIMESTAMP ELSE NULL END as video_generated_timestamp,
    
    -- Upload status for shorts: Not tracked in old schema
    'NOT_STARTED' as upload_status,
    
    -- YouTube URLs: Not in old schema
    NULL as youtube_url,
    NULL as youtube_shorts_url,
    NULL as upload_generated_timestamp,
    
    0 as retry_count,
    NULL as next_retry_timestamp,
    NULL as error_message,
    NULL as error_type,
    
    CURRENT_TIMESTAMP as created_timestamp,
    CURRENT_TIMESTAMP as last_status_change_timestamp
    
FROM ebook_lib el
CROSS JOIN (
    -- Generate sequence of short indices (1 to 100 to cover most cases)
    WITH RECURSIVE seq_gen(short_idx) AS (
        SELECT 1
        UNION ALL
        SELECT short_idx + 1 FROM seq_gen WHERE short_idx < 100
    )
    SELECT short_idx FROM seq_gen
) seq

WHERE el.no_shorts > 0 
AND seq.short_idx <= el.no_shorts
AND NOT EXISTS (
    -- Avoid duplicates
    SELECT 1 FROM SHORTS_PROGRESS sp 
    WHERE sp.ebook_no = el.ebook_no 
    AND sp.voice_code = el.voice_code 
    AND sp.chapter_idx = el.section_no 
    AND sp.short_idx = seq.short_idx
);