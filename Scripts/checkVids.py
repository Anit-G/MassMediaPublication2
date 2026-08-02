import os
import subprocess
import shlex
import math
import tempfile

# VIDEO_DIR = "./Data/Background/BGP/Converts_MP4s"
VIDEO_DIR = "./Data/Background/BGP/Original Pics"
OUTPUT_DIR = "./Data/Background/BGP/"

# VIDEO_DIR = "./Data/Background/BGV/orginals"
# OUTPUT_DIR = "./Data/Background/BGV/"
MIN_DURATION = 1800  # 30 minutes
TARGET_FPS = 24

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_video_info(filepath):
    cmd_duration = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{filepath}"'
    duration = float(subprocess.check_output(shlex.split(cmd_duration)).decode().strip())

    cmd_fps = f'ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "{filepath}"'
    fps_raw = subprocess.check_output(shlex.split(cmd_fps)).decode().strip().replace(",", "")
    
    if '/' in fps_raw:
        num, denom = map(int, fps_raw.split('/'))
        fps = num / denom
    else:
        fps = float(fps_raw)

    return duration, fps

def create_concat_file(input_path, loop_count):
    concat_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    abs_path = os.path.abspath(input_path)
    for _ in range(loop_count):
        concat_file.write(f"file '{abs_path}'\n")
    concat_file.flush()
    concat_file.close()
    return concat_file.name

def reencode_and_loop_concat(input_path, output_path, loop_count):
    concat_list_path = create_concat_file(input_path, loop_count)
    cmd = f'''ffmpeg -y -f concat -safe 0 -i "{concat_list_path}" \
-filter:v fps={TARGET_FPS} -t {MIN_DURATION} \
-c:v h264_nvenc -preset fast -c:a aac -shortest "{output_path}"'''
    subprocess.run(shlex.split(cmd), check=True)
    os.remove(concat_list_path)

def image_to_video(image_path, output_path):
    cmd = f'''ffmpeg -y -loop 1 -i "{image_path}" \
-f lavfi -t {MIN_DURATION} -i anullsrc=r=48000:cl=stereo \
-shortest -c:v h264_nvenc -preset fast -r {TARGET_FPS} \
-c:a aac -b:a 192k -pix_fmt yuv420p -t {MIN_DURATION} "{output_path}"'''
    subprocess.run(shlex.split(cmd), check=True)

for filename in os.listdir(VIDEO_DIR):
    if not filename.lower().endswith((".mp4", ".mkv", ".mov", ".jpg", ".jpeg", ".png")):
        continue

    input_path = os.path.join(VIDEO_DIR, filename)
    base_name = os.path.splitext(filename)[0]
    output_path = os.path.join(OUTPUT_DIR, f"{base_name}_fixed.mp4")

    if filename.lower().endswith((".jpg", ".jpeg", ".png")):
        print(f"\n🖼️ Converting image to 30-min video: {filename}")
        try:
            image_to_video(input_path, output_path)
            print(f"✅ Created video from image: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg image-to-video failed: {e}")
        continue

    print(f"\n▶️ Processing video: {filename}")
    try:
        duration, fps = get_video_info(input_path)
    except Exception as e:
        print(f"❌ Could not analyze video: {e}")
        continue

    if abs(fps - TARGET_FPS) < 0.1 and duration >= MIN_DURATION:
        print("✅ Already 24 FPS and ≥ 30 min")
        continue

    loop_count = math.ceil(MIN_DURATION / duration)
    print(f"⚙️ Re-encoding to 24 FPS and looping {loop_count}× using concat demuxer...")

    try:
        reencode_and_loop_concat(input_path, output_path, loop_count)
        print(f"✅ Done: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg failed: {e}")
