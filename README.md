# 🚀 VideoSpeeder: Turbocharge Your Video Editing! 🎬💨

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Tired of manually cutting out silent pauses in your videos? **VideoSpeeder** is here to revolutionize your workflow! ⚡️

This tool intelligently analyzes your video, detects silent segments, and automatically speeds them up, saving you precious editing time. Perfect for:

*   🎙️ **Podcasters & YouTubers:** Condense long recordings quickly.
*   👨‍🏫 **Educators & Presenters:** Make lectures more engaging.
*   💻 **Coders & Tutorial Makers:** Skip the thinking pauses in screen recordings.
*   ...anyone who wants faster, tighter videos!
[![VideoSpeeder in Action](media/videospeederinaction.png)](https://www.youtube.com/watch?v=XHBKlCnk-7k)

🎥 [Have a look at a video that uses it here](https://www.youtube.com/watch?v=XHBKlCnk-7k).

## ✨ Key Features

*   🤫 **Smart Silence Detection:** Uses `ffmpeg`'s powerful `silencedetect` filter to pinpoint moments without speech.
*   ⏩ **Dynamic Speed-Up:** Automatically calculates the optimal speed for silent parts, aiming for a concise ~4-second duration while capping at a blazing 1000x! Shorter silences get a fixed 4x boost.
*   📊 **Rich CLI Stats:** Get beautifully formatted video stats upfront using `rich`.
*   👁️ **Visual Speed Indicator:** Optional `>> [Speed]x` overlay shows exactly when the video is sped up.
*   💡 **Transcription Power:** Includes a separate script (`transcribe.py`) leveraging **OpenAI Whisper** for highly accurate VTT subtitle generation. Choose your model size!
*   ⚙️ **Fine-Tuned Control:** Adjust silence detection `threshold` (dB) and minimum `duration` (seconds).
*   ⏱️ **Segment Processing:** Process only specific parts of your video using `--offset` and `--process-duration`.
*   🚀 **GPU Acceleration:** Supports NVIDIA NVENC for encoding and CUVID/NVDEC for decoding (requires compatible hardware, drivers, and FFmpeg build) for significantly faster processing.
*   ⏳ **Progress Bar:** Keep track of the process with a `tqdm` progress bar.

## ✅ Requirements

*   **Python 3.x**
*   **FFmpeg & FFprobe:** Must be installed and accessible in your system's PATH.
*   **Python Packages:** Listed in `videospeeder_project/requirements.txt`. Install them via pip.
    ```bash
    pip install -r videospeeder_project/requirements.txt
    ```
*   **(Optional) NVIDIA GPU & Drivers:** For GPU acceleration features.
*   **(Optional) CUDA Toolkit:** Often needed for Whisper's GPU support during transcription.

## 🛠️ Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/jakkaj/videospeeder.git
    cd videospeeder
    ```
2.  **Install Python dependencies:**
    ```bash
    # Navigate into the project directory if you aren't already
    cd videospeeder_project
    pip install -r requirements.txt
    # Or use the Makefile shortcut from the project root
    # make install # (Run this from within videospeeder_project/)
    ```
    *(Note: The `make install` command in the Makefile assumes you are inside the `videospeeder_project` directory).*

## 🏃‍♀️ Usage

VideoSpeeder consists of two main scripts located in the `videospeeder_project` directory.

### 1. Speeding Up Videos (`videospeeder.py`)

Run this script from within the `videospeeder_project` directory.

```bash
python videospeeder.py --input <your_video.mp4> --output <output_video.mp4> [OPTIONS]
```

**Common Options:**

*   `-i, --input`: Path to your input video file (Required).
*   `-o, --output`: Path for the processed output video file (Required).
*   `-t, --threshold`: Silence threshold in dB (Default: -30.0). Lower values detect quieter sounds as silence.
*   `-d, --duration`: Minimum duration of silence in seconds to be sped up (Default: 2.0).
*   `--indicator`: Show the `>> [Speed]x` overlay during sped-up parts.
*   `--gpu`: Enable NVIDIA NVENC GPU *encoding*.
*   `--gpu-decode`: Enable NVIDIA CUVID/NVDEC GPU *decoding* (Experimental).
*   `--offset`: Start processing from this time (in seconds).
*   `--process-duration`: Process only this duration (in seconds) from the start (or offset).

**Example:**

```bash
# Process a video with default settings and add the speed indicator
python videospeeder.py -i my_recording.mp4 -o my_recording_fast.mp4 --indicator

# Process using GPU acceleration and a stricter silence threshold
python videospeeder.py -i lecture.mp4 -o lecture_fast.mp4 -t -40 --gpu --gpu-decode
```

### 2. Transcribing Videos/Audio (`transcribe.py`)

Run this script from within the `videospeeder_project` directory.

```bash
python transcribe.py --input <your_video_or_audio.mp4> --output <subtitles.vtt> [OPTIONS]
```

**Common Options:**

*   `-i, --input`: Path to your input video or audio file (Required).
*   `-o, --output`: Path for the output VTT subtitle file (Required).
*   `-m, --model`: Whisper model size (Choices: `tiny`, `base`, `small`, `medium`, `large`. Default: `large`). Larger models are more accurate but require more resources.

**Example:**

```bash
# Transcribe a video using the 'medium' Whisper model
python transcribe.py -i my_recording_fast.mp4 -o my_recording_subs.vtt -m medium
```

### Using the Makefile (Convenience)

The `Makefile` inside `videospeeder_project` provides shortcuts for common tasks (run from within `videospeeder_project` directory):

*   `make install`: Install dependencies.
*   `make test`: Run a test using a sample file path (edit the path in the Makefile first!) with GPU and indicator.
*   `make test-segment`: Run a test on a segment.
*   `make transcribe INPUT=video.mp4 OUTPUT=subs.vtt [MODEL=large]`: Transcribe a file.
*   `make transcript-segment`: Transcribe the output of `make test-segment`.
*   `make clean`: Remove generated `.mp4` files from the directory.
*   `make help`: Show available make commands.

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

## 🙌 Contributing

Found a bug or have an idea? Feel free to open an issue on the GitHub repository!

