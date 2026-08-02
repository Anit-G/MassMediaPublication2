import logging
import logging.handlers
import Utils.Config_vars as config
import time
import os
from pathlib import Path

"""
    Declare Loggers
"""
log_dir = config.LOG_DIR
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# delete if more then 10 files in the directory
log_path = Path(log_dir)
files = [f for f in log_path.iterdir() if f.is_file()]
if len(files) > 10:
    files_sorted = sorted(files, key = lambda f: f.stat().st_ctime, reverse=True)
    file_to_delete = files_sorted[10:]
    
    for file in file_to_delete:
        try:
            file.unlink()
        except Exception as e:
            print(f"Error while deleteing old logs: {e}")
    
logger = logging.getLogger("TTS")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
timestamp = time.strftime("%Y%m%d", time.localtime(time.time()))

# Handler 1: Log everything to 'logs/app.log'
handler = logging.handlers.RotatingFileHandler(f"{log_dir}/tts_{timestamp}.log", maxBytes=1000000, backupCount=5)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
# Add handlers to logger
logger.addHandler(handler)
# logger.addHandler(file_handler_debug)

def DEBUG(str):
    logger.debug(str)
    
def WARNING(str):
    logger.warning(str)
    
def ERROR(str):
    logger.error(str)

def INFO(str):
    logger.info(str)
