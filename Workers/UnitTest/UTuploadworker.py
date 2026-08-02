import sys
import os

# Adds the parent directory (workers) to the search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VideoGen.UpMonYoutube import UpMonYouTube
from Workers.UploadWorker import UploadWorker

def main():
    
    UpMonYouTube("cat(RS)")
    UpMonYouTube("cat(MS)")
    UpMonYouTube("cat(WE)")
    UpMonYouTube("cat(LM)")
    
    # category = "cat(RS)"
    # upyt = UpMonYouTube(category)
    # worker = UploadWorker(upyt, category)
    # worker.run()

if __name__ == "__main__":
    main()