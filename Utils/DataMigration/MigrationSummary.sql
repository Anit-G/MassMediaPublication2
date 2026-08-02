SELECT 
    'Migration Summary' as report_type,
    'PROCESSING_STATE' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT ebook_no) as unique_ebooks,
    COUNT(DISTINCT stage) as unique_stages
FROM PROCESSING_STATE
UNION ALL
SELECT 
    'Migration Summary',
    'CHAPTER_PROGRESS',
    COUNT(*),
    COUNT(DISTINCT ebook_no),
    COUNT(DISTINCT audio_status)
FROM CHAPTER_PROGRESS
UNION ALL
SELECT 
    'Migration Summary',
    'SHORTS_PROGRESS',
    COUNT(*),
    COUNT(DISTINCT ebook_no),
    COUNT(DISTINCT short_idx)
FROM SHORTS_PROGRESS;
