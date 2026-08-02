import sys
import os
import shutil
from path import Path

# Adds the parent directory (workers) to the search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import Utils.Config_vars as config
from VideoGen.VideoGenerator import VideoGen
from Workers.VideoGenWorker import VideoGenWorker

def cleanup_dir(base_path):
    for i in range(1, 6):
        dir_path = Path(base_path) / f"Book_{i}"
        
        if dir_path.exists() and dir_path.is_dir():
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                print(e)

def main():
    cleanup_dir(config.OUTPUT_FOLDER)
    vidGen = VideoGen()
    category = "cat(RS)"
    worker = VideoGenWorker(vidGen, category)
    worker.run()
    
if __name__ == "__main__":
    main() 