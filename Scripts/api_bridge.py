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
        conn, db_path = get_db_connection()
        init_tables_if_needed(conn)
        cursor = conn.cursor()

        # Seed sample EBOOK_METADATA
        cursor.execute("DELETE FROM EBOOK_METADATA")
        cursor.executemany("""
            INSERT OR REPLACE INTO EBOOK_METADATA (ebook_no, source, status, title, author, language, subject, content_url, summary, failure_count, category, rating, no_rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (1, 'https://www.gutenberg.org/ebooks/1', 'PARSED', 'Alice in Wonderland', 'Lewis Carroll', 'English', 'Fantasy', 'https://www.gutenberg.org/cache/epub/1/pg1-images.html', 'A tale of wonder.', 0, 'cat(WE)', 4.8, 150),
            (2, 'https://www.gutenberg.org/ebooks/2', 'PARSED', 'The Adventures of Sherlock Holmes', 'Arthur Conan Doyle', 'English', 'Mystery', 'https://www.gutenberg.org/cache/epub/2/pg2-images.html', 'Famous detective stories.', 0, 'cat(MS)', 4.9, 210),
            (3, 'https://www.gutenberg.org/ebooks/3', 'PARSED', 'The Lullaby & Sleep Collection', 'Various Authors', 'English', 'Relaxation', 'https://www.gutenberg.org/cache/epub/3/pg3-images.html', 'Calming sleep tales.', 0, 'cat(RS)', 4.7, 95),
            (4, 'https://www.gutenberg.org/ebooks/4', 'PARSED', 'Pride and Prejudice', 'Jane Austen', 'English', 'Classic Literature', 'https://www.gutenberg.org/cache/epub/4/pg4-images.html', 'Classic romance and social satire.', 0, 'cat(LM)', 4.9, 300),
            (5, 'https://www.gutenberg.org/ebooks/5', 'PARSED', 'Treasure Island', 'Robert Louis Stevenson', 'English', 'Adventure', 'https://www.gutenberg.org/cache/epub/5/pg5-images.html', 'Pirates and treasure hunt.', 0, 'cat(TA)', 4.8, 180)
        ])

        # Seed sample PROCESSING_STATE
        cursor.execute("DELETE FROM PROCESSING_STATE")
        cursor.executemany("""
            INSERT OR REPLACE INTO PROCESSING_STATE (id, ebook_no, category, current_chapter_idx, stage, rating, max_chapter_idx)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (1, 1, 'cat(WE)', 1, 'PROCESSING', 4.8, 3),
            (2, 2, 'cat(MS)', 0, 'PROCESSING', 4.9, 3),
            (3, 3, 'cat(RS)', 2, 'PROCESSING', 4.7, 3),
            (4, 4, 'cat(LM)', 1, 'PROCESSING', 4.9, 3),
            (5, 5, 'cat(TA)', 0, 'IDLE', 4.8, 3)
        ])

        # Seed sample CHAPTER_PROGRESS
        cursor.execute("DELETE FROM CHAPTER_PROGRESS")
        cursor.executemany("""
            INSERT OR REPLACE INTO CHAPTER_PROGRESS (ebook_no, voice_code, chapter_idx, category, audio_status, video_status, upload_status, youtube_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            # WE (MoonBerry Echoes - Voice 20)
            (1, 20, 0, 'cat(WE)', 'COMPLETED', 'COMPLETED', 'NOT_STARTED', None),
            (1, 20, 1, 'cat(WE)', 'GENERATING', 'NOT_STARTED', 'NOT_STARTED', None),
            (1, 20, 2, 'cat(WE)', 'NOT_STARTED', 'NOT_STARTED', 'NOT_STARTED', None),

            # MS (Erebus Echoes - Voice 18)
            (2, 18, 0, 'cat(MS)', 'COMPLETED', 'GENERATING', 'NOT_STARTED', None),
            (2, 18, 1, 'cat(MS)', 'NOT_STARTED', 'NOT_STARTED', 'NOT_STARTED', None),

            # RS (Echo's Slumber - Voice 3)
            (3, 3, 0, 'cat(RS)', 'COMPLETED', 'COMPLETED', 'COMPLETED', 'https://youtube.com/watch?v=sample123'),
            (3, 3, 1, 'cat(RS)', 'COMPLETED', 'COMPLETED', 'UPLOADING', None),

            # LM (Marrow & Manuscripts - Voice 17)
            (4, 17, 0, 'cat(LM)', 'COMPLETED', 'NOT_STARTED', 'NOT_STARTED', None),

            # TA (Orpheus Odes - Voice 15)
            (5, 15, 0, 'cat(TA)', 'NOT_STARTED', 'NOT_STARTED', 'NOT_STARTED', None)
        ])

        conn.commit()
        conn.close()
        return {"message": "Database successfully seeded with official schema tables and pipeline chapter progress"}
    except Exception as e:
        return {"error": str(e)}

def cmd_channel_status():
    conn, _ = get_db_connection()
    init_tables_if_needed(conn)
    cursor = conn.cursor()

    static_channels = [
        {
            'code': 'RS',
            'name': "Echo's Slumber",
            'tag': '@EchoSlumber',
            'category': 'Relaxing and Soothing',
            'category_code': 'cat(RS)',
            'voiceCodes': [3, 7],
            'channelId': 'UCXeqq2XcvF7jjEcv35dPl8A',
            'watermark': '/Data/Channel Specs/erbuesechoes channel watermark.png'
        },
        {
            'code': 'MS',
            'name': 'Erebus Echoes',
            'tag': '@ErebosEchoes',
            'category': 'Mystery and Suspense',
            'category_code': 'cat(MS)',
            'voiceCodes': [18, 26],
            'channelId': 'UCfOw-0ovjVZSE8HvaCNJJ_Q',
            'watermark': '/Data/Channel Specs/marrormanuscripts channel watermark.png'
        },
        {
            'code': 'WE',
            'name': 'MoonBerry Echoes',
            'tag': '@MoonBerryEchoes',
            'category': 'Whimsical Escapism',
            'category_code': 'cat(WE)',
            'voiceCodes': [20, 23],
            'channelId': 'UCKpi4fdhxKbO_DWUD3FODTA',
            'watermark': '/Data/Channel Specs/moonberryechoes channel watermark.png'
        },
        {
            'code': 'LM',
            'name': 'Marrow & Manuscripts',
            'tag': '@MarrowManuscripts',
            'category': 'Literary Masterpieces',
            'category_code': 'cat(LM)',
            'voiceCodes': [17, 22],
            'channelId': 'UChDu5fX4ICAQSgdT653TGzA',
            'watermark': '/Data/Channel Specs/orpheusodes channel watermark.png'
        },
        {
            'code': 'TA',
            'name': 'Orpheus Odes',
            'tag': '@OrpheusOdes',
            'category': 'Thrilling and Adventurous',
            'category_code': 'cat(TA)',
            'voiceCodes': [15, 19],
            'channelId': 'UCGKLnKX4AF6r1Fz86BvUPEw',
            'banner': '/Data/Channel Specs/erebusechoes channel banner.jpg'
        }
    ]

    try:
        cursor.execute("""
            SELECT cp.*, em.title as book_title
            FROM CHAPTER_PROGRESS cp
            LEFT JOIN EBOOK_METADATA em ON cp.ebook_no = em.ebook_no
        """)
        all_chapters = [dict(r) for r in cursor.fetchall()]
    except Exception:
        all_chapters = []

    result_channels = []

    for ch in static_channels:
        v_codes = set(ch['voiceCodes'])
        cat_code = ch['category_code']
        cat_name = ch['category']
        ch_code = ch['code']

        ch_rows = []
        for r in all_chapters:
            r_cat = str(r.get('category') or '')
            r_vc = r.get('voice_code')
            if r_cat in (cat_code, cat_name, ch_code) or (r_vc is not None and int(r_vc) in v_codes):
                ch_rows.append(r)

        audio_counts = {'pending': 0, 'in_progress': 0, 'completed': 0, 'failed': 0}
        video_counts = {'pending': 0, 'in_progress': 0, 'completed': 0, 'failed': 0}
        upload_counts = {'pending': 0, 'in_progress': 0, 'completed': 0, 'failed': 0}

        pending_items = []

        for r in ch_rows:
            a_stat = r.get('audio_status') or 'NOT_STARTED'
            v_stat = r.get('video_status') or 'NOT_STARTED'
            u_stat = r.get('upload_status') or 'NOT_STARTED'

            if a_stat == 'COMPLETED':
                audio_counts['completed'] += 1
            elif a_stat in ('GENERATING', 'PROCESSING'):
                audio_counts['in_progress'] += 1
            elif a_stat == 'FAILED':
                audio_counts['failed'] += 1
            else:
                audio_counts['pending'] += 1

            if v_stat == 'COMPLETED':
                video_counts['completed'] += 1
            elif v_stat in ('GENERATING', 'PROCESSING'):
                video_counts['in_progress'] += 1
            elif v_stat == 'FAILED':
                video_counts['failed'] += 1
            else:
                video_counts['pending'] += 1

            if u_stat == 'COMPLETED':
                upload_counts['completed'] += 1
            elif u_stat in ('UPLOADING', 'PROCESSING', 'GENERATING'):
                upload_counts['in_progress'] += 1
            elif u_stat in ('FAILED', 'MANUAL_REVIEW_NEEDED', 'PAUSED_QUOTA_EXCEEDED'):
                upload_counts['failed'] += 1
            else:
                upload_counts['pending'] += 1

            if u_stat != 'COMPLETED':
                if a_stat != 'COMPLETED':
                    current_stage = 'audio'
                    stage_status = a_stat
                elif v_stat != 'COMPLETED':
                    current_stage = 'video'
                    stage_status = v_stat
                else:
                    current_stage = 'upload'
                    stage_status = u_stat

                pending_items.append({
                    'ebook_no': r.get('ebook_no'),
                    'title': r.get('book_title') or f"Ebook #{r.get('ebook_no')}",
                    'chapter_idx': r.get('chapter_idx'),
                    'voice_code': r.get('voice_code'),
                    'current_stage': current_stage,
                    'stage_status': stage_status,
                    'audio_status': a_stat,
                    'video_status': v_stat,
                    'upload_status': u_stat,
                    'retry_count': r.get('retry_count') or 0,
                    'next_retry_timestamp': r.get('next_retry_timestamp'),
                    'error_message': r.get('error_message')
                })

        stuck_items = [
            item for item in pending_items
            if item['stage_status'] in ('MANUAL_REVIEW_NEEDED', 'FAILED', 'PAUSED_QUOTA_EXCEEDED')
            or (item['retry_count'] and item['retry_count'] > 0)
        ]

        ch_data = dict(ch)
        ch_data['total_chapters'] = len(ch_rows)
        ch_data['audio_stage'] = audio_counts
        ch_data['video_stage'] = video_counts
        ch_data['upload_stage'] = upload_counts
        ch_data['pending_items'] = pending_items
        ch_data['stuck_count'] = len(stuck_items)
        ch_data['stuck_items'] = stuck_items

        result_channels.append(ch_data)

    conn.close()
    return {"channels": result_channels}

def cmd_reset_chapter(ebook_no, voice_code, chapter_idx, stage=None):
    from Utils.DB_Operations import createDB
    dbops = createDB()
    success = dbops.reset_chapter_status(int(ebook_no), int(voice_code), int(chapter_idx), stage)
    return {"success": success, "message": f"Reset chapter {chapter_idx} voice {voice_code} for ebook {ebook_no}"}

def cmd_reset_book(ebook_no):
    from Utils.DB_Operations import createDB
    dbops = createDB()
    success = dbops.reset_book_processing(int(ebook_no))
    return {"success": success, "message": f"Reset processing state for ebook {ebook_no}"}

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "No command specified"}))
        sys.exit(1)

    cmd = args[0]
    if cmd == 'status':
        print(json.dumps(cmd_status()))
    elif cmd == 'channel_status':
        print(json.dumps(cmd_channel_status()))
    elif cmd == 'tables':
        print(json.dumps(cmd_tables()))
    elif cmd == 'table' and len(args) > 1:
        limit = int(args[2]) if len(args) > 2 else 50
        print(json.dumps(cmd_query_table(args[1], limit)))
    elif cmd == 'seed':
        print(json.dumps(cmd_seed_sample()))
    elif cmd == 'reset_chapter' and len(args) >= 4:
        stage = args[4] if len(args) > 4 else None
        print(json.dumps(cmd_reset_chapter(args[1], args[2], args[3], stage)))
    elif cmd == 'reset_book' and len(args) >= 2:
        print(json.dumps(cmd_reset_book(args[1])))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
