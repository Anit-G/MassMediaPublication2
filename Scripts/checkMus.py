import os
import subprocess
import math
import tempfile

AUDIO_DIR = "./Data/Background/BGM/Orignals/"
OUTPUT_DIR = "./Data/Background/BGM/"
MIN_DURATION = 1800  # 30 minutes
MP3_BITRATE = "192k"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_audio_duration(filepath):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return float(result.stdout.strip())

def create_concat_file(input_path, loop_count):
    concat_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    for _ in range(loop_count):
        concat_file.write(f"file '{os.path.abspath(input_path)}'\n")
    concat_file.flush()
    concat_file.close()
    return concat_file.name

def loop_audio_mp3(input_path, output_path, loop_count):
    concat_txt = create_concat_file(input_path, loop_count)
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0', '-i', concat_txt,
        '-t', str(MIN_DURATION),
        '-af', f"loudnorm=I=-15:TP=-2:LRA=7",
        '-c:a', 'libmp3lame', '-b:a', MP3_BITRATE,
        output_path
    ]
    subprocess.run(cmd, check=True)
    os.remove(concat_txt)
    
for filename in os.listdir(AUDIO_DIR):
    if not filename.lower().endswith(".mp3"):
        continue

    input_path = os.path.join(AUDIO_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, f"{os.path.splitext(filename)[0]}.mp3")

    print(f"\n▶️ Processing: {filename}")

    try:
        duration = get_audio_duration(input_path)
    except Exception as e:
        print(f"❌ Error reading duration: {e}")
        continue

    if duration >= MIN_DURATION:
        print("✅ Already ≥ 30 min")
        continue

    loop_count = math.ceil(MIN_DURATION / duration)
    print(f"🔁 Looping {loop_count}× using concat demuxer...")

    try:
        loop_audio_mp3(input_path, output_path, loop_count)
        print(f"✅ Saved: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg failed: {e}")
