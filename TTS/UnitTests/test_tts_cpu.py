import os
import sys
import time
import tracemalloc

# Ensure root directory is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Safe optional imports
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None

try:
    import soundfile as sf
    HAS_SF = True
except ImportError:
    HAS_SF = False
    sf = None

try:
    import numpy as np
    HAS_NP = True
except ImportError:
    HAS_NP = False
    np = None

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

import Utils.Config_vars as config
import Utils.Central_Logger as log

# Ensure device is explicitly set to CPU in config
config.TTS_DEVICE = 'cpu'

from TTS.TTS import TTS

"""
    Benchmark and evaluation test script for running TTS on CPU.
    Reads sample text from /Data/sample_alice.txt and logs detailed performance metrics:
    - Execution Time (Pipeline Init Time & Audio Generation Time)
    - Real-Time Factor (RTF = Generation Time / Generated Audio Duration)
    - CPU Usage (%) & Memory Delta / RAM Consumption
    - Text Throughput Metrics (Character Count, Word Count, Characters/Sec, Words/Sec)
    - Audio Characteristics (Sample Rate, Duration, File Size)
"""

def get_process_memory_mb():
    if HAS_PSUTIL:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    else:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except ImportError:
            return 0.0

def test_tts_cpu_evaluation():
    log.INFO("============================================== STARTING CPU TTS EVALUATION ==============================================")
    
    # 1. Read sample text from /Data/sample_alice.txt
    sample_text_path = os.path.join(root_dir, "Data/sample_alice.txt")
        
    if not os.path.exists(sample_text_path):
        sample_text_path = "./Data/sample_alice.txt"
        
    if not os.path.exists(sample_text_path):
        print(f"[ERROR] Sample text file not found at {sample_text_path}")
        return

    with open(sample_text_path, "r", encoding="utf-8") as f:
        sample_text = f.read().strip()

    char_count = len(sample_text)
    word_count = len(sample_text.split())
    paragraph_count = len([p for p in sample_text.split("\n") if p.strip()])

    print("\n" + "=" * 80)
    print("                     TTS CPU EVALUATION & BENCHMARK REPORT                      ")
    print("=" * 80)
    print(f" Python Version          : {sys.version.split()[0]}")
    print(f" PyTorch Available       : {HAS_TORCH} ({torch.__version__ if HAS_TORCH else 'N/A'})")
    print(f" Configured Target Device : {config.TTS_DEVICE}")
    print(f" Sample Source File       : {sample_text_path}")
    print(f" Input Character Count    : {char_count:,} characters")
    print(f" Input Word Count         : {word_count:,} words")
    print(f" Input Paragraph Count    : {paragraph_count:,} paragraphs")
    print("-" * 80)

    # Track memory before initialization
    tracemalloc.start()
    mem_before_init = get_process_memory_mb()
    
    # 2. Pipeline Initialization Benchmark
    init_start_time = time.perf_counter()
    weight_dist = 0.5
    mixer = 7
    book_pipe = TTS(weight_dist, mixer)
    init_end_time = time.perf_counter()
    
    init_duration = init_end_time - init_start_time
    mem_after_init = get_process_memory_mb()
    init_ram_delta = mem_after_init - mem_before_init

    # Output directory setup
    output_dir = "./TTS/UnitTests/KoKoro_samples/"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "sample_alice_cpu_eval.wav")
    report_path = os.path.join(output_dir, "cpu_evaluation_report.txt")

    # 3. Audio Generation Benchmark
    voice_keys = [2, 7] # 2: af_aoede, 7: af_nicole
    has_active_pipelines = getattr(book_pipe, "_pipelines", None) and len(book_pipe._pipelines) > 0

    if HAS_PSUTIL:
        psutil.cpu_percent(interval=None) # Reset CPU measurement baseline

    mem_before_gen = get_process_memory_mb()
    gen_start_time = time.perf_counter()
    
    # Execute generation (or fallback if pipelines mock)
    try:
        if has_active_pipelines:
            audio_data = book_pipe._generate_audio_kokoro(voice_keys, sample_text)
        else:
            # Fallback mock audio for benchmarking pipeline flow when Kokoro weights are not local
            log.WARNING("TTS pipelines running in fallback mock mode.")
            sample_rate = config.AUD_SAMPLE_RATE
            mock_duration_sec = word_count / (config.AVERAGE_SHORTS_WPM / 60.0)
            if HAS_NP:
                audio_data = np.zeros(int(sample_rate * mock_duration_sec), dtype=np.float32)
            else:
                audio_data = b"MOCK_AUDIO_DATA"
    except Exception as exc:
        log.ERROR(f"Error during audio generation: {exc}")
        audio_data = None

    gen_end_time = time.perf_counter()
    mem_after_gen = get_process_memory_mb()
    gen_duration = gen_end_time - gen_start_time
    
    cpu_usage_pct = psutil.cpu_percent(interval=None) if HAS_PSUTIL else "N/A"
    _, peak_traced_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Audio metrics calculation
    file_size_bytes = 0
    file_size_mb = 0.0
    audio_duration_sec = 0.0

    if audio_data is not None:
        if HAS_SF and HAS_NP and isinstance(audio_data, np.ndarray):
            sf.write(output_path, audio_data, config.AUD_SAMPLE_RATE)
            audio_samples = len(audio_data)
            audio_duration_sec = audio_samples / float(config.AUD_SAMPLE_RATE) if config.AUD_SAMPLE_RATE > 0 else 0.0
        else:
            with open(output_path, "wb") as f:
                f.write(b"MOCK_CPU_TTS_AUDIO")
            audio_duration_sec = word_count / 2.5 # Estimated audio duration

        if os.path.exists(output_path):
            file_size_bytes = os.path.getsize(output_path)
            file_size_mb = file_size_bytes / (1024 * 1024)

    # Key Performance Indicators
    real_time_factor = (gen_duration / audio_duration_sec) if audio_duration_sec > 0 else 0.0
    chars_per_sec = (char_count / gen_duration) if gen_duration > 0 else 0.0
    words_per_sec = (word_count / gen_duration) if gen_duration > 0 else 0.0

    # 4. Print & Save Benchmark Report
    report_content = f"""================================================================================
                    TTS CPU EVALUATION & BENCHMARK REPORT                      
================================================================================
Timestamp                : {time.strftime("%Y-%m-%d %H:%M:%S")}
Execution Mode           : {'Active Kokoro Engine' if has_active_pipelines else 'Mock/Fallback Engine'}
PyTorch Version          : {torch.__version__ if HAS_TORCH else 'Not Installed'}
Configured Device        : {config.TTS_DEVICE}
Sample Source File       : {sample_text_path}

[INPUT TEXT STATISTICS]
- Character Count        : {char_count:,}
- Word Count             : {word_count:,}
- Paragraph Count        : {paragraph_count:,}

[EXECUTION TIME & THROUGHPUT]
- Pipeline Init Time     : {init_duration:.4f} seconds
- Audio Generation Time  : {gen_duration:.4f} seconds
- Total Time Elapsed     : {init_duration + gen_duration:.4f} seconds
- Processing Speed       : {chars_per_sec:.2f} chars/sec | {words_per_sec:.2f} words/sec

[AUDIO OUTPUT METRICS]
- Generated Audio Length  : {audio_duration_sec:.2f} seconds ({audio_duration_sec/60:.2f} minutes)
- Real-Time Factor (RTF)  : {real_time_factor:.4f}x ({'Faster than real-time' if real_time_factor < 1 else 'Slower than real-time'})
- Output Audio File Path  : {output_path}
- Output Audio File Size  : {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)
- Target Sample Rate      : {config.AUD_SAMPLE_RATE} Hz

[CPU & MEMORY RESOURCE USAGE]
- CPU Usage During Gen    : {f"{cpu_usage_pct}%" if isinstance(cpu_usage_pct, (int, float)) else cpu_usage_pct}
- Initial Process Memory  : {mem_before_init:.2f} MB
- RAM After Model Init    : {mem_after_init:.2f} MB (Delta: +{init_ram_delta:.2f} MB)
- RAM After Generation   : {mem_after_gen:.2f} MB
- Peak Traced Allocation  : {peak_traced_mem / (1024 * 1024):.2f} MB
================================================================================
"""

    print(report_content)

    with open(report_path, "w", encoding="utf-8") as rf:
        rf.write(report_content)

    print(f"[REPORT SAVED] Evaluation metrics saved to {report_path}\n")
    log.INFO(f"TTS CPU Evaluation completed. RTF: {real_time_factor:.4f}, Gen Time: {gen_duration:.2f}s, Chars/sec: {chars_per_sec:.2f}")

if __name__ == "__main__":
    test_tts_cpu_evaluation()
