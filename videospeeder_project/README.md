# VideoSpeeder

VideoSpeeder is a Python command-line tool that processes a video file, detects silent sections, speeds up those sections by a configurable factor, adds a visual indicator (">>") during sped-up parts, and outputs the modified video.

## Features

- Detects silent sections in video using FFmpeg's silencedetect.
- Speeds up silent sections by a user-defined factor.
- Adds a ">>" indicator during sped-up segments (optional).
- Provides a progress bar during processing.
- Fully configurable via command-line arguments.
- **Optional GPU acceleration** for video encoding (`--gpu`, NVIDIA NVENC) and **experimental GPU decoding** (`--gpu-decode`, NVIDIA CUVID/NVDEC, see below).

## Prerequisites

- Python 3.7+
- [FFmpeg](https://ffmpeg.org/) (must be installed and in your PATH)
- Python packages: `tqdm`
- For GPU acceleration: NVIDIA GPU with NVENC/NVDEC support and drivers
- For GPU decoding: FFmpeg build with `h264_cuvid` support (check with `ffmpeg -codecs | grep h264_cuvid`)

## Installation

1. Install FFmpeg (see [FFmpeg download page](https://ffmpeg.org/download.html)).
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```bash
python videospeeder.py --input INPUT.mp4 --output OUTPUT.mp4 [options]
```

### Options

- `--input`, `-i`: Path to input video file (required)
- `--output`, `-o`: Path to output video file (required)
- `--threshold`, `-t`: Silence threshold in dB (default: -30.0)
- `--duration`, `-d`: Minimum silence duration in seconds (default: 0.5)
- `--indicator`: Show ">>" indicator during sped-up segments (flag)
- `--gpu`: Enable GPU acceleration for video encoding (NVIDIA NVENC)
- `--gpu-decode`: Enable GPU acceleration for video decoding (NVIDIA CUVID/NVDEC, experimental)

### Example

```bash
python videospeeder.py -i input.mp4 -o output.mp4 -t -35 -d 0.7 --indicator --gpu --gpu-decode
```

## Makefile Usage

- `make install` — Install Python dependencies
- `make run ARGS="--input input.mp4 --output output.mp4 --gpu --gpu-decode"` — Run with custom arguments (add `--gpu` and/or `--gpu-decode`)
- `make test` — Run on the provided test file (`/mnt/c/Users/jorkni/Downloads/test speed upper.mp4`)
- `make test ARGS="--gpu --gpu-decode"` — Run test with GPU encoding and decoding
- `make clean` — Remove output video files

## Notes on GPU Decoding

- GPU decoding (`--gpu-decode`) is experimental and may not work with all FFmpeg builds or filter chains.
- Your FFmpeg must be built with `h264_cuvid` support.
- Some filters (e.g., drawtext, trim) may require frames to be downloaded to system memory, which can reduce performance benefits.
- If you encounter issues, try running without `--gpu-decode`.

## How it Works

1. Detects silent intervals in the input video using FFmpeg.
2. Calculates silent and non-silent segments, including a 2-second buffer of normal speed before non-silent sections that follow silence.
3. Builds a dynamic FFmpeg filtergraph to speed up silent segments and add indicators. The speedup logic is as follows:
    - **Short Silence (3-10 seconds):** Sped up by a fixed factor of **4x**.
    - **Long Silence (> 10 seconds):** Sped up dynamically. The speed factor is calculated to make the resulting segment approximately **4 seconds** long. This speedup is capped at a maximum of **1000x** for video (`setpts`) and uses chained `atempo` filters for audio to handle high speed factors.
4. Processes the video using the generated filtergraph and outputs the result, showing a progress bar.

## License

MIT License