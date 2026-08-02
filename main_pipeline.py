import argparse
import Utils.Central_Logger as log
from Workers.Orchestrator import WorkerOrchestrator

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start the MassMediaPublication worker pipeline."
    )
    parser.add_argument(
        "--audio-runs",
        type=int,
        default=1,
        help="Number of times to audio generation worker should be run",
    )
    parser.add_argument(
        "--video-runs",
        type=int,
        default=1,
        help="Number of times to video generation worker should be run",
    )
    parser.add_argument(
        "--upload-runs",
        type=int,
        default=1,
        help="Number of times to upload worker should be run",
    )

    args = parser.parse_args()
    log.INFO("main_pipeline: starting worker pipeline")

    orchestrator = WorkerOrchestrator(
        poll_interval=2,
        audio_runs = args.audio_runs,
        video_runs = args.video_runs,
        upload_runs = args.upload_runs
    )
    orchestrator.start()


if __name__ == "__main__":
    main()
