#!/usr/bin/env python3

import argparse
import os
import shutil
import sys

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
except ImportError:  # pragma: no cover
    Console = None
    Table = None
    Panel = None
    box = None

def probe_and_print_video_stats(input_file):
    """
    Probes the input video and prints a colored, icon-enhanced summary using rich.
    """
    import subprocess
    import json

    if Console is None or Table is None or Panel is None or box is None:
        print("[warn] rich is not installed; skipping formatted input stats.")
        return

    console = Console()
    # ffprobe command to get video and audio stream info
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration:stream=index,codec_name,codec_type,width,height,avg_frame_rate,channels,sample_rate,bit_rate",
        "-of", "json",
        input_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        console.print(f"[bold red]❌ ffprobe failed:[/bold red] {result.stderr}")
        return
    info = json.loads(result.stdout)
    duration = float(info["format"].get("duration", 0))
    streams = info.get("streams", [])

    # Prepare stats
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    # Video info
    if video_streams:
        v = video_streams[0]
        v_codec = v.get("codec_name", "?")
        width = v.get("width", "?")
        height = v.get("height", "?")
        fps = v.get("avg_frame_rate", "0/0")
        try:
            if "/" in fps:
                num, den = map(float, fps.split("/"))
                fps_val = num / den if den != 0 else 0
            else:
                fps_val = float(fps)
        except Exception:
            fps_val = 0
    else:
        v_codec = width = height = fps_val = "?"

    # Audio info
    if audio_streams:
        a = audio_streams[0]
        a_codec = a.get("codec_name", "?")
        channels = a.get("channels", "?")
        sample_rate = a.get("sample_rate", "?")
    else:
        a_codec = channels = sample_rate = "?"

    # Build table
    table = Table(title="🎬 [bold cyan]Input Video Stats[/bold cyan]", box=box.ROUNDED, show_header=False)
    table.add_row("📄 [bold]File[/bold]", f"[white]{input_file}[/white]")
    table.add_row("⏱️ [bold]Duration[/bold]", f"[green]{duration:.2f}[/green] sec")
    table.add_row("🖼️ [bold]Video Codec[/bold]", f"[magenta]{v_codec}[/magenta]")
    table.add_row("📏 [bold]Resolution[/bold]", f"[yellow]{width}x{height}[/yellow]")
    table.add_row("🎞️ [bold]Frame Rate[/bold]", f"[blue]{fps_val:.2f}[/blue] fps")
    table.add_row("🔊 [bold]Audio Codec[/bold]", f"[magenta]{a_codec}[/magenta]")
    table.add_row("🔈 [bold]Channels[/bold]", f"[yellow]{channels}[/yellow]")
    table.add_row("🎚️ [bold]Sample Rate[/bold]", f"[blue]{sample_rate}[/blue] Hz")
    console.print(Panel(table, title="📝 [bold green]Probed Video Information[/bold green]", border_style="bright_green"))
    
def parse_args():
    parser = argparse.ArgumentParser(
        description="VideoSpeeder: Speed up silent sections in a video file."
    )
    parser.add_argument(
        "--input", "-i", required=True, help="Path to input video file."
    )
    parser.add_argument(
        "--output", "-o", required=True, help="Path to output video file."
    )
    parser.add_argument(
        "--threshold", "-t", type=float, default=-30.0,
        help="Silence threshold in dB (default: -30.0)."
    )
    parser.add_argument(
        "--duration", "-d", type=float, default=2,
        help="Minimum silence duration in seconds (default: 2)."
    )
    def _float_0_1(value):
        try:
            parsed = float(value)
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e))
        if parsed < 0.0 or parsed > 1.0:
            raise argparse.ArgumentTypeError("must be between 0.0 and 1.0")
        return parsed
    parser.add_argument(
        "--vad", action="store_true",
        help="Use Voice Activity Detection (Silero VAD) to detect speech vs non-speech (keyboard/mouse/noise)."
    )
    parser.add_argument(
        "--vad-threshold", type=_float_0_1, default=0.75,
        help="VAD speech probability threshold in [0.0, 1.0] (default: 0.75). Higher rejects more keyboard noise."
    )
    # --speed argument removed as speed is now dynamic
    parser.add_argument(
        "--indicator", action="store_true",
        help="Show '>>' indicator during sped-up segments."
    )
    parser.add_argument(
        "--gpu", action="store_true",
        help="Enable GPU acceleration for video encoding (NVIDIA NVENC, requires compatible GPU and drivers)."
    )
    parser.add_argument(
        "--gpu-decode", action="store_true",
        help="Enable GPU acceleration for video decoding (NVIDIA CUVID/NVDEC, experimental: requires compatible GPU, drivers, and FFmpeg build with h264_cuvid support)."
    )
    parser.add_argument(
        "--offset", type=float, default=0.0,
        help="Start time offset in seconds (default: 0.0)."
    )
    parser.add_argument(
        "--process-duration", type=float, default=None,
        help="Duration to process in seconds (default: entire file)."
    )
    parser.add_argument(
        "--debug-segments", action="store_true",
        help="Print computed segments with speed/output timing details (useful for diagnosing slow sections)."
    )
    return parser.parse_args()

def compute_silent_speed(segment_duration):
    target_duration = 4.0
    min_duration_for_variable_speed = 10.0
    fixed_speed_short = 4.0
    if segment_duration <= min_duration_for_variable_speed:
        return fixed_speed_short
    return max(1.0, segment_duration / target_duration)

def import_vad_dependencies():
    """
    Import VAD dependencies lazily (only when --vad is used) and provide actionable error messaging.
    """
    try:
        import torch  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "VAD mode requires additional dependencies.\n"
            "Install them with:\n"
            "  pip install -r /Users/jordanknight/github/videospeeder/videospeeder_project/requirements.txt\n"
            "Required packages: torch, torchaudio, silero-vad\n"
            "Note: PyTorch installs can be large."
        ) from e

    try:
        from silero_vad import load_silero_vad, get_speech_timestamps  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "VAD mode requires the 'silero-vad' package.\n"
            "Install dependencies with:\n"
            "  pip install -r /Users/jordanknight/github/videospeeder/videospeeder_project/requirements.txt"
        ) from e

    return torch, load_silero_vad, get_speech_timestamps

def get_video_duration(input_file):
    """
    Uses ffprobe to get the duration of the input video in seconds.
    """
    import subprocess
    import json
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        input_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])

def get_video_codec(input_file):
    """
    Uses ffprobe to get the codec name of the first video stream.
    Returns codec_name (e.g., 'h264', 'hevc', 'av1').
    """
    import subprocess
    import json
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "json",
        input_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    info = json.loads(result.stdout)
    if "streams" in info and len(info["streams"]) > 0:
        return info["streams"][0]["codec_name"]
    else:
        raise RuntimeError("No video stream found in input file.")

import subprocess

def run_silencedetect(input_file, threshold, duration, offset=0.0, process_duration=None):
    """
    Runs FFmpeg silencedetect filter and returns stderr output.
    Allows offset and process_duration to limit the region analyzed.
    """
    cmd = [
        "ffmpeg",
    ]
    if offset and offset > 0:
        cmd += ["-ss", str(offset)]
    if process_duration:
        cmd += ["-t", str(process_duration)]
    cmd += [
        "-i", input_file,
        "-af", f"silencedetect=noise={threshold}dB:d={duration}",
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stderr
    except subprocess.CalledProcessError as e:
        print("Error running FFmpeg silencedetect:", e)
        print("FFmpeg stderr output:")
        print(e.stderr)
        raise

import re

def parse_silencedetect_output(stderr):
    """
    Parses FFmpeg silencedetect output and returns a list of (start, end) tuples.
    """
    silence_starts = []
    silence_ends = []
    for line in stderr.splitlines():
        start_match = re.search(r"silence_start: (\d+(\.\d+)?)", line)
        end_match = re.search(r"silence_end: (\d+(\.\d+)?)", line)
        if start_match:
            silence_starts.append(float(start_match.group(1)))
        if end_match:
            silence_ends.append(float(end_match.group(1)))
    # Pair starts and ends
    intervals = []
    for i, start in enumerate(silence_starts):
        end = silence_ends[i] if i < len(silence_ends) else None
        intervals.append((start, end))
    return intervals

def extract_audio_pcm_s16le(input_file, offset=0.0, process_duration=None, sample_rate=16000):
    """
    Extract 16-bit mono PCM (s16le) audio via FFmpeg pipe for VAD processing.

    Returned audio is raw bytes (little-endian int16 samples).
    Timestamps produced by downstream processing are relative to the extracted region, starting at 0.
    """
    cmd = ["ffmpeg", "-hide_banner"]
    if offset and offset > 0:
        cmd += ["-ss", str(offset)]
    cmd += ["-i", input_file]
    if process_duration:
        cmd += ["-t", str(process_duration)]
    cmd += [
        "-map", "0:a:0",
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-f", "s16le",
        "-loglevel", "error",
        "pipe:1",
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    audio_bytes, stderr_bytes = proc.communicate()
    if proc.returncode != 0:
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        raise RuntimeError(f"FFmpeg audio extraction failed:\n{stderr_text}".rstrip())
    if not audio_bytes:
        raise RuntimeError(
            "FFmpeg returned no audio data. Input may have no audio stream (or audio is unsupported)."
        )
    return audio_bytes

def pcm_s16le_bytes_to_float_tensor(audio_bytes, torch):
    """
    Convert s16le PCM bytes into a 1D float32 torch tensor normalized to ~[-1.0, 1.0].
    """
    from array import array

    if not audio_bytes:
        raise ValueError("audio_bytes is empty")
    if len(audio_bytes) % 2 != 0:
        audio_bytes = audio_bytes[:-1]
    samples = array("h")
    samples.frombytes(audio_bytes)
    if len(samples) == 0:
        raise ValueError("no samples decoded from audio_bytes")
    return torch.tensor(samples, dtype=torch.float32) / 32768.0

def stream_audio_pcm_s16le_chunks(
    input_file,
    offset=0.0,
    process_duration=None,
    sample_rate=16000,
    chunk_seconds=30.0,
):
    """
    Stream s16le PCM audio from FFmpeg in fixed-size chunks to avoid loading the entire audio into memory.

    Yields: raw PCM bytes (little-endian int16), sized to approximately `chunk_seconds` per yield.
    """
    import threading

    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be > 0")

    chunk_samples = int(sample_rate * chunk_seconds)
    bytes_per_chunk = chunk_samples * 2

    cmd = ["ffmpeg", "-hide_banner"]
    if offset and offset > 0:
        cmd += ["-ss", str(offset)]
    cmd += ["-i", input_file]
    if process_duration:
        cmd += ["-t", str(process_duration)]
    cmd += [
        "-map", "0:a:0",
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-f", "s16le",
        "-loglevel", "error",
        "pipe:1",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=max(1024 * 1024, bytes_per_chunk * 2),
    )

    stderr_chunks = []

    def _drain_stderr():
        if proc.stderr is None:
            return
        while True:
            chunk = proc.stderr.read(1024 * 16)
            if not chunk:
                break
            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    if proc.stdout is None:
        proc.kill()
        stderr_thread.join(timeout=1)
        raise RuntimeError("Failed to open FFmpeg stdout for PCM streaming.")

    try:
        while True:
            data = proc.stdout.read(bytes_per_chunk)
            if not data:
                break
            yield data
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        proc.wait()
        stderr_thread.join(timeout=1)

    if proc.returncode != 0:
        stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        raise RuntimeError(f"FFmpeg audio streaming failed:\n{stderr_text}".rstrip())

def detect_speech_segments_silero(
    input_file,
    vad_threshold,
    offset=0.0,
    process_duration=None,
    sample_rate=16000,
    chunk_seconds=30.0,
    overlap_seconds=1.0,
    min_speech_duration_ms=200,
    min_silence_duration_ms=100,
    speech_pad_ms=50,
):
    """
    Detect speech segments in the input using Silero VAD.

    Returns list of (start_seconds, end_seconds) tuples, relative to the processed region starting at 0.
    """
    torch, load_silero_vad, get_speech_timestamps = import_vad_dependencies()

    if overlap_seconds < 0:
        raise ValueError("overlap_seconds must be >= 0")
    overlap_samples = int(overlap_seconds * sample_rate)
    overlap_bytes = overlap_samples * 2

    torch.set_num_threads(1)
    try:
        model = load_silero_vad()
    except Exception as e:
        raise RuntimeError(
            "Failed to load Silero VAD model. This may require network access on first run. "
            "See README for offline notes."
        ) from e

    all_segments = []
    time_offset_seconds = 0.0
    tail_bytes = b""
    carry_byte = b""

    for chunk_bytes in stream_audio_pcm_s16le_chunks(
        input_file,
        offset=offset,
        process_duration=process_duration,
        sample_rate=sample_rate,
        chunk_seconds=chunk_seconds,
    ):
        if carry_byte:
            chunk_bytes = carry_byte + chunk_bytes
            carry_byte = b""
        if len(chunk_bytes) % 2 != 0:
            carry_byte = chunk_bytes[-1:]
            chunk_bytes = chunk_bytes[:-1]

        combined = tail_bytes + chunk_bytes
        if len(combined) % 2 != 0:
            combined = combined[:-1]

        combined_seconds = (len(combined) / 2) / sample_rate
        tail_seconds = (len(tail_bytes) / 2) / sample_rate
        chunk_start_seconds = max(0.0, time_offset_seconds - tail_seconds)

        audio_tensor = pcm_s16le_bytes_to_float_tensor(combined, torch)
        speech_timestamps = get_speech_timestamps(
            audio_tensor,
            model,
            threshold=vad_threshold,
            sampling_rate=sample_rate,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            speech_pad_ms=speech_pad_ms,
            return_seconds=True,
        )

        for ts in speech_timestamps:
            start = float(ts["start"]) + chunk_start_seconds
            end = float(ts["end"]) + chunk_start_seconds
            all_segments.append((start, end))

        if overlap_bytes > 0:
            tail_bytes = combined[-overlap_bytes:] if len(combined) > overlap_bytes else combined
        else:
            tail_bytes = b""

        time_offset_seconds += (len(chunk_bytes) / 2) / sample_rate

    if carry_byte:
        # Unpaired last byte shouldn't happen, but avoid silent corruption.
        raise RuntimeError("PCM stream ended on an odd byte boundary.")

    return all_segments

def normalize_speech_segments(
    speech_segments,
    max_end,
    merge_gap_seconds=0.3,
    pad_seconds=0.05,
    merge_tolerance_seconds=0.1,
):
    """
    Merge, pad, and clamp speech segments to reduce fragmentation and avoid boundary clipping.
    """
    if max_end < 0:
        raise ValueError("max_end must be >= 0")

    cleaned = []
    for start, end in speech_segments:
        try:
            start_f = float(start)
            end_f = float(end)
        except (TypeError, ValueError):
            continue
        if end_f <= start_f:
            continue
        cleaned.append((start_f, end_f))

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: x[0])

    # Merge segments that overlap or are separated by a small gap.
    merged = [cleaned[0]]
    for start, end in cleaned[1:]:
        last_start, last_end = merged[-1]
        gap = start - last_end
        if gap <= merge_gap_seconds:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    # Pad and clamp.
    padded = []
    for start, end in merged:
        padded_start = max(0.0, start - pad_seconds)
        padded_end = min(max_end, end + pad_seconds)
        if padded_end > padded_start:
            padded.append((padded_start, padded_end))

    if not padded:
        return []

    # Merge again after padding to remove overlaps.
    padded.sort(key=lambda x: x[0])
    final = [padded[0]]
    for start, end in padded[1:]:
        last_start, last_end = final[-1]
        if start <= last_end + merge_tolerance_seconds:
            final[-1] = (last_start, max(last_end, end))
        else:
            final.append((start, end))

    return final

def speech_segments_to_silence_intervals(speech_segments, total_duration):
    """
    Convert speech segments into non-speech ("silence") intervals for the existing pipeline.

    - If no speech is detected: returns [(0, total_duration)] (all silence / all sped-up).
    - If speech covers entire duration: returns [] (no silence to speed up).
    """
    if total_duration < 0:
        raise ValueError("total_duration must be >= 0")

    if not speech_segments:
        return [(0.0, float(total_duration))]

    intervals = []
    prev_end = 0.0
    for start, end in speech_segments:
        if start > prev_end:
            intervals.append((prev_end, start))
        prev_end = max(prev_end, end)

    if prev_end < total_duration:
        intervals.append((prev_end, float(total_duration)))

    # If speech starts at 0 and runs through end, there will be no intervals (correct).
    return intervals

def validate_silence_intervals(silence_intervals, max_end):
    """
    Validate silence intervals are ordered, non-negative, and within [0, max_end].
    """
    prev_end = 0.0
    for idx, (start, end) in enumerate(silence_intervals):
        if start is None or end is None:
            raise ValueError(f"silence interval {idx} has open-ended bound (start={start}, end={end})")
        if start < 0 or end < 0:
            raise ValueError(f"silence interval {idx} is negative: ({start}, {end})")
        if end < start:
            raise ValueError(f"silence interval {idx} has end < start: ({start}, {end})")
        if start < prev_end:
            raise ValueError(f"silence interval {idx} overlaps or is unsorted: ({start}, {end})")
        if end > max_end + 1e-6:
            raise ValueError(f"silence interval {idx} exceeds max_end={max_end}: ({start}, {end})")
        prev_end = end

def calculate_segments(silence_intervals, video_duration, buffer_duration=1.0):
    """
    Given silence intervals and total duration, returns a list of segments:
    Each segment is (start, end, type) where type is 'silent' or 'non-silent'.
    Adds a buffer of normal speed (non-silent) before each non-silent segment.
    """
    segments = []
    prev_end = 0.0
    for start, end in silence_intervals:
        # Non-silent before this silence
        if start > prev_end:
            segments.append((prev_end, start, "non-silent"))
        # Silent segment
        if end is not None:
            segments.append((start, end, "silent"))
            prev_end = end
        else:
            # Open-ended silence (shouldn't happen, but handle gracefully)
            segments.append((start, video_duration, "silent"))
            prev_end = video_duration
    # Any remaining non-silent at the end
    if prev_end < video_duration:
        segments.append((prev_end, video_duration, "non-silent"))

    # Post-process to add buffer before each non-silent segment
    adjusted_segments = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if seg[2] == "silent" and i + 1 < len(segments) and segments[i + 1][2] == "non-silent":
            silent_start, silent_end, _ = seg
            next_non_silent_start, next_non_silent_end, _ = segments[i + 1]
            # Only adjust if silent segment is longer than buffer
            if silent_end - silent_start > buffer_duration:
                # Shorten silent segment
                new_silent_end = max(silent_start, silent_end - buffer_duration)
                adjusted_segments.append((silent_start, new_silent_end, "silent"))
                # Insert buffer as non-silent
                buffer_start = new_silent_end
                buffer_end = silent_end
                adjusted_segments.append((buffer_start, buffer_end, "non-silent"))
                # Adjust next non-silent segment to start after buffer
                segments[i + 1] = (buffer_end, next_non_silent_end, "non-silent")
            else:
                # If silent segment is too short, treat as non-silent
                adjusted_segments.append((silent_start, silent_end, "non-silent"))
            i += 1
        else:
            adjusted_segments.append(seg)
            i += 1
    return adjusted_segments

def build_filtergraph(segments, indicator, use_gpu_decode=False, png_input_index=1, png_path="fastforward.png"):
    """
    Builds a dynamic FFmpeg filtergraph string for the given segments.
    - segments: list of (start, end, type)
    - indicator: bool, whether to add fastforward overlay during sped-up segments
    - use_gpu_decode: bool, whether GPU decode is active (insert hwdownload/format if True)
    - png_input_index: index of the PNG input in FFmpeg (default 1, i.e., [1:v])
    - png_path: path to the PNG file
    Returns: filtergraph string
    """
    MAX_VIDEO_SPEED = 1000.0 # Cap for setpts
    MAX_ATEMPO = 2.0         # FFmpeg atempo max per filter
    vf_parts = []
    af_parts = []
    concat_v = []
    concat_a = []
    seg_idx = 0

    for start, end, typ in segments:
        v_label = f"v{seg_idx}"
        a_label = f"a{seg_idx}"

        # --- Audio part ---
        af = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS"
        if typ == "silent":
            segment_duration = end - start
            audio_speed = compute_silent_speed(segment_duration)
            remain = audio_speed
            atempo_chain = []
            while remain > MAX_ATEMPO:
                atempo_chain.append(f"atempo={MAX_ATEMPO}")
                remain /= MAX_ATEMPO
            if remain > 1.001:
                final_atempo = min(remain, MAX_ATEMPO)
                if final_atempo > 1.001:
                    atempo_chain.append(f"atempo={final_atempo:.2f}")
            if atempo_chain:
                af += "," + ",".join(atempo_chain)
            # Keep A/V durations aligned (still apply atempo), but mute audio during sped-up segments.
            af += ",volume=0"
        af += f"[{a_label}]"
        af_parts.append(af)

        # --- Video part ---
        vf_segment_chain = "" # Build the chain for this segment as a string
        last_video_label = "[0:v]" # Start with the main video input

        # 1. Trim and initial setpts
        trim_label = f"trim{seg_idx}"
        vf_segment_chain += f"{last_video_label}trim=start={start}:end={end},setpts=PTS-STARTPTS[{trim_label}]"
        last_video_label = trim_label

        # 2. Optional GPU download
        if use_gpu_decode:
            gpu_label = f"gpu{seg_idx}"
            vf_segment_chain += f";[{last_video_label}]hwdownload,format=yuv420p[{gpu_label}]"
            last_video_label = gpu_label

        # 3. If silent, apply indicator and then speedup
        if typ == "silent":
            # Recalculate speed (needed for video_speed and text)
            segment_duration = end - start
            target_duration = 4.0
            min_duration_for_variable_speed = 10.0
            fixed_speed_short = 4.0
            if segment_duration <= min_duration_for_variable_speed:
                current_speed = fixed_speed_short
            else:
                current_speed = max(1.0, segment_duration / target_duration)
            video_speed = min(current_speed, MAX_VIDEO_SPEED)

            # 3a. Apply indicator if requested (MOVED: now happens BEFORE speed change)
            if indicator:
                box_label = f"box{seg_idx}"
                overlay_label = f"ovl{seg_idx}"
                text_label = f"txt{seg_idx}"
                # Draw a semi-transparent black box first
                # Position everything top-left
                # y=10: Position box 10px from top edge
                vf_segment_chain += f";[{last_video_label}]drawbox=x=10:y=10:w=400:h=220:color=black@0.5:t=fill[{box_label}]"
                last_video_label = box_label # Output of drawbox is input for overlay
                
                # Chain overlay filter (takes 2 inputs: box stream and png input)
                # Place overlay in top-left, on top of the box
                vf_segment_chain += f";[{last_video_label}][{png_input_index}:v]overlay=x=10:y=10[{overlay_label}]"
                last_video_label = overlay_label # Output of overlay is input for drawtext
                
                # Chain drawtext filter, place text right of icon, aligned near top, on top of the box
                # x=10+w+10: Position text 10px right of the overlay icon (icon starts at x=10, width is 'w')
                # y=10: Align text baseline near top
                # Move text further right and down for better separation from icon
                vf_segment_chain += f";[{last_video_label}]drawtext=text='{int(current_speed)}x':x=260:y=100:fontsize=60:fontcolor=white:borderw=4[{text_label}]"
                last_video_label = text_label # Output of drawtext is input for speed change
            
            # 3b. Apply speed change (setpts) AFTER overlays
            spedup_label = f"spedup{seg_idx}"
            vf_segment_chain += f";[{last_video_label}]setpts=PTS/{video_speed}[{v_label}]"
            last_video_label = v_label # Final label is v_label
        else:
            # If not silent, alias last_video_label to v_label
            vf_segment_chain += f";[{last_video_label}]null[{v_label}]"
            last_video_label = v_label

        # Append the completed chain for this segment
        vf_parts.append(vf_segment_chain)

        # Add segment labels for final concat
        concat_v.append(f"[{v_label}]")
        concat_a.append(f"[{a_label}]")
        seg_idx += 1

    # --- Final filtergraph assembly ---
    n = len(segments)
    # Join all segment filter chains first
    filtergraph = ";".join(vf_parts + af_parts)
    # Then add the final concatenation filters
    filtergraph += f";{''.join(concat_v)}concat=n={n}:v=1:a=0[vout]" # Concat video
    filtergraph += f";{''.join(concat_a)}concat=n={n}:v=0:a=1[aout]" # Concat audio
    return filtergraph

def run_ffmpeg_processing(input_file, output_file, filtergraph, video_duration, codec_name, use_gpu=False, offset=0.0, process_duration=None, png_path="fastforward.png"):
    """
    Runs the main FFmpeg processing command with the given filtergraph and shows a tqdm progress bar.
    Selects hardware/software encoder/decoder based on codec_name and use_gpu.
    Allows offset and process_duration to limit the region processed.
    """
    import subprocess
    import re

    # Map codec to decoder/encoder
    codec_map = {
        "h264": {
            "gpu_decoder": ["-hwaccel", "cuvid", "-c:v", "h264_cuvid"],
            "gpu_encoder": "h264_nvenc",
            "cpu_encoder": "libx264"
        },
        "hevc": {
            "gpu_decoder": ["-hwaccel", "cuvid", "-c:v", "hevc_cuvid"],
            "gpu_encoder": "hevc_nvenc",
            "cpu_encoder": "libx265"
        },
        "h265": {
            "gpu_decoder": ["-hwaccel", "cuvid", "-c:v", "hevc_cuvid"],
            "gpu_encoder": "hevc_nvenc",
            "cpu_encoder": "libx265"
        },
        "av1": {
            "gpu_decoder": ["-hwaccel", "cuvid", "-c:v", "av1_cuvid"],
            "gpu_encoder": "av1_nvenc",
            "cpu_encoder": "libaom-av1"
        }
    }

    codec_key = codec_name.lower()
    if codec_key not in codec_map:
        print(f"Warning: Unrecognized codec '{codec_name}'. Defaulting to software x264.")
        vcodec = "libx264"
        decoder_args = []
    else:
        entry = codec_map[codec_key]
        vcodec = entry["gpu_encoder"] if use_gpu else entry["cpu_encoder"]
        decoder_args = entry["gpu_decoder"] if use_gpu and getattr(run_ffmpeg_processing, "use_gpu_decode", False) else []

    print(f"Detected input codec: {codec_name}")
    print(f"Selected encoder: {vcodec}")
    if decoder_args:
        print(f"Selected decoder args: {' '.join(decoder_args)}")

    cmd = ["ffmpeg", "-y"]
    cmd += decoder_args
    if offset and offset > 0:
        cmd += ["-ss", str(offset)]
    if process_duration:
        cmd += ["-t", str(process_duration)]
    cmd += [
        "-i", input_file,
        "-i", png_path,  # Add PNG as second input
        "-filter_complex", filtergraph,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", vcodec,
        "-crf", "23" if not use_gpu else "18",
        "-c:a", "aac",
        "-b:a", "128k",
        "-progress", "pipe:1",
        "-nostats",
        output_file
    ]
    print("Running FFmpeg processing command:")
    print(" ".join(cmd))
    try:
        progress_segments = getattr(run_ffmpeg_processing, "progress_segments", None)
        progress_map = None
        progress_map_index = 0
        if progress_segments:
            out_cursor = 0.0
            progress_map = []
            for seg_start, seg_end, seg_type in progress_segments:
                seg_start = float(seg_start)
                seg_end = float(seg_end)
                in_duration = max(0.0, seg_end - seg_start)
                speed = 1.0
                if seg_type == "silent":
                    speed = compute_silent_speed(in_duration)
                out_duration = 0.0 if speed <= 0 else in_duration / speed
                progress_map.append(
                    {
                        "out_start": out_cursor,
                        "out_end": out_cursor + out_duration,
                        "in_start": seg_start,
                        "in_end": seg_end,
                        "speed": speed,
                    }
                )
                out_cursor += out_duration

        def map_out_time_to_input_time(out_time_seconds):
            nonlocal progress_map_index
            if not progress_map:
                return out_time_seconds
            while (
                progress_map_index < len(progress_map)
                and out_time_seconds > progress_map[progress_map_index]["out_end"] + 1e-6
            ):
                progress_map_index += 1
            if progress_map_index >= len(progress_map):
                return video_duration
            seg = progress_map[progress_map_index]
            rel_out = max(0.0, min(out_time_seconds - seg["out_start"], seg["out_end"] - seg["out_start"]))
            return min(video_duration, seg["in_start"] + rel_out * seg["speed"])

        if tqdm is None:
            print("[warn] tqdm is not installed; running without progress bar.")
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
            )
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                if line.startswith("out_time_ms=") or line.startswith("out_time="):
                    print(line.strip())
            proc.wait()
        else:
            with tqdm(total=video_duration, unit="s", desc="Processing", dynamic_ncols=True) as pbar:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
                )
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    if line.startswith("out_time_ms="):
                        try:
                            value = line.strip().split("=")[1]
                            if value != "N/A":
                                ms = int(value)
                                seconds = ms / 1_000_000
                                input_seconds = map_out_time_to_input_time(seconds)
                                pbar.n = min(input_seconds, video_duration)
                                pbar.refresh()
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith("out_time="):
                        try:
                            t = line.strip().split("=")[1]
                            if t != "N/A":
                                h, m, s = t.split(":")
                                seconds = int(h) * 3600 + int(m) * 60 + float(s)
                                input_seconds = map_out_time_to_input_time(seconds)
                                pbar.n = min(input_seconds, video_duration)
                                pbar.refresh()
                        except (ValueError, IndexError):
                            pass

                proc.wait()
                pbar.n = video_duration
                pbar.refresh()

        if proc.returncode == 0:
            print("FFmpeg processing completed successfully.")
        else:
            print("Error running FFmpeg processing. See FFmpeg output above.")
            print(proc.stderr.read())
            raise subprocess.CalledProcessError(proc.returncode, cmd)
    except Exception as e:
        print("Error during FFmpeg processing:", e)
        raise

def main():
    args = parse_args()
    print("Arguments parsed:")
    for k, v in vars(args).items():
        print(f"  {k}: {v}")

    # Debug: Show current working directory and file list
    print(f"[DEBUG] Current working directory: {os.getcwd()}")
    print(f"[DEBUG] Files in cwd: {os.listdir(os.getcwd())}")

    # If indicator or any software filter is used, disable GPU decode (hardware decode)
    if args.indicator or True:  # Always True for now, as filtergraph always uses software filters
        print("[info] Disabling GPU decode due to software filters in filtergraph.")
        args.gpu_decode = False

    # Probe and print video stats before any processing
    print(f"[DEBUG] Probing input file: {args.input}")
    probe_and_print_video_stats(args.input)

    png_path = os.path.join(os.path.dirname(__file__), "fastforward.png")

    # Error handling: Check for ffmpeg and ffprobe
    if shutil.which("ffmpeg") is None:
        print("[DEBUG] ffmpeg not found in PATH.")
        print("Error: ffmpeg is not installed or not in PATH.")
        sys.exit(1)
    if shutil.which("ffprobe") is None:
        print("[DEBUG] ffprobe not found in PATH.")
        print("Error: ffprobe is not installed or not in PATH.")
        sys.exit(1)
    # Check input file exists
    if not os.path.isfile(args.input):
        print(f"[DEBUG] Input file existence check failed: {args.input}")
        print(f"Error: Input file '{args.input}' does not exist.")
        sys.exit(1)
    else:
        print(f"[DEBUG] Input file exists: {args.input}")

    try:
        # Determine processing duration.
        # If process_duration is set, use it; otherwise, use the full video duration minus offset.
        if args.process_duration:
            video_duration = args.process_duration
        else:
            full_duration = get_video_duration(args.input)
            video_duration = max(0, full_duration - args.offset)
        print(f"Processing duration: {video_duration:.2f} seconds (offset: {args.offset})")

        if args.vad:
            print(f"\nUsing VAD (Silero) threshold={args.vad_threshold}")
            try:
                speech_segments_raw = detect_speech_segments_silero(
                    args.input,
                    vad_threshold=args.vad_threshold,
                    offset=args.offset,
                    process_duration=args.process_duration,
                )
            except RuntimeError as e:
                print(str(e), file=sys.stderr)
                sys.exit(1)
            speech_segments = normalize_speech_segments(
                speech_segments_raw,
                max_end=video_duration,
            )
            silence_intervals = speech_segments_to_silence_intervals(
                speech_segments, total_duration=video_duration
            )
            try:
                validate_silence_intervals(silence_intervals, max_end=video_duration)
            except ValueError as e:
                print(f"Invalid VAD-derived silence intervals: {e}", file=sys.stderr)
                sys.exit(1)
            print("VAD-derived silence intervals (start, end):")
            for interval in silence_intervals:
                print(interval)
        else:
            # Task 2.1: Run silencedetect and print stderr
            print("\nRunning FFmpeg silencedetect...")
            silencedetect_stderr = run_silencedetect(
                args.input,
                args.threshold,
                args.duration,
                offset=args.offset,
                process_duration=args.process_duration,
            )
            print("FFmpeg silencedetect output:")
            print(silencedetect_stderr)

            # Task 2.2: Parse silencedetect output
            silence_intervals = parse_silencedetect_output(silencedetect_stderr)
            print("Parsed silence intervals (start, end):")
            for interval in silence_intervals:
                print(interval)

        # Silence intervals and segments are relative to the processed region (start at 0).
        segments = calculate_segments(silence_intervals, video_duration)
        print("Segments (start, end, type):")
        for seg in segments:
            print(seg)

        if args.debug_segments:
            print("\n[debug] Segment speed details (input_time -> output_time):")
            total_out = 0.0
            longest_silent = None
            for idx, (start, end, typ) in enumerate(segments):
                in_dur = max(0.0, end - start)
                speed = 1.0 if typ != "silent" else compute_silent_speed(in_dur)
                out_dur = 0.0 if speed <= 0 else in_dur / speed
                total_out += out_dur
                if typ == "silent":
                    if longest_silent is None or in_dur > longest_silent["in_dur"]:
                        longest_silent = {
                            "idx": idx,
                            "start": start,
                            "end": end,
                            "in_dur": in_dur,
                            "speed": speed,
                            "out_dur": out_dur,
                        }
                overlay = "on" if (args.indicator and typ == "silent") else "off"
                if typ == "silent" or in_dur >= 30.0:
                    print(
                        f"  seg#{idx:03d} {typ:10s} in=[{start:.2f},{end:.2f}] "
                        f"in_dur={in_dur:.2f}s speed={speed:.2f} out_dur={out_dur:.2f}s overlay={overlay}"
                    )
            print(f"[debug] Estimated output duration from segments: {total_out:.2f}s")
            if longest_silent:
                print(
                    "[debug] Longest silent segment:\n"
                    f"  seg#{longest_silent['idx']:03d} in=[{longest_silent['start']:.2f},{longest_silent['end']:.2f}] "
                    f"in_dur={longest_silent['in_dur']:.2f}s speed={longest_silent['speed']:.2f} "
                    f"out_dur={longest_silent['out_dur']:.2f}s"
                )

        # Set attribute for GPU decode (hacky, but avoids changing all function signatures)
        setattr(run_ffmpeg_processing, "use_gpu_decode", args.gpu_decode)
        # Progress mapping: let run_ffmpeg_processing estimate input-time progress even when output time is
        # compressed by setpts for sped-up segments.
        setattr(run_ffmpeg_processing, "progress_segments", segments)

        # Task 3.2: Build FFmpeg filtergraph
        filtergraph = build_filtergraph(
            segments,
            args.indicator,
            use_gpu_decode=getattr(run_ffmpeg_processing, "use_gpu_decode", False),
            png_input_index=1,
            png_path=png_path
        )
        print("Generated FFmpeg filtergraph:")
        print(filtergraph)

        # Task 3.3: Run main FFmpeg processing
        # Detect input codec
        codec_name = get_video_codec(args.input)
        print(f"Input video codec detected: {codec_name}")
        # Pass offset and process_duration to ffmpeg via -ss/-t
        run_ffmpeg_processing(
            args.input,
            args.output,
            filtergraph,
            video_duration,
            codec_name,
            use_gpu=args.gpu,
            offset=args.offset,
            process_duration=args.process_duration,
            png_path=png_path
        )
    except Exception as e:
        print(f"[DEBUG] Exception occurred in main(): {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
