import sys
import os
import json
import sqlite3

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import Utils.Config_vars as config

def get_db_connection():
    db_path = getattr(config, 'METADB_PATH', './Data/testDB.db3')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, db_path

def init_tables_if_needed(conn):
    cursor = conn.cursor()
    # CHAPTER_PROGRESS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS CHAPTER_PROGRESS (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ebook_no INTEGER NOT NULL,
        voice_code INTEGER NOT NULL,
        chapter_idx INTEGER NOT NULL,
        category TEXT NOT NULL,
        audio_status TEXT DEFAULT 'NOT_STARTED' CHECK(audio_status IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'AUDIO_ARCHIVED', 'DELETED')),
        audio_path TEXT,
        audio_generated_timestamp DATETIME,
        video_status TEXT DEFAULT 'NOT_STARTED' CHECK(video_status IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'VIDEO_ARCHIVED', 'DELETED')),
        video_path TEXT,
        video_generated_timestamp DATETIME,
        waveform_path TEXT,
        upload_status TEXT DEFAULT 'NOT_STARTED' CHECK(upload_status IN ('NOT_STARTED', 'UPLOADING', 'COMPLETED', 'FAILED', 'PAUSED_QUOTA_EXCEEDED', 'MANUAL_REVIEW_NEEDED', 'DELETED')),
        upload_path TEXT,
        youtube_url TEXT,
        upload_generated_timestamp DATETIME,
        retry_count INTEGER DEFAULT 0,
        next_retry_timestamp DATETIME,
        error_message TEXT,
        error_type TEXT DEFAULT 'UNKNOWN' CHECK(error_type IN ('TRANSIENT', 'PERMANENT', 'API_QUOTA', 'UNKNOWN')),
        created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_status_change_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ebook_no, voice_code, chapter_idx, category)
    )
    """)
    # EBOOK_METADATA
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS EBOOK_METADATA (
        ebook_no INTEGER PRIMARY KEY,
        source TEXT,
        status TEXT,
        title TEXT,
        author TEXT,
        language TEXT,
        subject TEXT,
        content_url TEXT,
        summary TEXT,
        failure_count INTEGER DEFAULT 0,
        category TEXT,
        rating REAL,
        no_rating INTEGER
    )
    """)
    # PROCESSING_STATE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PROCESSING_STATE (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ebook_no INTEGER NOT NULL UNIQUE,
        category TEXT NOT NULL,
        current_chapter_idx INTEGER DEFAULT 0,
        stage TEXT NOT NULL CHECK(stage IN ('IDLE', 'PROCESSING', 'COMPLETE')),
        last_updated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        error_log TEXT,
        created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        rating INTEGER,
        max_chapter_idx INTEGER DEFAULT -1,
        UNIQUE(ebook_no, category)
    )
    """)
    # SHORTS_PROGRESS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS SHORTS_PROGRESS (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ebook_no INTEGER NOT NULL,
        voice_code INTEGER NOT NULL,
        chapter_idx INTEGER NOT NULL,
        short_idx INTEGER NOT NULL,
        category TEXT NOT NULL,
        audio_status TEXT DEFAULT 'NOT_STARTED' CHECK(audio_status IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'AUDIO_ARCHIVED', 'DELETED')),
        audio_path TEXT,
        audio_generated_timestamp DATETIME,
        video_status TEXT DEFAULT 'NOT_STARTED' CHECK(video_status IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'VIDEO_ARCHIVED', 'DELETED')),
        video_path TEXT,
        video_generated_timestamp DATETIME,
        waveform_path TEXT,
        upload_status TEXT DEFAULT 'NOT_STARTED' CHECK(upload_status IN ('NOT_STARTED', 'UPLOADING', 'COMPLETED', 'FAILED', 'PAUSED_QUOTA_EXCEEDED', 'MANUAL_REVIEW_NEEDED', 'DELETED')),
        upload_path TEXT,
        youtube_url TEXT,
        youtube_shorts_url TEXT,
        upload_generated_timestamp DATETIME,
        retry_count INTEGER DEFAULT 0,
        next_retry_timestamp DATETIME,
        error_message TEXT,
        error_type TEXT DEFAULT 'UNKNOWN' CHECK(error_type IN ('TRANSIENT', 'PERMANENT', 'API_QUOTA', 'UNKNOWN')),
        created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_status_change_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ebook_no, voice_code, chapter_idx, short_idx, category)
    )
    """)
    # KEY_VALUE_STORE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS KEY_VALUE_STORE (
        key TEXT NOT NULL PRIMARY KEY,
        value TEXT NOT NULL,
        cypher_key TEXT DEFAULT 'NONE'
    )
    """)
    # YOUTUBE_MAP
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS YOUTUBE_MAP (
        category_name TEXT NOT NULL,
        category TEXT NOT NULL,
        yt_hash TEXT NOT NULL,
        voice_idx TEXT NOT NULL UNIQUE
    )
    """)
    
    # Ensure initial YOUTUBE_MAP data
    cursor.execute("SELECT COUNT(*) FROM YOUTUBE_MAP")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO YOUTUBE_MAP (category_name, category, yt_hash, voice_idx)
            VALUES (?, ?, ?, ?)
        """, [
            ('Relaxing and Soothing', 'cat(RS)', 'UCXeqq2XcvF7jjEcv35dPl8A', '3,7'),
            ('Mystery and Suspense', 'cat(MS)', 'UCfOw-0ovjVZSE8HvaCNJJ_Q', '18,26'),
            ('Whimsical escapism', 'cat(WE)', 'UCKpi4fdhxKbO_DWUD3FODTA', '20,23'),
            ('Litrary Masterpieces', 'cat(LM)', 'UChDu5fX4ICAQSgdT653TGzA', '17,22'),
            ('Thrilling and Adventurous', 'cat(TA)', 'UCGKLnKX4AF6r1Fz86BvUPEw', '15,19')
        ])

    conn.commit()

def cmd_status():
    conn, db_path = get_db_connection()
    init_tables_if_needed(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM EBOOK_METADATA")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT status, COUNT(*) FROM EBOOK_METADATA GROUP BY status")
    book_status = dict(cursor.fetchall())

    cursor.execute("SELECT COUNT(*) FROM CHAPTER_PROGRESS")
    total_chapters = cursor.fetchone()[0]

    cursor.execute("SELECT audio_status, COUNT(*) FROM CHAPTER_PROGRESS GROUP BY audio_status")
    chapter_audio_status = dict(cursor.fetchall())

    cursor.execute("SELECT video_status, COUNT(*) FROM CHAPTER_PROGRESS GROUP BY video_status")
    chapter_video_status = dict(cursor.fetchall())

    cursor.execute("SELECT upload_status, COUNT(*) FROM CHAPTER_PROGRESS GROUP BY upload_status")
    chapter_upload_status = dict(cursor.fetchall())

    cursor.execute("SELECT COUNT(*) FROM SHORTS_PROGRESS")
    total_shorts = cursor.fetchone()[0]

    cursor.execute("SELECT audio_status, COUNT(*) FROM SHORTS_PROGRESS GROUP BY audio_status")
    shorts_audio_status = dict(cursor.fetchall())

    cursor.execute("SELECT video_status, COUNT(*) FROM SHORTS_PROGRESS GROUP BY video_status")
    shorts_video_status = dict(cursor.fetchall())

    cursor.execute("SELECT upload_status, COUNT(*) FROM SHORTS_PROGRESS GROUP BY upload_status")
    shorts_upload_status = dict(cursor.fetchall())

    cursor.execute("SELECT COALESCE(SUM(retry_count), 0) FROM CHAPTER_PROGRESS")
    chap_retries = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(retry_count), 0) FROM SHORTS_PROGRESS")
    short_retries = cursor.fetchone()[0]
    total_retries = chap_retries + short_retries

    cursor.execute("SELECT * FROM YOUTUBE_MAP")
    youtube_channels = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM PROCESSING_STATE")
    processing_state = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "db_path": db_path,
        "total_books": total_books,
        "book_status": book_status,
        "total_chapters": total_chapters,
        "chapter_audio_status": chapter_audio_status,
        "chapter_video_status": chapter_video_status,
        "chapter_upload_status": chapter_upload_status,
        "total_shorts": total_shorts,
        "shorts_audio_status": shorts_audio_status,
        "shorts_video_status": shorts_video_status,
        "shorts_upload_status": shorts_upload_status,
        "total_retries": total_retries,
        "youtube_channels": youtube_channels,
        "processing_state": processing_state,
        "python_version": sys.version.split()[0],
    }

def cmd_tables():
    conn, _ = get_db_connection()
    init_tables_if_needed(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    result = []
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        cnt = cursor.fetchone()[0]
        result.append({"name": t, "count": cnt})
    conn.close()
    return result

def cmd_query_table(table_name, limit=50):
    conn, _ = get_db_connection()
    init_tables_if_needed(conn)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM [{table_name}] LIMIT ?", (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return {"columns": columns, "rows": rows}
    except Exception as e:
        conn.close()
        return {"error": str(e)}

def cmd_seed_sample():
    try:
        from Utils.DB_Operations import createDB
        _, db_path = get_db_connection()
        testdb = createDB(db_path)
        testdb.createTestDB()
        return {"message": "Database successfully seeded with official schema tables and YouTube channels"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "No command specified"}))
        sys.exit(1)

    cmd = args[0]
    if cmd == 'status':
        print(json.dumps(cmd_status()))
    elif cmd == 'tables':
        print(json.dumps(cmd_tables()))
    elif cmd == 'table' and len(args) > 1:
        limit = int(args[2]) if len(args) > 2 else 50
        print(json.dumps(cmd_query_table(args[1], limit)))
    elif cmd == 'seed':
        print(json.dumps(cmd_seed_sample()))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
