import sys
import os
import shutil
from path import Path

# Adds the parent directory (workers) to the search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from Workers.AudioGenWorker import AudioGenWorker
from TTS.TTS import TTS
from Utils.DB_Operations import createDB
import Utils.Config_vars as config

"""
Run Audio Gen Worker once for a given set of categories
"""

def cleanup_dir(base_path):
    for i in range(1, 6):
        dir_path = Path(base_path) / f"Book_{i}"
        
        if dir_path.exists() and dir_path.is_dir():
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                print(e)

def main():
    # testdb_filepath = "./Data/testDB.db3"
    # if os.path.isfile(testdb_filepath):
    #     os.remove(testdb_filepath)
    # with createDB("./Data/testDB.db3") as testdb:
    #     testdb.createTestDB()
    # cleanup_dir(config.AUD_FILEPATH)
        
    tts = TTS()
    category = "cat(RS)"
    worker = AudioGenWorker(tts, category)
    worker.run()

if __name__ == "__main__":
    main()