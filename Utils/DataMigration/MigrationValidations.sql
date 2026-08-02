-- Combined Migration Validation Report
-- Standardized to 4 columns for a clean unified result set

-- Check 1: PROCESSING_STATE coverage
SELECT 
    'Migration Validation' as check_type, 
    'PROCESSING_STATE coverage' as check_name,
    'Source: ' || COUNT(DISTINCT el.ebook_no) || ' | Target: ' || COUNT(DISTINCT ps.ebook_no) as details,
    CASE 
        WHEN COUNT(DISTINCT el.ebook_no) = COUNT(DISTINCT ps.ebook_no) THEN 'PASS'
        ELSE 'FAIL - Missing entries'
    END as status
FROM ebook_list el
LEFT JOIN PROCESSING_STATE ps ON ps.ebook_no = el.ebook_no

UNION ALL

-- Check 2: CHAPTER_PROGRESS coverage
SELECT 
    'Migration Validation', 
    'CHAPTER_PROGRESS coverage',
    'Lib: ' || COUNT(*) || ' | CP: ' || (SELECT COUNT(*) FROM CHAPTER_PROGRESS),
    CASE 
        WHEN COUNT(*) = (SELECT COUNT(*) FROM CHAPTER_PROGRESS) THEN 'PASS'
        ELSE 'FAIL - Row count mismatch'
    END
FROM ebook_lib

UNION ALL

-- Check 3: Status mapping correctness (Aggregated Summary)
SELECT 
    'Migration Validation', 
    'Status mapping integrity',
    'Total Mappings: ' || COUNT(*),
    CASE 
        WHEN SUM(CASE 
            WHEN el.status = 'PARSED' AND ps.stage = 'PARSED' THEN 0
            WHEN el.status = 'AUDGEN_DONE' AND ps.stage = 'AUDIO_GEN' THEN 0
            WHEN el.status = 'VIDGEN_DONE' AND ps.stage = 'VIDEO_GEN' THEN 0
            WHEN el.status = 'FULL_VIDEO_UPLOADED' AND ps.stage = 'UPLOAD' THEN 0
            ELSE 1 END) = 0 THEN 'PASS'
        ELSE 'WARN - Found ' || SUM(CASE 
            WHEN el.status = 'PARSED' AND ps.stage = 'PARSED' THEN 0
            WHEN el.status = 'AUDGEN_DONE' AND ps.stage = 'AUDIO_GEN' THEN 0
            WHEN el.status = 'VIDGEN_DONE' AND ps.stage = 'VIDEO_GEN' THEN 0
            WHEN el.status = 'FULL_VIDEO_UPLOADED' AND ps.stage = 'UPLOAD' THEN 0
            ELSE 1 END) || ' unexpected mappings'
    END
FROM ebook_list el
LEFT JOIN PROCESSING_STATE ps ON ps.ebook_no = el.ebook_no

UNION ALL

-- Check 4: Audio file tracking consistency
SELECT 
    'Migration Validation', 
    'Audio file integrity',
    'Path count: ' || SUM(CASE WHEN el.rel_path IS NOT NULL THEN 1 ELSE 0 END) || ' | CP Complete: ' || SUM(CASE WHEN cp.audio_status = 'COMPLETED' THEN 1 ELSE 0 END),
    CASE 
        WHEN SUM(CASE WHEN el.rel_path IS NOT NULL THEN 1 ELSE 0 END) = SUM(CASE WHEN cp.audio_status = 'COMPLETED' THEN 1 ELSE 0 END) THEN 'PASS'
        ELSE 'FAIL - Audio status mismatch'
    END
FROM ebook_lib el
LEFT JOIN CHAPTER_PROGRESS cp ON cp.ebook_no = el.ebook_no 
    AND cp.voice_code = el.voice_code 
    AND cp.chapter_idx = el.section_no

UNION ALL

-- Check 6: Shorts population (Aggregated)
SELECT 
    'Migration Validation', 
    'Shorts coverage',
    'Exp: ' || SUM(ebook_lib.no_shorts) || ' | Created: ' || (SELECT COUNT(*) FROM SHORTS_PROGRESS),
    CASE 
        WHEN SUM(ebook_lib.no_shorts) = (SELECT COUNT(*) FROM SHORTS_PROGRESS) THEN 'PASS'
        ELSE 'FAIL - Shorts count mismatch'
    END
FROM ebook_lib
WHERE no_shorts > 0

UNION ALL

-- Check 7: Category consistency
SELECT 
    'Migration Validation', 
    'Category mapping',
    'List Cats: ' || COUNT(DISTINCT el.category) || ' | PS Cats: ' || COUNT(DISTINCT ps.category),
    CASE 
        WHEN COUNT(DISTINCT el.category) = COUNT(DISTINCT ps.category) THEN 'PASS'
        ELSE 'FAIL - Category mismatch'
    END
FROM ebook_list el
LEFT JOIN PROCESSING_STATE ps ON ps.ebook_no = el.ebook_no;