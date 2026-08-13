import Utils.Config_vars as config
import Utils.Central_Logger as log
import sqlite3
import json
import shutil
import threading
import os

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(): pass

from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List, Union

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

def signature(ebook_no: int, voice_code: int, ch_idx: int) -> str:
    return f"{str(ebook_no).zfill(5)}_{str(voice_code).zfill(2)}_{str(ch_idx).zfill(3)}"

def write_path(ebook_no: int, voice_code: int, chapter_idx: int, 
                    stage: str, **kwargs) -> str:
        shorts_idx = kwargs.get("shorts_idx")
        head_flag = kwargs.get("headsectionFlag")
        
        front_section = signature(ebook_no, voice_code, chapter_idx)
        prefix = Status.convertStages(stage)
        
        if prefix == 'audio':
            base_dir = Path(config.AUD_FILEPATH) / f"Book_{ebook_no}"
            ext = "wav"
        elif prefix in ('video','upload'):
            base_dir = Path(config.OUTPUT_FOLDER) / f"Book_{ebook_no}"
            ext = "mp4"
        else:
            log.ERROR(f"DB[{ebook_no}]: Unknown prefix for stage {stage}")
            return ""
        
        if shorts_idx is not None:
            folder = base_dir / f"{front_section}_Shorts"
            name = f"short_{shorts_idx:02d}" if prefix == 'audio' else f"{front_section}_videoshort_{shorts_idx:02d}"
            filename = f"{name}.{ext}"
        elif prefix == 'audio' and head_flag:
            folder = base_dir
            filename = f"{front_section}_headsection.wav"
        else:
            folder = base_dir
            suffix = "chapsection" if prefix == 'audio' else 'videosection'
            filename = f"{front_section}_{suffix}.{ext}"
        
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            
        return (folder / filename).as_posix()

def encrypt(data):
    load_dotenv()
    MY_KEY = os.environ.get("AES_KEY", "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
    iv = os.urandom(16)
    if not HAS_CRYPTO:
        key_bytes = bytes.fromhex(MY_KEY)
        xor_key = (key_bytes * ((len(data) // len(key_bytes)) + 1))[:len(data)]
        cipher_text = bytes([b ^ k for b, k in zip(data, xor_key)])
        return iv, cipher_text

    key_bytes = bytes.fromhex(MY_KEY)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    cipher_text = encryptor.update(padded_data) + encryptor.finalize()
    return iv, cipher_text

def decrypt(iv, ciphertext) -> bytes:
    load_dotenv()
    MY_KEY = os.environ.get("AES_KEY", "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
    if not HAS_CRYPTO:
        key_bytes = bytes.fromhex(MY_KEY)
        xor_key = (key_bytes * ((len(ciphertext) // len(key_bytes)) + 1))[:len(ciphertext)]
        return bytes([b ^ k for b, k in zip(ciphertext, xor_key)])

    key_bytes = bytes.fromhex(MY_KEY)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data
          
class Status:
    # Legacy status constants
    BOOK_PARSEABLE = "PARSEABLE"
    BOOK_PARSED = "PARSED"
    VIDGEN_DONE = "VIDGEN_DONE"
    VID_GENERATED = "GENERATED"
    
    @staticmethod
    def convertStages(stage: str):
        stage_map = {
                'AUDIO_GEN': 'audio',
                'VIDEO_GEN': 'video',
                'UPLOAD': 'upload'
            }
            
        prefix = stage_map.get(stage, '')
        return prefix
    
    @staticmethod
    def next_stage(curr_stage: str) -> str:
        match curr_stage:
            case Status.ProcessingStage.IDLE:
                return Status.ProcessingStage.PROCESSING
            case Status.ProcessingStage.PROCESSING:
                return Status.ProcessingStage.COMPLETE
            case _:
                return ""
    
    # State management constants
    class ProcessingStage:
        # Defines the current stage of processing for a book/voice/category combination
        # Example if we are generating audio and some chapters are completed, we set book to processing
        # While CHAPTER STATUS will be updated at chapter level for each stage of AUDIO, VIDEO and UPLOAD.
        # Once a book is carried through all stages for all chapters it is set to COMPLETE
        IDLE = "IDLE"
        PROCESSING = "PROCESSING"
        COMPLETE = "COMPLETE"
    
    class ChapterStatus:
        # The status of each chapter for audio/video/upload processing and for shorts
        NOT_STARTED = "NOT_STARTED" # initial status for all chapters and stage needs to determine next action
        GENERATING = "GENERATING" # when the process is running for this chapter
        UPLOADING = "UPLOADING"
        COMPLETED = "COMPLETED" # when the process is done successfully for this chapter
        FAILED = "FAILED" 
        MANUAL_REVIEW_NEEDED = "MANUAL_REVIEW_NEEDED"
    
    class PossibleStates:
        AUDIO_GEN = "AUDIO_GEN"
        VIDEO_GEN = "VIDEO_GEN"
        UPLOAD = "UPLOAD"
    
    class ErrorType:
        TRANSIENT = "TRANSIENT"
        PERMANENT = "PERMANENT"
        API_QUOTA = "API_QUOTA"
        UNKNOWN = "UNKNOWN"

class DBOps:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls,  *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(DBOps, cls).__new__(cls)
        return cls._instance 
    
    def __init__(self, path = config.METADB_PATH):
        if not hasattr(self, "_initialized"):
            # initialize the SQLite DB
            self._path = path
            self._connection = sqlite3.connect(self._path, check_same_thread=False)
            self._cursor = self._connection.cursor()
            self._ensure_kvs_table()
            self._initialized = True

    def _ensure_kvs_table(self):
        try:
            self._cursor.execute("SELECT 1 FROM KEY_VALUE_STORE LIMIT 1")
        except sqlite3.OperationalError:
            try:
                self.createKVS()
            except Exception as e:
                log.WARNING(f"Could not auto-create KEY_VALUE_STORE: {e}")
    
    # ============================================================================
    # LEGACY METHODS
    # ============================================================================
    
    def insert_new_book(self,ebook_no: int, category: str, no_rating: int) -> None:
        log.INFO(f"DB[{ebook_no}] Insert into ebook_list for TTS")
        self._cursor.execute("INSERT INTO ebook_list (ebook_no, status, category, no_rating) VALUES (?,?,?,?)", (ebook_no, "PARSED", category, no_rating))
        if self._cursor.rowcount == 0:
            log.ERROR(f"DB[{ebook_no}]: No rows were updated")    
            return
        self._connection.commit()
        
    # ============================================================================
    # KEY VALUE STORE METHODS
    # ============================================================================
    
    def get_value(self, key: str) -> list:
        log.INFO(f"DB: Get {key} from KVS")
        try:
            self._cursor.execute("SELECT value, cypher_key FROM KEY_VALUE_STORE WHERE key = ?", (key,))
        except sqlite3.OperationalError:
            self._ensure_kvs_table()
            try:
                self._cursor.execute("SELECT value, cypher_key FROM KEY_VALUE_STORE WHERE key = ?", (key,))
            except Exception:
                return []
        res = self._cursor.fetchone()
        return res if res else []
    
    def get_encrypted_data(self, key: str):
        log.INFO(f"DB: Get encrypted data")
        client_data = self.get_value(key) # Returns the value and cypher_key
        if client_data:
            # Decrypt the data
            decrypted_data = decrypt(bytes.fromhex(client_data[-1]), bytes.fromhex(client_data[0]))
            return decrypted_data
        return ""
    
    def get_client_secret(self):
        data = self.get_encrypted_data("client_secret")
        if data:
            try:
                return json.loads(data.decode('utf-8'))
            except Exception:
                return data.decode('utf-8')
        return ""
    
    def set_client_secret(self, secret_value) -> bool:
        log.INFO("DB: Set client_secret in KVS")
        try:
            if isinstance(secret_value, dict):
                secret_str = json.dumps(secret_value)
            else:
                secret_str = str(secret_value)
            iv, encrypted_data = encrypt(secret_str.encode('utf-8'))
            res = self.set_value("client_secret", encrypted_data.hex(), iv.hex())
            return res
        except Exception as e:
            log.ERROR(f"DB: Failed to set client_secret: {e}")
            return False

    def get_channel_token(self, channel_id: str):
        data = self.get_encrypted_data(f"token_{channel_id}")
        if data:
            try:
                return json.loads(data.decode('utf-8'))
            except Exception:
                return data.decode('utf-8')
        return ""
    
    def set_value(self, key: str, value: str, cypher_key: str = "") -> bool:
        log.INFO(f"DB: Set {key} in KVS")
        try:
            self._cursor.execute("UPDATE KEY_VALUE_STORE SET value = ?, cypher_key = ? WHERE key = ?", (value, cypher_key, key,))
            if self._cursor.rowcount == 0:
                self._cursor.execute("INSERT INTO KEY_VALUE_STORE VALUES (?,?,?)", (key, value, cypher_key,))
                if self._cursor.rowcount == 0:
                    log.ERROR(f"DB: FAILED to Set for key {key} in KVS")
                    return False
            self._connection.commit()
            return True
        except sqlite3.OperationalError:
            self._ensure_kvs_table()
            self._cursor.execute("UPDATE KEY_VALUE_STORE SET value = ?, cypher_key = ? WHERE key = ?", (value, cypher_key, key,))
            if self._cursor.rowcount == 0:
                self._cursor.execute("INSERT INTO KEY_VALUE_STORE VALUES (?,?,?)", (key, value, cypher_key,))
            self._connection.commit()
            return True
    
    def set_channel_token(self, channel_id: str, token_value) -> bool:
        log.INFO(f"DB: set token value for {channel_id} in KVS")
        try:
            if isinstance(token_value, dict):
                token_str = json.dumps(token_value)
            else:
                token_str = str(token_value)
            iv, encrypted_data = encrypt(token_str.encode('utf-8'))
            res = self.set_value(f"token_{channel_id}", encrypted_data.hex(), iv.hex())
            return res
        except Exception as e:
            log.ERROR(f"DB: Failed to set channel token: {e}")
            return False
    
    # ============================================================================
    # EBOOK METADATA METHODS
    # ============================================================================
    
    def get_parseable_books(self, category: str) -> list:
        log.INFO(f"DB: Get books with status PARSEABLE, category: {category}")
        query = """
        SELECT ebook_no, content_url, category, no_rating 
        FROM EBOOK_METADATA 
        WHERE status = ? AND failure_count < 5 AND category = ?
        ORDER BY no_rating DESC LIMIT 2"""
     
        self._cursor.execute(query, (Status.BOOK_PARSEABLE, category,))
        return self._cursor.fetchall()        
    
    def get_content_url(self, ebook_no: int) -> str:
        log.INFO(f"DB: Gettting book, {ebook_no}")
        self._cursor.execute("SELECT content_url FROM EBOOK_METADATA WHERE ebook_no = ?", (ebook_no,))
        res = self._cursor.fetchone()
        return res[0] if res else ""
        
    def get_book_source_urls(self) -> list:
        log.INFO("DB: Get the first hundered books up for EBOOK_METADATA scarping")
        self._cursor.execute("SELECT source FROM EBOOK_METADATA WHERE failure_count < 5 AND status IS NULL LIMIT ?", (config.BOOK_BATCH_SIZE,))
        return self._cursor.fetchall()
    
    def get_book_author(self, ebook_no: int) -> list:
        self._cursor.execute("SELECT title, author FROM EBOOK_METADATA WHERE ebook_no = ?", (ebook_no,))
        res = self._cursor.fetchone()
        return res if res else []

    def update_failure_count(self, ebook_no: int) -> None:
        log.INFO(f"DB[{ebook_no}]: Increment count by 1")
        self._cursor.execute("UPDATE EBOOK_METADATA SET failure_count = failure_count + 1 WHERE ebook_no = ?", (ebook_no,))
        if self._cursor.rowcount == 0:
            log.ERROR(f"DB[{ebook_no}]: Failed to update metadata for failure count")
            return
        self._connection.commit()
        
    def update_status_meta(self, ebook_no: int , status: str) -> None:
        log.INFO(f"DB[{ebook_no}]: updating status, book {ebook_no} to {status}")
        self._cursor.execute("UPDATE EBOOK_METADATA SET status = ? WHERE ebook_no = ?", (status, ebook_no))
        if self._cursor.rowcount == 0:
                log.ERROR(f"DB[{ebook_no}]: No rows were updated. Check your WHERE condition!")
                return
        self._connection.commit()
        
    def update_meta_state(self, book_data: dict) -> None:
        # get data from dict
        source = book_data['source']
        status = book_data['status']      
        title = book_data['book_title']  
        lang = book_data['language']
        sub = book_data['subject']
        summ = book_data['summary']
        content_url = book_data['content_url']
        ebook_no = int(book_data['ebook_no'])
        
        if not all(isinstance(arg, str) for arg in (title, source, status)):
            log.ERROR(f"DB[{ebook_no}]: Failed type check")
            return None
        log.INFO(f"DB[{ebook_no}]: write to DB: [{ebook_no, title, source, content_url, lang, sub, status}]")
        try: 
            self._cursor.execute("UPDATE EBOOK_METADATA SET title = ?, content_url = ?, language = ?, subject = ?, summary = ?, status = ? WHERE ebook_no = ?", (title, content_url, lang, sub, summ, status, ebook_no))
            # Check if any rows were updated
            if self._cursor.rowcount == 0:
                log.INFO(f"DB[{ebook_no}]: No rows were updated. Check your WHERE condition!")
                return
            self._connection.commit()
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: SQLite error: {e}")

    # ============================================================================
    # State Getter Methods
    # ============================================================================
    
    def get_voice_codes(self, category: str) -> List[int]:
        self._cursor.execute("SELECT voice_idx FROM YOUTUBE_MAP WHERE category = ?", (category,))
        row = self._cursor.fetchone()
        if not row or not row[0]:
            return []

        return [int(v.strip()) for v in row[0].split(",") if v.strip().isdigit()]
    
    def get_next_action_category(self, category: str, stage: str, pipeState: str) -> Optional[Tuple[int, int]]:
        """ 
        Query PROCESSING_STATE to get the next ebook and chapter index that needs TTS generation for a given category.
        
        stage: IDLE, PROCESSING, COMPLETE
        pipeState: AUDIO_GEN, VIDEO_GEN OR UPLOAD
        
        Note: PS table only holds chapter value for a stage if that chapter has already been processed for said stage.
        Returns: (ebook_no, chapter_idx) or None if no TTS action needed
        """
        state_map = {
                'AUDIO_GEN': 'audio',
                'VIDEO_GEN': 'video',
                'UPLOAD': 'upload'
            }
        prefix = state_map.get(pipeState, '')
        log.INFO(f"DB: Getting the next {prefix} action for category {category}")
        try:               
            # Get the ebook no from PROCESSING STATE with stage IDLE or PROCESSING prioritise PROCESSING
            self._cursor.execute("SELECT ebook_no, current_chapter_idx, category, max_chapter_idx FROM PROCESSING_STATE WHERE stage = ? AND category = ? ORDER BY rating ASC LIMIT 1", 
                                 (stage, category))
            ebook_res = self._cursor.fetchone()
            if not ebook_res:
                log.INFO(f"DB: No books found in PROCESSING_STATE for category {category} in PROCESSING moving to a new book")
                return self.get_next_action_category(category, Status.ProcessingStage.IDLE, pipeState)
                
            ebook_no, curr_chapter_idx, _, max_chapter_idx = ebook_res
            log.INFO(f"DB: Processing book {ebook_no}, with current chapter {curr_chapter_idx} out of {max_chapter_idx}")
            
            if curr_chapter_idx >= max_chapter_idx:
                # update PS table to next stage for ebook_no
                self.update_processing_state(ebook_no, category, Status.ProcessingStage.COMPLETE, max_chapter_idx)
                return self.get_next_action_category(category, Status.ProcessingStage.PROCESSING, pipeState)
            
            if stage == Status.ProcessingStage.IDLE:
                self.update_processing_state(ebook_no, category, Status.ProcessingStage.PROCESSING, 0) 
            
            # Get Voice IDs for the category from YOUTUBE_MAP
            self._cursor.execute("SELECT voice_idx FROM YOUTUBE_MAP WHERE category = ?", (category,))
            voice_res = self._cursor.fetchone()
            if not voice_res:
                log.ERROR(f"DB: No voice codes found for category {category} in YOUTUBE MAP")
                return None
            
            voice_codes = [v.strip() for v in voice_res[0].split(",") if v.strip().isdigit()]
            if not voice_codes:
                log.ERROR(f"DB: No valid voice codes found for category {category}")
                return None
            
            status_key = f"{prefix}_status"
            voices_needing_work = []
            all_voices_finished = True
            
            for vc_str in voice_codes:
                voice_code = int(vc_str)
                chapter_state = self.get_chapter_state(ebook_no, voice_code, curr_chapter_idx)
                curr_st = chapter_state.get(status_key) if chapter_state else Status.ChapterStatus.NOT_STARTED
                
                if curr_st in [Status.ChapterStatus.COMPLETED, Status.ChapterStatus.MANUAL_REVIEW_NEEDED]:
                    continue
                else:
                    all_voices_finished = False
                    voices_needing_work.append((voice_code, curr_st))
            
            if all_voices_finished:
                if pipeState == Status.PossibleStates.UPLOAD:
                    log.INFO(f"DB: Chapter {curr_chapter_idx} for ebook {ebook_no} is fully uploaded for all voices. Advancing chapter.")
                    next_ch = curr_chapter_idx + 1
                    if max_chapter_idx > 0 and next_ch >= max_chapter_idx:
                        self.update_processing_state(ebook_no, category, Status.ProcessingStage.COMPLETE, max_chapter_idx)
                    else:
                        self.update_processing_state(ebook_no, category, Status.ProcessingStage.PROCESSING, next_ch)
                    return self.get_next_action_category(category, Status.ProcessingStage.PROCESSING, pipeState)
                else:
                    log.INFO(f"DB: Chapter {curr_chapter_idx} for ebook {ebook_no} completed stage {pipeState} across all voices. Awaiting upload to advance.")
                    return None
            
            for voice_code, curr_st in voices_needing_work:
                log.INFO(f"DB: Chapter {curr_chapter_idx} for ebook {ebook_no} voice {voice_code} stage {pipeState}, status {curr_st} -> updating")
                if pipeState == Status.PossibleStates.UPLOAD:
                    self.update_chapter_status(ebook_no, voice_code, curr_chapter_idx, pipeState, Status.ChapterStatus.UPLOADING)
                else:
                    self.update_chapter_status(ebook_no, voice_code, curr_chapter_idx, pipeState, Status.ChapterStatus.GENERATING)
            
            return (ebook_no, curr_chapter_idx)
        except Exception as e:
            log.ERROR(f"DB: Error occurred while fetching next action for category {category}: {e}")
            return None
    
    def get_chapter_state(self, ebook_no: int, voice_code: int, chapter_idx: int) -> Optional[Dict]:
        """
        Query CHAPTER_PROGRESS and return all status fields as dictionary.
        
        Returns: dict with all chapter status fields or None if not found
        """
        log.INFO(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Getting chapter state for chapter {chapter_idx}, voice {voice_code}")
        try:
            self._cursor.execute("""
            SELECT id, audio_status, audio_path, audio_generated_timestamp,
                   video_status, video_path, video_generated_timestamp,
                   waveform_path, upload_status, youtube_url, upload_generated_timestamp,
                   retry_count, next_retry_timestamp, error_message, error_type,
                   created_timestamp, last_status_change_timestamp
            FROM CHAPTER_PROGRESS 
            WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?
            """, (ebook_no, voice_code, chapter_idx))
            
            row = self._cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'audio_status': row[1],
                'audio_path': row[2],
                'audio_generated_timestamp': row[3],
                'video_status': row[4],
                'video_path': row[5],
                'video_generated_timestamp': row[6],
                'waveform_path': row[7],
                'upload_status': row[8],
                'youtube_url': row[9],
                'upload_generated_timestamp': row[10],
                'retry_count': row[11],
                'next_retry_timestamp': row[12],
                'error_message': row[13],
                'error_type': row[14],
                'created_timestamp': row[15],
                'last_status_change_timestamp': row[16],
            }
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Failed to get chapter state: {e}")
            return None
    
    def get_shorts_state(self, ebook_no: int, voice_code: int, chapter_idx: int) -> Optional[Dict]:
        """
        Query SHORTS_PROGRESS and return all status fields as dictionary.
        
        Returns: dict with all shorts status fields or None if not found
        """
        log.INFO(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Getting shorts state for chapter {chapter_idx}, voice {voice_code}")
        try:
            self._cursor.execute("""
            SELECT id, short_idx, 
            audio_status, audio_path, audio_generated_timestamp,
            video_status, video_path, video_generated_timestamp,
            waveform_path, upload_status, youtube_url, upload_generated_timestamp,
            retry_count, next_retry_timestamp, error_message, error_type,
            created_timestamp, last_status_change_timestamp 
            FROM SHORTS_PROGRESS WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?;
            """, (ebook_no, voice_code, chapter_idx))
            
            rows = self._cursor.fetchall()
            if rows == []:
                return None

            shorts_dict = {}
            for row in rows:
                short_dict = {
                    'id': row[0],
                    'short_idx': row[1],
                    'audio_status': row[2],
                    'audio_path': row[3],
                    'audio_generated_timestamp': row[4],
                    'video_status': row[5],
                    'video_path': row[6],
                    'video_generated_timestamp': row[7],
                    'waveform_path': row[8],
                    'upload_status': row[9],
                    'youtube_url': row[10],
                    'upload_generated_timestamp': row[11],
                    'retry_count': row[12],
                    'next_retry_timestamp': row[13],
                    'error_message': row[14],
                    'error_type': row[15],
                    'created_timestamp': row[16],
                    'last_status_change_timestamp': row[17],
                }
                shorts_dict[row[1]] = short_dict
            return shorts_dict
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Failed to get chapter state: {e}")
            return None
    
    def get_all_sync_status(self, ebook_no: int, voice_code: int, category: str) -> Optional[Dict]:
        """
        Count chapters by status for each stage (audio, video, upload) for a given ebook, voice, and category.
        
        Returns: dict with progress counts for each stage
        """
        log.INFO(f"DB[{ebook_no}]: Getting sync status for voice {voice_code}, category {category}")
        try:
            self._cursor.execute("""
            SELECT 
                SUM(CASE WHEN audio_status = ? THEN 1 ELSE 0 END) as audio_completed,
                SUM(CASE WHEN audio_status = ? THEN 1 ELSE 0 END) as audio_generating,
                SUM(CASE WHEN audio_status = ? THEN 1 ELSE 0 END) as audio_failed,
                COUNT(*) as total_chapters
            FROM CHAPTER_PROGRESS 
            WHERE ebook_no = ? AND voice_code = ?
            """, (Status.ChapterStatus.COMPLETED, Status.ChapterStatus.GENERATING, 
                  Status.ChapterStatus.FAILED, ebook_no, voice_code))
            
            row = self._cursor.fetchone()
            audio_completed = row[0] or 0
            audio_generating = row[1] or 0
            audio_failed = row[2] or 0
            total = row[3] or 0
            
            # Video stats
            self._cursor.execute("""
            SELECT 
                SUM(CASE WHEN video_status = ? THEN 1 ELSE 0 END) as video_completed,
                SUM(CASE WHEN video_status = ? THEN 1 ELSE 0 END) as video_generating,
                SUM(CASE WHEN video_status = ? THEN 1 ELSE 0 END) as video_failed
            FROM CHAPTER_PROGRESS 
            WHERE ebook_no = ? AND voice_code = ?
            """, (Status.ChapterStatus.COMPLETED, Status.ChapterStatus.GENERATING,
                  Status.ChapterStatus.FAILED, ebook_no, voice_code))
            
            row = self._cursor.fetchone()
            video_completed = row[0] or 0
            video_generating = row[1] or 0
            video_failed = row[2] or 0
            
            # Upload stats
            self._cursor.execute("""
            SELECT 
                SUM(CASE WHEN upload_status = ? THEN 1 ELSE 0 END) as upload_completed,
                SUM(CASE WHEN upload_status = ? THEN 1 ELSE 0 END) as upload_generating,
                SUM(CASE WHEN upload_status = ? THEN 1 ELSE 0 END) as upload_failed
            FROM CHAPTER_PROGRESS 
            WHERE ebook_no = ? AND voice_code = ?
            """, (Status.ChapterStatus.COMPLETED, Status.ChapterStatus.GENERATING,
                  Status.ChapterStatus.FAILED, ebook_no, voice_code))
            
            row = self._cursor.fetchone()
            upload_completed = row[0] or 0
            upload_generating = row[1] or 0
            upload_failed = row[2] or 0
            
            return {
                'total_chapters': total,
                'audio': {
                    'completed': audio_completed,
                    'generating': audio_generating,
                    'failed': audio_failed,
                    'pending': total - audio_completed - audio_generating - audio_failed
                },
                'video': {
                    'completed': video_completed,
                    'generating': video_generating,
                    'failed': video_failed,
                    'pending': total - video_completed - video_generating - video_failed
                },
                'upload': {
                    'completed': upload_completed,
                    'generating': upload_generating,
                    'failed': upload_failed,
                    'pending': total - upload_completed - upload_generating - upload_failed
                }
            }
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to get sync status: {e}")
            return None
    
    def can_start_video_gen(self, ebook_no: int, voice_code: int, chapter_idx: int) -> str:
        """
        Check if video generation can start for this chapter.
        Validates: audio_status == COMPLETED, audio_path exists, waveform_path available.
        """
        log.INFO(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Checking if video gen can start for chapter {chapter_idx}, voice {voice_code}")
        try:
            chapter_state = self.get_chapter_state(ebook_no, voice_code, chapter_idx)
            if not chapter_state:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Chapter {chapter_idx} not found in state")
                return ""
            
            # Check audio is completed
            if chapter_state['audio_status'] != Status.ChapterStatus.COMPLETED:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Audio not completed for chapter {chapter_idx}")
                return ""
            
            # Check audio path exists and is readable
            if not chapter_state['audio_path']:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: No audio path for chapter {chapter_idx}")
                return ""
            
            if not os.path.exists(chapter_state['audio_path']):
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Audio file not found at {chapter_state['audio_path']}")
                return ""
            
            if not os.access(chapter_state['audio_path'], os.R_OK):
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Audio file not readable at {chapter_state['audio_path']}")
                return ""
            
            return chapter_state["audio_path"]
        except Exception as e:
            log.ERROR(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Error checking video gen readiness: {e}")
            return ""
        
    def can_start_shorts_video_gen(self, ebook_no: int, voice_code: int, chapter_idx: int) -> list[tuple[int, str]]:
        """
        Check if video generation can start for this chapter.
        Validates: audio_status == COMPLETED, audio_path exists, waveform_path available.
        """
        log.INFO(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Checking if video gen can start for chapter {chapter_idx}, voice {voice_code}")
        try:
            shorts_state = self.get_shorts_state(ebook_no, voice_code, chapter_idx)
            if not shorts_state:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Chapter {chapter_idx}'s shorts not found in state table")
                return []
            
            shorts_audio_paths = []
            for _, short_state in shorts_state.items():
                # Check audio is completed
                if short_state['audio_status'] != Status.ChapterStatus.COMPLETED:
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Audio not completed for chapter {chapter_idx}")
                    return []
                
                # Check audio path exists and is readable
                if not short_state['audio_path']:
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: No audio path for chapter {chapter_idx}")
                    return []
                
                if not os.path.exists(short_state['audio_path']):
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Audio file not found at {short_state['audio_path']}")
                    return []
                
                if not os.access(short_state['audio_path'], os.R_OK):
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Audio file not readable at {short_state['audio_path']}")
                    return []
                
                shorts_audio_paths.append((short_state['short_idx'], short_state['audio_path']))
            return shorts_audio_paths
        except Exception as e:
            log.ERROR(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Error checking video gen readiness: {e}")
            return []
    
    def can_start_upload(self, ebook_no: int, voice_code: int, chapter_idx: int) -> str:
        """
        Check if upload can start for this chapter.
        Validates: video_status == COMPLETED, video_path exists, upload_status not already COMPLETED.
        """
        log.INFO(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Checking if upload can start for chapter {chapter_idx}, voice {voice_code}")
        try:
            chapter_state = self.get_chapter_state(ebook_no, voice_code, chapter_idx)
            if not chapter_state:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Chapter {chapter_idx} not found in state")
                return ""
            
            # Check video is completed
            if chapter_state['video_status'] != Status.ChapterStatus.COMPLETED:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Video not completed for chapter {chapter_idx}")
                return ""
            
            # Check video path exists
            if not chapter_state['video_path']:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: No video path for chapter {chapter_idx}")
                return ""
            
            if not os.path.exists(chapter_state['video_path']):
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Video file not found at {chapter_state['video_path']}")
                return ""
            
            # Check upload not already completed (prevent duplicates)
            if chapter_state['upload_status'] == Status.ChapterStatus.COMPLETED:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Chapter {chapter_idx} already uploaded")
                return ""
            
            return chapter_state['video_path']
        except Exception as e:
            log.ERROR(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Error checking upload readiness: {e}")
            return ""
    
    def can_start_shorts_upload(self, ebook_no: int, voice_code: int, chapter_idx: int) -> list[tuple[int, str]]:
        """
        Check if upload can start for this chapter.
        Validates: video_status == COMPLETED, video_path exists, upload_status not already COMPLETED.
        """
        log.INFO(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Checking if upload can start for chapter {chapter_idx}, voice {voice_code}")
        try:
            shorts_state = self.get_shorts_state(ebook_no, voice_code, chapter_idx)
            if not shorts_state:
                log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Chapter {chapter_idx} not found in state")
                return []
            
            shorts_video_paths = []
            for _, short_state in shorts_state.items():
                # Check video is completed
                if short_state['video_status'] != Status.ChapterStatus.COMPLETED:
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Video not completed for chapter {chapter_idx}")
                    return []
                
                # Check video path exists
                if not short_state['video_path']:
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: No video path for chapter {chapter_idx}")
                    return []
                
                if not os.path.exists(short_state['video_path']):
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Video file not found at {short_state['video_path']}")
                    return []
                
                # Check upload not already completed (prevent duplicates)
                if short_state['upload_status'] == Status.ChapterStatus.COMPLETED:
                    log.WARNING(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Chapter {chapter_idx} already uploaded")
                    return []
                
                shorts_video_paths.append((short_state['short_idx'], short_state['video_path']))
            
            return shorts_video_paths
        except Exception as e:
            log.ERROR(f"DB[{ebook_no}:{voice_code}:{chapter_idx}]: Error checking upload readiness: {e}")
            return []
           
    # ============================================================================
    # State Setter Methods
    # ============================================================================
             
    def update_chapter_status(self, ebook_no: int, voice_code: int, chapter_idx: int, 
                             stage: str, status: str, **kwargs) -> bool:
        """
        Update chapter status for a specific stage with transaction support.
        Handles COMPLETED, FAILED, and GENERATING cases with appropriate updates.
        
        Args:
            ebook_no: Book ID
            voice_code: Voice code
            chapter_idx: Chapter index
            stage: Stage name (AUDIO_GEN, VIDEO_GEN, UPLOAD)
            status: New status (GENERATING, COMPLETED, FAILED)
            **kwargs: Optional fields like audio_path, error_message, error_type, etc.
        
        Returns: True if update successful, False otherwise
        """
        log.INFO(f"DB[{ebook_no}]: Updating chapter {chapter_idx} status to {status} for stage {stage}")
        try:
            # Map stage to column prefix
            prefix = Status.convertStages(stage)
            if not prefix:
                log.ERROR(f"DB[{ebook_no}]: Unknown stage {stage}")
                return False

             # get category
            self._cursor.execute("""SELECT category FROM YOUTUBE_MAP WHERE ',' || voice_idx || ',' LIKE '%,' || ? || ',%'""", (voice_code,))
            category = self._cursor.fetchone()
            category = category[0] if category else 'UNKNOWN'
            
            # Ensure chapter entry exists
            self._cursor.execute("""
            SELECT id FROM CHAPTER_PROGRESS 
            WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?
            """, (ebook_no, voice_code, chapter_idx))
            res = self._cursor.fetchone()
            if not res:                
                # Create new entry
                self._cursor.execute("""
                INSERT INTO CHAPTER_PROGRESS (ebook_no, voice_code, chapter_idx, category)
                VALUES (?, ?, ?, ?)
                """, (ebook_no, voice_code, chapter_idx, category))
                if self._cursor.rowcount == 0:
                    log.ERROR(f"DB[{ebook_no}]: Failed to insert new entry to CHAPTERs")
                self._connection.commit()
            
            # Build update query based on status
            if status == Status.ChapterStatus.GENERATING:
                query = f"""
                UPDATE CHAPTER_PROGRESS 
                SET {prefix}_status = ?, last_status_change_timestamp = CURRENT_TIMESTAMP
                WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?
                """
                self._cursor.execute(query, (status, ebook_no, voice_code, chapter_idx))
                if self._cursor.rowcount == 0:
                    log.ERROR(f"DB[{ebook_no}]: Failed to update status to Generating")
                self._connection.commit()
            elif status == Status.ChapterStatus.COMPLETED:
                timestamp = datetime.now().isoformat()
                path_col = f"{prefix}_path"
                path_val = write_path(ebook_no, voice_code, chapter_idx, stage)
                
                query = f"""
                UPDATE CHAPTER_PROGRESS 
                SET {prefix}_status = ?, {prefix}_generated_timestamp = ?, 
                    last_status_change_timestamp = CURRENT_TIMESTAMP
                """
                params = [status, timestamp]
                
                if path_val:
                    query += f", {path_col} = ?"
                    params.append(path_val)
                
                # Handle waveform path for video completion
                if stage == Status.PossibleStates.VIDEO_GEN and 'waveform_path' in kwargs:
                    query += ", waveform_path = ?"
                    params.append(kwargs['waveform_path'])
                
                # Handel youtube url
                if stage == Status.PossibleStates.UPLOAD and 'youtube_url' in kwargs:
                    query += ", youtube_url = ?"
                    params.append(kwargs['youtube_url'])
                
                query += " WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?"
                params.extend([str(ebook_no), str(voice_code), str(chapter_idx)])
                self._cursor.execute(query, params)
                     
            elif status == Status.ChapterStatus.FAILED:
                error_msg = kwargs.get('error_message', 'Unknown error')
                error_type = kwargs.get('error_type', Status.ErrorType.UNKNOWN)
                
                query = f"""
                UPDATE CHAPTER_PROGRESS 
                SET {prefix}_status = ?, error_message = ?, error_type = ?,
                    last_status_change_timestamp = CURRENT_TIMESTAMP
                WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?
                """
                self._cursor.execute(query, (status, error_msg, error_type, ebook_no, voice_code, chapter_idx))
            
            if self._cursor.rowcount == 0:
                log.WARNING(f"DB[{ebook_no}]: No rows updated for chapter {chapter_idx}")
                return False
            
            log.INFO(f"DB[{ebook_no}]: Successfully updated chapter {chapter_idx} to {status}")
            self._connection.commit()
            return True
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to update chapter status: {e}")
            return False
    
    def update_shorts_status(self, ebook_no: int, voice_code: int, chapter_idx: int,
                             short_idx: int, stage: str, status: str, **kwargs) -> bool:
        """
        Update shorts status for a specific stage in SHORTS_PROGRESS.
        Handles COMPLETED, FAILED, and GENERATING cases with optional path and upload URL updates.

        Args:
            ebook_no: Book ID
            voice_code: Voice code
            chapter_idx: Chapter index
            short_idx: Short index
            stage: Stage name (AUDIO_GEN, VIDEO_GEN, UPLOAD)
            status: New status (GENERATING, COMPLETED, FAILED)
            **kwargs: Optional fields like path, error_message, error_type, youtube_shorts_url

        Returns: True if update successful, False otherwise
        """
        log.INFO(f"DB[{ebook_no}]: Updating short {short_idx} for chapter {chapter_idx} status to {status} for stage {stage}")
        try:
            prefix = Status.convertStages(stage)
            if not prefix:
                log.ERROR(f"DB[{ebook_no}]: Unknown stage {stage}")
                return False

             # get category
            self._cursor.execute("""SELECT category FROM YOUTUBE_MAP WHERE ',' || voice_idx || ',' LIKE '%,' || ? || ',%'""", (voice_code,))
            category = self._cursor.fetchone()
            category = category[0] if category else 'UNKNOWN'

            self._cursor.execute(
                """
                SELECT id FROM SHORTS_PROGRESS
                WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ? AND short_idx = ?
                """,
                (ebook_no, voice_code, chapter_idx, short_idx)
            )
            res = self._cursor.fetchone()
            if not res:
                self._cursor.execute(
                    """
                    INSERT INTO SHORTS_PROGRESS (ebook_no, voice_code, chapter_idx, short_idx, category)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (ebook_no, voice_code, chapter_idx, short_idx, category)
                )
                if self._cursor.rowcount == 0:
                    log.ERROR(f"DB[{ebook_no}]: Failed to INSERT new entry to SHORTs")
                self._connection.commit()

            if status == Status.ChapterStatus.GENERATING:
                query = f"""
                UPDATE SHORTS_PROGRESS
                SET {prefix}_status = ?, last_status_change_timestamp = CURRENT_TIMESTAMP
                WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ? AND short_idx = ?
                """
                self._cursor.execute(query, (status, ebook_no, voice_code, chapter_idx, short_idx))

            elif status == Status.ChapterStatus.COMPLETED:
                timestamp = datetime.now().isoformat()
                path_col = f"{prefix}_path"
                path_val = kwargs.get('path')
                if path_val is None:
                    path_val = write_path(ebook_no, voice_code, chapter_idx, stage, shorts_idx=short_idx)

                query = f"""
                UPDATE SHORTS_PROGRESS
                SET {prefix}_status = ?, {prefix}_generated_timestamp = ?,
                    last_status_change_timestamp = CURRENT_TIMESTAMP
                """
                params: list[object] = [status, timestamp]

                if path_val:
                    query += f", {path_col} = ?"
                    params.append(path_val)

                if 'youtube_url' in kwargs:
                    query += ", youtube_url = ?"
                    params.append(kwargs['youtube_url'])

                query += " WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ? AND short_idx = ?"
                params.extend([ebook_no, voice_code, chapter_idx, short_idx])
                self._cursor.execute(query, tuple(params))

            elif status == Status.ChapterStatus.FAILED:
                error_msg = kwargs.get('error_message', 'Unknown error')
                error_type = kwargs.get('error_type', Status.ErrorType.UNKNOWN)

                query = f"""
                UPDATE SHORTS_PROGRESS
                SET {prefix}_status = ?, error_message = ?, error_type = ?,
                    last_status_change_timestamp = CURRENT_TIMESTAMP
                WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ? AND short_idx = ?
                """
                self._cursor.execute(query, (status, error_msg, error_type, ebook_no, voice_code, chapter_idx, short_idx))

            if self._cursor.rowcount == 0:
                log.WARNING(f"DB[{ebook_no}]: No rows updated for short {short_idx} in chapter {chapter_idx}")
                return False

            log.INFO(f"DB[{ebook_no}]: Successfully updated short {short_idx} for chapter {chapter_idx} to {status}")
            self._connection.commit()
            return True
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to update short status: {e}")
            return False

    def update_processing_state(self, ebook_no: int, category: str, 
                               new_stage: str, new_chapter_idx: int) -> bool:
        """
        Update PROCESSING_STATE with new stage and chapter index.
        Uses transaction for atomicity.
        """
        try:
            timestamp = datetime.now().isoformat()
            self._cursor.execute("""
            UPDATE PROCESSING_STATE 
            SET stage = ?, current_chapter_idx = ?, last_updated_timestamp = ?
            WHERE ebook_no = ? AND category = ?
            """, (new_stage, new_chapter_idx, timestamp, ebook_no, category))
            
            if self._cursor.rowcount == 0:
                log.WARNING(f"DB[{ebook_no}]: Processing state not found, creating new entry")
                self._cursor.execute("""
                INSERT INTO PROCESSING_STATE (ebook_no, category, stage, current_chapter_idx)
                VALUES (?, ?, ?, ?)
                """, (ebook_no, category, new_stage, new_chapter_idx))
            
            log.INFO(f"DB[{ebook_no}]: Processing state updated successfully")
            self._connection.commit()
            return True
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to update processing state: {e}")
            return False
     
    def mark_chapter_retry(self, ebook_no: int, voice_code: int, chapter_idx: int, 
                          stage: str, error_msg: str, base_delay: int = 30, 
                          backoff_factor: int = 2, max_retries: int = 3) -> bool:
        """
        Mark chapter for retry with exponential backoff.
        Updates retry count, calculates next retry time, and updates status accordingly.
        """
        log.INFO(f"DB[{ebook_no}]: Marking chapter {chapter_idx} for retry on stage {stage}")
        try:
            prefix = Status.convertStages(stage)
            if not prefix:
                log.ERROR(f"DB[{ebook_no}]: Unknown stage {stage} for retry")
                return False
            
            # Get current retry count
            self._cursor.execute("""
            SELECT retry_count FROM CHAPTER_PROGRESS 
            WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?
            """, (ebook_no, voice_code, chapter_idx))
            
            row = self._cursor.fetchone()
            retry_count = (row[0] if row else 0) + 1
            
            # Calculate next retry time with exponential backoff
            delay_seconds = base_delay * (backoff_factor ** (retry_count - 1))
            next_retry_time = datetime.now() + timedelta(seconds=delay_seconds)
            
            # Determine status based on retry count used
            if retry_count > max_retries:
                new_status = Status.ChapterStatus.MANUAL_REVIEW_NEEDED
            else:
                new_status = Status.ChapterStatus.FAILED
                
            query = f"""
            UPDATE CHAPTER_PROGRESS 
            SET retry_count = ?, next_retry_timestamp = ?, error_message = ?,
                last_status_change_timestamp = CURRENT_TIMESTAMP, """
            query += f"{prefix}_status = ? "
            query += "WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?"
            
            # Update chapter progress
            self._cursor.execute(query, (retry_count, next_retry_time.isoformat(), error_msg, new_status, ebook_no, voice_code, chapter_idx))
            
            if self._cursor.rowcount == 0:
                log.WARNING(f"DB[{ebook_no}]: Chapter {chapter_idx} not found, creating entry")
                query = f"""
                INSERT INTO CHAPTER_PROGRESS 
                (ebook_no, voice_code, chapter_idx, category, retry_count, 
                 next_retry_timestamp, error_message, {prefix}_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                self._cursor.execute(query, (ebook_no, voice_code, chapter_idx, 'unknown', retry_count, 
                      next_retry_time.isoformat(), error_msg, new_status))
            
            log.INFO(f"DB[{ebook_no}]: Chapter {chapter_idx} scheduled for retry. Attempt {retry_count}/{max_retries}")
            self._connection.commit()
            return True
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to mark chapter for retry: {e}")
            return False
    
    def get_pending_retries(self) -> List[Tuple[int, int, int, str]]:
        """
        Query for chapters ready to retry.
        Returns list of (ebook_no, voice_code, chapter_idx, stage) tuples
        """
        log.INFO("DB: Getting pending retries")
        try:
            current_time = datetime.now().isoformat()
            self._cursor.execute("""
            SELECT DISTINCT ebook_no, voice_code, chapter_idx,
                CASE 
                    WHEN audio_status = ? THEN ?
                    WHEN video_status = ? THEN ?
                    WHEN upload_status = ? THEN ?
                    ELSE ?
                END as stage
            FROM CHAPTER_PROGRESS 
            WHERE next_retry_timestamp IS NOT NULL 
              AND next_retry_timestamp <= ?
              AND (audio_status = ? OR video_status = ? OR upload_status = ?)
            ORDER BY next_retry_timestamp ASC
            """, (Status.ChapterStatus.FAILED, 'AUDIO_GEN',
                  Status.ChapterStatus.FAILED, 'VIDEO_GEN',
                  Status.ChapterStatus.FAILED, 'UPLOAD',
                  'UNKNOWN', current_time,
                  Status.ChapterStatus.FAILED, Status.ChapterStatus.FAILED, Status.ChapterStatus.FAILED))
            
            result = self._cursor.fetchall()
            log.INFO(f"DB: Found {len(result)} chapters pending retry")
            return result
        except sqlite3.Error as e:
            log.ERROR(f"DB: Failed to get pending retries: {e}")
            return []
        
    def get_stage_retries(self, stage) -> List[Tuple[int, int, int, str]]:
        """
        Query for chapters ready to retry based on next_retry_timestamp <= now.
        Returns list of (ebook_no, voice_code, chapter_idx, category) tuples
        """
        prefix = Status.convertStages(stage)
        log.INFO(f"DB: Getting pending retries for {stage}")
        try:
            current_time = datetime.now().isoformat()
            self._cursor.execute(f"""
            SELECT DISTINCT ebook_no, voice_code, chapter_idx, category
            FROM CHAPTER_PROGRESS 
            WHERE {prefix}_status = ?
              AND (next_retry_timestamp IS NULL OR next_retry_timestamp <= ?)
            ORDER BY next_retry_timestamp ASC
            """, (Status.ChapterStatus.FAILED, current_time))
            
            result = self._cursor.fetchall()
            log.INFO(f"DB: Found {len(result)} chapters pending retry for {stage}")
            return result
        except sqlite3.Error as e:
            log.ERROR(f"DB: Failed to get pending retries: {e}")
            return []

    def mark_short_retry(self, ebook_no: int, voice_code: int, chapter_idx: int,
                         short_idx: int, stage: str, error_msg: str,
                         base_delay: int = 30, backoff_factor: int = 2, max_retries: int = 3) -> bool:
        """
        Mark a short for retry with exponential backoff in SHORTS_PROGRESS.
        """
        log.INFO(f"DB[{ebook_no}]: Marking short {short_idx} of chapter {chapter_idx} for retry on stage {stage}")
        try:
            prefix = Status.convertStages(stage)
            if not prefix:
                log.ERROR(f"DB[{ebook_no}]: Unknown stage {stage} for short retry")
                return False

            self._cursor.execute("""
            SELECT retry_count, category FROM SHORTS_PROGRESS 
            WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ? AND short_idx = ?
            """, (ebook_no, voice_code, chapter_idx, short_idx))

            row = self._cursor.fetchone()
            retry_count = (row[0] if row else 0) + 1
            category = row[1] if row else 'unknown'

            delay_seconds = base_delay * (backoff_factor ** (retry_count - 1))
            next_retry_time = datetime.now() + timedelta(seconds=delay_seconds)

            if retry_count > max_retries:
                new_status = Status.ChapterStatus.MANUAL_REVIEW_NEEDED
            else:
                new_status = Status.ChapterStatus.FAILED

            query = f"""
            UPDATE SHORTS_PROGRESS 
            SET retry_count = ?, next_retry_timestamp = ?, error_message = ?,
                last_status_change_timestamp = CURRENT_TIMESTAMP, {prefix}_status = ?
            WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ? AND short_idx = ?
            """

            self._cursor.execute(query, (retry_count, next_retry_time.isoformat(), error_msg, new_status, ebook_no, voice_code, chapter_idx, short_idx))

            if self._cursor.rowcount == 0:
                query = f"""
                INSERT INTO SHORTS_PROGRESS 
                (ebook_no, voice_code, chapter_idx, short_idx, category, retry_count, 
                 next_retry_timestamp, error_message, {prefix}_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                self._cursor.execute(query, (ebook_no, voice_code, chapter_idx, short_idx, category, retry_count, 
                      next_retry_time.isoformat(), error_msg, new_status))

            self._connection.commit()
            return True
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to mark short for retry: {e}")
            return False

    def reset_chapter_status(self, ebook_no: int, voice_code: int, chapter_idx: int, stage: Optional[str] = None) -> bool:
        """
        Admin reset path: resets a chapter's status back to NOT_STARTED and clears retry state.
        """
        try:
            if stage:
                prefix = Status.convertStages(stage)
                if not prefix:
                    return False
                query = f"""
                UPDATE CHAPTER_PROGRESS
                SET {prefix}_status = ?, retry_count = 0, next_retry_timestamp = NULL, error_message = NULL,
                    last_status_change_timestamp = CURRENT_TIMESTAMP
                WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?
                """
                self._cursor.execute(query, (Status.ChapterStatus.NOT_STARTED, ebook_no, voice_code, chapter_idx))
            else:
                self._cursor.execute("""
                UPDATE CHAPTER_PROGRESS
                SET audio_status = ?, video_status = ?, upload_status = ?,
                    retry_count = 0, next_retry_timestamp = NULL, error_message = NULL,
                    last_status_change_timestamp = CURRENT_TIMESTAMP
                WHERE ebook_no = ? AND voice_code = ? AND chapter_idx = ?
                """, (Status.ChapterStatus.NOT_STARTED, Status.ChapterStatus.NOT_STARTED, Status.ChapterStatus.NOT_STARTED, ebook_no, voice_code, chapter_idx))

            self._connection.commit()
            log.INFO(f"DB[{ebook_no}]: Reset chapter status for chapter {chapter_idx}, voice {voice_code}")
            return True
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to reset chapter status: {e}")
            return False

    def reset_book_processing(self, ebook_no: int) -> bool:
        """
        Admin reset path: resets a book's PROCESSING_STATE to IDLE and current_chapter_idx to 0,
        and resets all chapter progress rows for that book.
        """
        try:
            self._cursor.execute("""
            UPDATE PROCESSING_STATE
            SET stage = ?, current_chapter_idx = 0, last_updated_timestamp = CURRENT_TIMESTAMP, error_log = NULL
            WHERE ebook_no = ?
            """, (Status.ProcessingStage.IDLE, ebook_no))

            self._cursor.execute("""
            UPDATE CHAPTER_PROGRESS
            SET audio_status = ?, video_status = ?, upload_status = ?,
                retry_count = 0, next_retry_timestamp = NULL, error_message = NULL,
                last_status_change_timestamp = CURRENT_TIMESTAMP
            WHERE ebook_no = ?
            """, (Status.ChapterStatus.NOT_STARTED, Status.ChapterStatus.NOT_STARTED, Status.ChapterStatus.NOT_STARTED, ebook_no))

            self._connection.commit()
            log.INFO(f"DB[{ebook_no}]: Reset processing state and chapter progress for book {ebook_no}")
            return True
        except sqlite3.Error as e:
            log.ERROR(f"DB[{ebook_no}]: Failed to reset book processing state: {e}")
            return False

class createDB:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls,  *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(createDB, cls).__new__(cls)
        return cls._instance 
    
    def __init__(self, path = config.METADB_PATH):
        if not hasattr(self, "_initialized"):
            # initialize the SQLite DB
            self._connection = None
            self._initialized = True
            self._path = path
    
    def _ensure_cursor(self):
        if getattr(self, "_connection", None) is None or getattr(self, "_cursor", None) is None:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            self._connection = sqlite3.connect(self._path, check_same_thread=False)
            self._cursor = self._connection.cursor()

    def __enter__(self):
        """Context manager entry method."""
        self._ensure_cursor()
        log.INFO(f"DB: Connection opened for {self._path}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit method."""
        if self._connection:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
                log.ERROR(f"DB: Exception occurred - {exc_type}, {exc_val}")
            self._connection.close()
            self._connection = None
            log.INFO("DB: Connection closed")     
    
    def createChapterStatus(self):
        query = """ CREATE TABLE "CHAPTER_PROGRESS" (
            "id"	INTEGER,
            "ebook_no"	INTEGER NOT NULL,
            "voice_code"	INTEGER NOT NULL,
            "chapter_idx"	INTEGER NOT NULL,
            "category"	TEXT NOT NULL,
            "audio_status"	TEXT DEFAULT 'NOT_STARTED' CHECK("audio_status" IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'AUDIO_ARCHIVED', 'DELETED')),
            "audio_path"	TEXT,
            "audio_generated_timestamp"	DATETIME,
            "video_status"	TEXT DEFAULT 'NOT_STARTED' CHECK("video_status" IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'VIDEO_ARCHIVED', 'DELETED')),
            "video_path"	TEXT,
            "video_generated_timestamp"	DATETIME,
            "waveform_path"	TEXT,
            "upload_status"	TEXT DEFAULT 'NOT_STARTED' CHECK("upload_status" IN ('NOT_STARTED', 'UPLOADING', 'COMPLETED', 'FAILED', 'PAUSED_QUOTA_EXCEEDED', 'MANUAL_REVIEW_NEEDED', 'DELETED')),
            "upload_path" TEXT,
            "youtube_url"	TEXT,
            "upload_generated_timestamp"	DATETIME,
            "retry_count"	INTEGER DEFAULT 0,
            "next_retry_timestamp"	DATETIME,
            "error_message"	TEXT,
            "error_type"	TEXT DEFAULT 'UNKNOWN' CHECK("error_type" IN ('TRANSIENT', 'PERMANENT', 'API_QUOTA', 'UNKNOWN')),
            "created_timestamp"	DATETIME DEFAULT CURRENT_TIMESTAMP,
            "last_status_change_timestamp"	DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE("ebook_no","voice_code","chapter_idx","category"),
            PRIMARY KEY("id" AUTOINCREMENT)
        )
        """
        self._cursor.execute(query)

    def createShortsStatus(self):
        query = """
        CREATE TABLE "SHORTS_PROGRESS" (
            "id"	INTEGER,
            "ebook_no"	INTEGER NOT NULL,
            "voice_code"	INTEGER NOT NULL,
            "chapter_idx"	INTEGER NOT NULL,
            "short_idx"	INTEGER NOT NULL,
            "category"	TEXT NOT NULL,
            "audio_status"	TEXT DEFAULT 'NOT_STARTED' CHECK("audio_status" IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'AUDIO_ARCHIVED', 'DELETED')),
            "audio_path"	TEXT,
            "audio_generated_timestamp"	DATETIME,
            "video_status"	TEXT DEFAULT 'NOT_STARTED' CHECK("video_status" IN ('NOT_STARTED', 'GENERATING', 'COMPLETED', 'FAILED', 'VIDEO_ARCHIVED', 'DELETED')),
            "video_path"	TEXT,
            "video_generated_timestamp"	DATETIME,
            "waveform_path"	TEXT,
            "upload_status"	TEXT DEFAULT 'NOT_STARTED' CHECK("upload_status" IN ('NOT_STARTED', 'UPLOADING', 'COMPLETED', 'FAILED', 'PAUSED_QUOTA_EXCEEDED', 'MANUAL_REVIEW_NEEDED', 'DELETED')),
            "upload_path" TEXT,
            "youtube_url"	TEXT,
            "youtube_shorts_url"	TEXT,
            "upload_generated_timestamp"	DATETIME,
            "retry_count"	INTEGER DEFAULT 0,
            "next_retry_timestamp"	DATETIME,
            "error_message"	TEXT,
            "error_type"	TEXT DEFAULT 'UNKNOWN' CHECK("error_type" IN ('TRANSIENT', 'PERMANENT', 'API_QUOTA', 'UNKNOWN')),
            "created_timestamp"	DATETIME DEFAULT CURRENT_TIMESTAMP,
            "last_status_change_timestamp"	DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE("ebook_no","voice_code","chapter_idx","short_idx","category"),
            PRIMARY KEY("id" AUTOINCREMENT)
        )
        """
        self._cursor.execute(query)

    def createProcessingState(self):
        query = """
        CREATE TABLE "PROCESSING_STATE" (
            "id"	INTEGER,
            "ebook_no"	INTEGER NOT NULL UNIQUE,
            "category"	TEXT NOT NULL,
            "current_chapter_idx"	INTEGER DEFAULT 0,
            "stage"	TEXT NOT NULL CHECK("stage" IN ('IDLE', 'PROCESSING', 'COMPLETE')),
            "last_updated_timestamp"	DATETIME DEFAULT CURRENT_TIMESTAMP,
            "error_log"	TEXT,
            "created_timestamp"	DATETIME DEFAULT CURRENT_TIMESTAMP,
            "rating"	INTEGER,
            "max_chapter_idx"	INTEGER DEFAULT -1,
            UNIQUE("ebook_no","category"),
            PRIMARY KEY("id" AUTOINCREMENT)
        )
        """
        self._cursor.execute(query)
        
    def createMetadata(self):
        query = """
        CREATE TABLE "EBOOK_METADATA" (
            "ebook_no"	INTEGER,
            "source"	TEXT,
            "status"	TEXT,
            "title"	TEXT,
            "author"	TEXT,
            "language"	TEXT,
            "subject"	TEXT,
            "content_url"	TEXT,
            "summary"	TEXT,
            "failure_count"	INTEGER,
            "category"	TEXT,
            "rating"	REAL,
            "no_rating"	INTEGER
        )
        """
        self._cursor.execute(query)

    def createYoutubeMap(self):
        query = """
        CREATE TABLE "YOUTUBE_MAP" (
            "category_name"	TEXT NOT NULL,
            "category"	TEXT NOT NULL,
            "yt_hash"	TEXT NOT NULL,
            "voice_idx"	TEXT NOT NULL UNIQUE
        )
        """
        self._cursor.execute(query)
    
    def createKVS(self):
        query = """
        CREATE TABLE IF NOT EXISTS "KEY_VALUE_STORE" (
            "key"	TEXT NOT NULL,
            "value"	TEXT NOT NULL,
            "cypher_key"	TEXT DEFAULT 'NONE',
            PRIMARY KEY("key")
        )
        """
        self._cursor.execute(query)
        
        # add KVS data safely
        client_secret = "./Data/Secrets/client_secrets.json"
        if os.path.exists(client_secret):
            try:
                with open(client_secret, 'r', encoding='utf-8') as file:
                    client_config = json.load(file)
                iv, encrypted_cc = encrypt(json.dumps(client_config).encode('utf-8'))
                log.INFO("DB: Setting value for client_secret")
                self._cursor.execute("INSERT INTO KEY_VALUE_STORE VALUES (?,?,?)",("client_secret", encrypted_cc.hex(), iv.hex()))
            except Exception as e:
                log.ERROR(f"DB: Failed to read client_secret: {e}")
        else:
            dummy_config = {"installed": {"client_id": "dummy_client_id", "client_secret": "dummy_secret"}}
            iv, encrypted_cc = encrypt(json.dumps(dummy_config).encode('utf-8'))
            self._cursor.execute("INSERT INTO KEY_VALUE_STORE VALUES (?,?,?)",("client_secret", encrypted_cc.hex(), iv.hex()))
        
        dir_path = Path('./Data/Secrets')
        if dir_path.exists():
            token_files = list(dir_path.glob('token*.json'))
            for token_path in token_files:
                key = token_path.name.split('.json')[0]
                log.INFO(f"DB: Setting value for {key}")
                try:
                    with open(token_path, 'r', encoding='utf-8') as file:
                        token_value = json.load(file)
                    iv, encrypted_token = encrypt(json.dumps(token_value).encode('utf-8'))
                    self._cursor.execute("INSERT INTO KEY_VALUE_STORE VALUES (?,?,?)", (key, encrypted_token.hex(), iv.hex(),))
                except Exception as e:
                    log.ERROR(f"DB: Failed token read {key}: {e}")
        self._connection.commit()
    def generateTestContent(self, num: int) -> dict:
        content = {"ToC": {}, "Book_Content": {}}
        toc_dict = {}
        book_content_dict = {}
        
        for ch_idx in range(3):
            chapter_name = f"chapter_{ch_idx}"
            toc_val = f"CHAPTER I. TEST CHAPTER {ch_idx+1} BOOK {num}"
            book_content_value = {"header": toc_val, "content" : [f"THIS IS TEST CONTENT FOR CHAPTER {ch_idx} for Book {num}", 
                                                                  "Punctuation test: epilods ... commas, periods. fuck yeah", 
                                                                  "I AM ON FIRE",
                                                                  "Alice was beginning to get very tired of sitting by her sister on the bank, and of having nothing to do: once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it, “and what is the use of a book,” thought Alice “without pictures or conversations?”",
                                                                  "So she was considering in her own mind (as well as she could, for the hot day\r\nmade her feel very sleepy and stupid), whether the pleasure of making a\r\ndaisy-chain would be worth the trouble of getting up and picking the daisies,\r\nwhen suddenly a White Rabbit with pink eyes ran close by her."]}
            toc_dict[chapter_name] = toc_val
            book_content_dict[chapter_name] = book_content_value
        
        content["ToC"] = toc_dict
        content["Book_Content"] = book_content_dict
        return content
        
    def createTestJSON(self):
        os.makedirs(config.JSON_FILEPATH, exist_ok=True)
        for i in range(1,6):
            content = self.generateTestContent(i)
            filename = f"/book_{i}.json"
            with open(config.JSON_FILEPATH + filename, "w", encoding="utf-8") as file:
                json.dump(content, file, ensure_ascii=False, indent=4)
    
    def cleanUp(self):
        for i in range(1, 6):
            # Clean up books:
            json_path = Path(config.JSON_FILEPATH)/f"book_{i}.json"
            if json_path.exists and json_path.is_file():
                try:
                    os.remove(json_path)
                except Exception as e:
                    print(e)
                    
            # Clean up audio and video    
            for base_path in [config.AUD_FILEPATH, config.OUTPUT_FOLDER]:
                dir_path = Path(base_path) / f"Book_{i}"
                
                if dir_path.exists() and dir_path.is_dir():
                    try:
                        shutil.rmtree(dir_path)
                    except Exception as e:
                        print(e)   
        
    def createTestDB(self):
        self._ensure_cursor()
        self.cleanUp()
        self.createTestJSON()
        self.createChapterStatus()
        self.createShortsStatus()
        self.createProcessingState()
        self.createMetadata()
        self.createYoutubeMap()
        self.createKVS()
        
        addYTMapQuery = """
        INSERT INTO YOUTUBE_MAP ("category_name", "category", "yt_hash", "voice_idx") VALUES ('Relaxing and Soothing', 'cat(RS)', 'UCXeqq2XcvF7jjEcv35dPl8A', '3,7');
        INSERT INTO YOUTUBE_MAP ("category_name", "category", "yt_hash", "voice_idx") VALUES ('Mystery and Suspense', 'cat(MS)', 'UCfOw-0ovjVZSE8HvaCNJJ_Q', '18,26');
        INSERT INTO YOUTUBE_MAP ("category_name", "category", "yt_hash", "voice_idx") VALUES ('Whimsical escapism', 'cat(WE)', 'UCKpi4fdhxKbO_DWUD3FODTA', '20,23');
        INSERT INTO YOUTUBE_MAP ("category_name", "category", "yt_hash", "voice_idx") VALUES ('Litrary Masterpieces', 'cat(LM)', 'UChDu5fX4ICAQSgdT653TGzA', '17,22');
        """
        addMetadataQuery = """
        INSERT INTO EBOOK_METADATA ("ebook_no", "source", "status", "title", "author", "language", "subject", "content_url", "summary", "failure_count", "category", "rating", "no_rating") VALUES (1, 'https://www.gutenberg.org/ebooks/1', 'PARSED', 'TEST EBOOK 1', 'EBOOK AUTHOR 1', 'English', 'genre_1, genre_2, genre_3, genre_4,', 'https://www.gutenberg.org/cache/epub/1/pg1-images.html', '', 0, 'cat(WE)', 4.00, 100);
        INSERT INTO EBOOK_METADATA ("ebook_no", "source", "status", "title", "author", "language", "subject", "content_url", "summary", "failure_count", "category", "rating", "no_rating") VALUES (3, 'https://www.gutenberg.org/ebooks/3', 'PARSED', 'TEST EBOOK 3', 'EBOOK AUTHOR 3', 'English', 'genre_1, genre_2, genre_3, genre_4,', 'https://www.gutenberg.org/cache/epub/3/pg3-images.html', '', 0, 'cat(RS)', 4.00, 100);
        INSERT INTO EBOOK_METADATA ("ebook_no", "source", "status", "title", "author", "language", "subject", "content_url", "summary", "failure_count", "category", "rating", "no_rating") VALUES (4, 'https://www.gutenberg.org/ebooks/4', 'PARSED', 'TEST EBOOK 4', 'EBOOK AUTHOR 4', 'English', 'genre_1, genre_2, genre_3, genre_4,', 'https://www.gutenberg.org/cache/epub/4/pg4-images.html', '', 0, 'cat(MS)', 4.00, 100);
        INSERT INTO EBOOK_METADATA ("ebook_no", "source", "status", "title", "author", "language", "subject", "content_url", "summary", "failure_count", "category", "rating", "no_rating") VALUES (5, 'https://www.gutenberg.org/ebooks/5', 'PARSED', 'TEST EBOOK 5', 'EBOOK AUTHOR 5', 'English', 'genre_1, genre_2, genre_3, genre_4,', 'https://www.gutenberg.org/cache/epub/5/pg5-images.html', '', 0, 'cat(LM)', 4.00, 100);
        """
        addProcessingState = """
        INSERT INTO PROCESSING_STATE ("id", "ebook_no", "category", "current_chapter_idx", "stage", "last_updated_timestamp", "error_log", "created_timestamp", "rating", "max_chapter_idx") VALUES (1, 1, 'cat(WE)', 0, 'IDLE', CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP, 4.00, 3);
        INSERT INTO PROCESSING_STATE ("id", "ebook_no", "category", "current_chapter_idx", "stage", "last_updated_timestamp", "error_log", "created_timestamp", "rating", "max_chapter_idx") VALUES (3, 3, 'cat(RS)', 0, 'IDLE', CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP, 4.00, 3);
        INSERT INTO PROCESSING_STATE ("id", "ebook_no", "category", "current_chapter_idx", "stage", "last_updated_timestamp", "error_log", "created_timestamp", "rating", "max_chapter_idx") VALUES (4, 4, 'cat(MS)', 0, 'IDLE', CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP, 4.00, 3);
        INSERT INTO PROCESSING_STATE ("id", "ebook_no", "category", "current_chapter_idx", "stage", "last_updated_timestamp", "error_log", "created_timestamp", "rating", "max_chapter_idx") VALUES (5, 5, 'cat(LM)', 0, 'IDLE', CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP, 4.00, 3);
        """
        self._cursor.executescript(addProcessingState+addMetadataQuery+addYTMapQuery)