import os
import Utils.Central_Logger as log
from Workers.Orchestrator import WorkerOrchestrator
from Utils.DB_Operations import createDB

def main() -> None:
    testdb_filepath = "./Data/testDB.db3"
    if os.path.isfile(testdb_filepath):
        os.remove(testdb_filepath)
    with createDB("./Data/testDB.db3") as testdb:
        testdb.createTestDB()
    
    orchestrator = WorkerOrchestrator(
        poll_interval=2,
        audio_runs = 1,
        video_runs = 1,
        upload_runs = 1
    )
    orchestrator.start()


if __name__ == "__main__":
    main()