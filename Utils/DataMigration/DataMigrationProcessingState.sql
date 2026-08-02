DELETE FROM PROCESSING_STATE;
DELETE FROM sqlite_sequence WHERE name = 'PROCESSING_STATE';

INSERT INTO PROCESSING_STATE (
    ebook_no, 
    voice_code, 
    category, 
    current_chapter_idx, 
    stage, 
    last_updated_timestamp, 
    error_log,
    created_timestamp,
    rating
)
SELECT 
    el.ebook_no,
    -- Get representative voice_code from ebook_lib (use max as there may be multiple)
    COALESCE((SELECT MAX(voice_code) FROM ebook_lib WHERE ebook_no = el.ebook_no), 0),
    el.category,
    -- Infer current_chapter_idx from highest section_no with any progress
    COALESCE((SELECT MAX(section_no) FROM ebook_lib WHERE ebook_no = el.ebook_no), 0),
    -- Map old status to new stage enum
    CASE el.status
        WHEN 'PARSED' THEN 'PARSED'
        WHEN 'AUDGEN_DONE' THEN 'AUDIO_GEN'
        WHEN 'VIDGEN_DONE' THEN 'VIDEO_GEN'
        WHEN 'FULL_VIDEO_UPLOADED' THEN 'UPLOAD'
        WHEN 'COMPLETE' THEN 'COMPLETE'
        ELSE 'IDLE'
    END as stage,
    CURRENT_TIMESTAMP,
    NULL as error_log,
    CURRENT_TIMESTAMP,
    el.no_rating as rating
FROM ebook_list el
WHERE NOT EXISTS (
    -- Avoid duplicates if table already has data
    SELECT 1 FROM PROCESSING_STATE ps 
    WHERE ps.ebook_no = el.ebook_no 
    AND ps.category = el.category
);