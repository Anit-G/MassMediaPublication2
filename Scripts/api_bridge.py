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
    # Ensure ebook_list
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ebook_list (
        ebook_no INTEGER PRIMARY KEY,
        title TEXT,
        authors TEXT,
        language TEXT,
        subjects TEXT,
        category TEXT,
        no_rating INTEGER,
        status TEXT,
        voice_code INTEGER
    )
    """)
    # Ensure chapter_progress
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapter_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ebook_no INTEGER,
        voice_code INTEGER,
        chapter_idx INTEGER,
        audio_status TEXT DEFAULT 'NOT_STARTED',
        video_status TEXT DEFAULT 'NOT_STARTED',
        upload_status TEXT DEFAULT 'NOT_STARTED',
        audio_path TEXT,
        video_path TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Ensure shorts_progress
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shorts_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ebook_no INTEGER,
        voice_code INTEGER,
        chapter_idx INTEGER,
        short_idx INTEGER,
        audio_status TEXT DEFAULT 'NOT_STARTED',
        video_status TEXT DEFAULT 'NOT_STARTED',
        upload_status TEXT DEFAULT 'NOT_STARTED',
        audio_path TEXT,
        video_path TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Ensure processing_state
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processing_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ebook_no INTEGER,
        voice_code INTEGER,
        category TEXT,
        stage TEXT,
        status TEXT,
        last_action TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Ensure retries
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS retries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ebook_no INTEGER,
        stage TEXT,
        chapter_idx INTEGER,
        retry_count INTEGER DEFAULT 0,
        last_error TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

def cmd_status():
    conn, db_path = get_db_connection()
    init_tables_if_needed(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM ebook_list")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT status, COUNT(*) FROM ebook_list GROUP BY status")
    book_status = dict(cursor.fetchall())

    cursor.execute("SELECT COUNT(*) FROM chapter_progress")
    total_chapters = cursor.fetchone()[0]

    cursor.execute("SELECT audio_status, COUNT(*) FROM chapter_progress GROUP BY audio_status")
    chapter_audio_status = dict(cursor.fetchall())

    cursor.execute("SELECT video_status, COUNT(*) FROM chapter_progress GROUP BY video_status")
    chapter_video_status = dict(cursor.fetchall())

    cursor.execute("SELECT COUNT(*) FROM shorts_progress")
    total_shorts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM retries")
    total_retries = cursor.fetchone()[0]

    conn.close()

    return {
        "db_path": db_path,
        "total_books": total_books,
        "book_status": book_status,
        "total_chapters": total_chapters,
        "chapter_audio_status": chapter_audio_status,
        "chapter_video_status": chapter_video_status,
        "total_shorts": total_shorts,
        "total_retries": total_retries,
        "python_version": sys.version.split()[0],
    }

def cmd_tables():
    conn, _ = get_db_connection()
    init_tables_if_needed(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
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
    conn, _ = get_db_connection()
    init_tables_if_needed(conn)
    cursor = conn.cursor()
    
    # Check if books exist
    cursor.execute("SELECT COUNT(*) FROM ebook_list")
    if cursor.fetchone()[0] == 0:
        sample_books = [
            (1001, "Alice's Adventures in Wonderland", "Lewis Carroll", "en", "Fantasy, Children", "WE", 5, "PARSED", 20),
            (1002, "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "en", "Mystery, Detective", "MS", 5, "PARSED", 18),
            (1003, "The Art of War", "Sun Tzu", "en", "Strategy, Philosophy", "LM", 4, "AUDGEN_DONE", 17),
            (1004, "Meditations", "Marcus Aurelius", "en", "Philosophy, Calm", "RS", 5, "VIDGEN_DONE", 3),
            (1005, "The Odyssey", "Homer", "en", "Epic, Adventure", "TA", 4, "FULL_VIDEO_UPLOADED", 15)
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO ebook_list 
            (ebook_no, title, authors, language, subjects, category, no_rating, status, voice_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_books)

        sample_chapters = [
            (1001, 20, 1, 'COMPLETED', 'NOT_STARTED', 'NOT_STARTED', 'Data/AudFiles/Book_1001/01001_20_001_chapsection.wav', None),
            (1001, 20, 2, 'GENERATING', 'NOT_STARTED', 'NOT_STARTED', None, None),
            (1002, 18, 1, 'COMPLETED', 'COMPLETED', 'NOT_STARTED', 'Data/AudFiles/Book_1002/01002_18_001_chapsection.wav', 'Data/OutputVideos/Book_1002/01002_18_001_videosection.mp4'),
            (1003, 17, 1, 'COMPLETED', 'COMPLETED', 'COMPLETED', 'Data/AudFiles/Book_1003/01003_17_001_chapsection.wav', 'Data/OutputVideos/Book_1003/01003_17_001_videosection.mp4'),
        ]
        cursor.executemany("""
            INSERT INTO chapter_progress 
            (ebook_no, voice_code, chapter_idx, audio_status, video_status, upload_status, audio_path, video_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_chapters)

        conn.commit()
    conn.close()
    return {"message": "Sample data seeded successfully"}

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
