""" Scrapper related configurable variables """
# Groud Source for Book titles
BOOK_DATA_FILE = './Data/book_sources.csv'
# Rate at which DB is updated when parsing through metadata of books 
DB_WRITE_FREQUENCY = 100
# Log files directory
LOG_DIR = './Central_Logs'
# Get list of ebook numbers that need to be test run
TEST_LIST_FILE_PATH = './Configs/test_lst.txt'
# Metadata Database Sqlite path
# METADB_PATH = './Data/mainDB.db3'
METADB_PATH = './Data/testDB.db3'
# Number of books to get in a single batch of status pending at a time
BOOK_BATCH_SIZE = "100"
# Use selenium vs standard python request library
USE_REQUEST = True
# filesystem path where the JSON should be written to
JSON_FILEPATH = "./Data/JSONlib"

""" TTS Related Configurable variables """
# path to save to the audio files
AUD_FILEPATH = './Data/AudFiles'
# Running the TTS BACKEND
TTS_INSTANCE = True
# Store the summaries in this folder
SUM_FILEPATH = './Data/SumFiles'
# Produce stereo audio rather then mono audio
STEREO_AUD = True
# Start producing audio from summaries
CONVERT_SUMMS = False
# Audio sample rate
AUD_SAMPLE_RATE = 22050
# TTS model speed (default 0.7, range 0.5 to 1.5)
TTS_MODEL_SPEED = 0.7
# skip tts for chapters with these headers
NON_TTS_CHAPTERS = ["preface", "etymology", "extracts", "prolog", "instructions"]
# Path to the breathe in sound effects
BREATH_IN_PATH = './Data/Background/Breaths'
# Path to the chime sound effects
CHIME_PATH = './Data/Background/Chimes'
# Minimuim length of content to be considered a chapter
MINIMUIM_CONTENT_LENGTH = 500
# use the 5 seconds chimes that were made
USE_CHIMES = False
# Average words per minute for the shorts generation (already the lower bound) TTS WPM ranges from 160 to 220 at 0.7 speed, 
# so 160 is a safe average to use for shorts generation. At 1.0 speed WPM goes up to 230 and the range is 230-300.
# TODO: Ideally each combination of speed, voice code with voice mixing ratio and mixer should be profiled for WPM and used. 
AVERAGE_SHORTS_WPM = 160
# Short generation length in minutes
SHORTS_LENGTH_MINUTES = 3.0
# under bound correction factor for short generation (to account for pauses, etc.)
SHORTS_LENGTH_CORRECTION_FACTOR = 0.95
# Max number of shorts to be generated per chapter
MAX_SHORTS_PER_CHAPTER = 5 

""" Video Generator related configurable variables """
# Path to templates file that stores all the templates for video gen
TEMPLATES_PATH = './Data/templates.json'
# path to the background video, audio and pictures
BGM_FOLDER = './Data/Background/BGM'
BGV_FOLDER = './Data/Background/BGV'
BGP_FOLDER = './Data/Background/BGP'
# Output folder for where the completed videos will be stored
OUTPUT_FOLDER = './Data/OutputVideos'
# Remove Waveform .mp4 file after video is generated
RETAIN_WF = True
# The default template to produce full length videos
DEFAULT_TEMPLATE= "temp_3"
# Audio waveform generation specs
WAVEFORM_FOLDER = './Data/Waveform'
USE_WAVEFORM = False
WAVEFORM_WIDTH  = 1920//2      # waveform is mirrored about centre y axis
WAVEFORM_HEIGHT = 200          # arbitrary
WAVEFORM_YPOS = 70
WAVEFORM_BG_COLOR = (0, 0, 0)
WAVEFORM_BAR_COLOR = (20, 185, 255) # BGR
# video generation specifics
FPS             = 24
VIDEO_DURATION = 3600
VIDEO_RESOLUTION = (1920, 1080)
BGM_VOLUME       = 0.3          # 30% volume
KOKORO_VOICEMAP = {1: "af_alloy", 2: "af_aoede", 3: "af_bella", 4: "af_heart", 5: "af_jessica", 6: "af_kore", 7: "af_nicole", 8: "af_nova", 9: "af_river", 10:"af_sarah",
                11:"af_sky", 12:"am_adam", 13:"am_echo", 14:"am_eric", 15:"am_fenrir", 16:"am_liam", 17:"am_michael", 18:"am_onyx", 19:"am_puck", 20:"am_santa",
                21:"bf_alice", 22:"bf_emma", 23:"bf_isabella", 24:"bf_lily", 25:"bm_daniel", 26:"bm_fable", 27:"bm_george", 28:"bm_lewis",}
BANDPASS_FREQ = [20,25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1500, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000]
# Wether to use one of the pre-recorded BGVs or use the looped thumbnail with VFX as the BGV
USE_STILL_BGV = True
# For shorts wether to use stills or doom scrolling game play
USE_STILL_FOR_SHORTS = False
GENERATE_SHORTS = True

""" State Management Configuration (Phase 1) """
# Database schema version for state tracking
DB_SCHEMA_VERSION = 2

# State checking interval in seconds
STATE_CHECK_INTERVAL_SECONDS = 5

# Retry policy configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2  # exponential: 30s, 60s, 120s
RETRY_BASE_DELAY_SECONDS = 30

# Pipeline Worker Control
ENABLE_AUDIO_GEN_WORKER = True
ENABLE_VIDEO_GEN_WORKER = True
ENABLE_UPLOAD_WORKER = True
WORKER_THREAD_COUNT = 3

# Storage Lifecycle Policies
DELETE_AUDIO_AFTER_VIDEO = False  # Start conservative
DELETE_VIDEO_AFTER_UPLOAD = False
RETENTION_DAYS_AUDIO = 30
RETENTION_DAYS_VIDEO = 90
ARCHIVE_TO_CLOUD = False

# Logging configuration for state management
STATE_LOG_DIR = './Central_Logs/State'
EVENTS_LOG_PATH = './Central_Logs/State/events.jsonl'

# Thumbnail generation PROMPT, arguments are (Bookt_title, Full Category Name, Full Category Name)
PROMPT = """
    You are a professional image-prompt engineer for AI art models. Produce a single image-generation prompt optimized for a YouTube audiobook thumbnail that **includes** a stylized representation of the book title inside the image. Use these placeholders:

    Book title: {}
    Channel theme: {}

    Requirements:
    - Output only one image-generation prompt string (no explanation).
    - 16:9 aspect ratio, high resolution, bold composition.
    - Create a central focal element that captures the book's mood and {}.
    - Integrate the book title as an artistic, legible element (large, bold, high-contrast typography effect — e.g., engraved, glowing, stencil) but avoid exact readable lettering the model struggles with; design it as a stylized graphic element rather than precise small text.
    - Color palette, lighting, camera angle, props, and mood should be optimized for thumbnails (high contrast, simple shapes).
    - Add in small text the word "Audiobook" in a reserved corner
    - End with negatives: "no watermarks, no signatures, avoid small unreadable text".
    - Don't include anything NSFW and construct a prompt with sufficient detail to bypass or be compliant with copyright policy. Replace words that would set copyright policy off with descriptions instead that is compliant.

    Write the final prompt as one compact sentence or short paragraph.
"""