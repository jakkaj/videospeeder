# VideoSpeeder task runner (https://github.com/casey/just)
#
# Override variables on the command line, e.g.:
#   just run-vad input=scratch/my.mp4 output=scratch/out.mp4

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

venv_dir := ".venv-vad"
script := "videospeeder_project/videospeeder.py"

# Default sample input/output (override as needed)
input ?= "scratch/output_5min.mp4"
out_baseline ?= "scratch/out-silencedetect-short.mp4"
out_vad ?= "scratch/out-vad-short.mp4"
out_vad_indicator ?= "scratch/out-vad-indicator-short.mp4"
process_duration ?= "5"

# Parallel-work sample (uses existing scratch asset)
parallel_input ?= "scratch/parallel-work-output.mp4"
parallel_trimmed ?= "scratch/parallel-work-output-trimmed.mp4"
parallel_vad_600 ?= "scratch/parallel-work-output-trimmed-vad-600s.mp4"
parallel_process_duration ?= "600"

default: help

help:
  @just --list
  @echo
  @echo "Samples:"
  @echo "  just baseline"
  @echo "  just venv"
  @echo "  just vad"
  @echo "  just vad-indicator"
  @echo "  just sample-parallel-vad"
  @echo
  @echo "Override example:"
  @echo "  just vad input=scratch/my.mp4 out_vad=scratch/my-vad.mp4 process_duration=10"

# Create a local venv and install runtime deps (network required).
venv:
  python -m venv "{{venv_dir}}"
  . "{{venv_dir}}/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install -r videospeeder_project/requirements.txt

# Run baseline silencedetect (no venv required, but tqdm/rich improve output).
baseline:
  python "{{script}}" -i "{{input}}" -o "{{out_baseline}}" --process-duration "{{process_duration}}"

# Run VAD mode (requires venv created by `just venv`).
vad:
  . "{{venv_dir}}/bin/activate"
  python "{{script}}" -i "{{input}}" -o "{{out_vad}}" --vad --process-duration "{{process_duration}}"

# Run VAD + overlay indicator (requires venv).
vad-indicator:
  . "{{venv_dir}}/bin/activate"
  python "{{script}}" -i "{{input}}" -o "{{out_vad_indicator}}" --vad --indicator --process-duration "{{process_duration}}"

# Clean sample outputs.
clean-samples:
  rm -f "{{out_baseline}}" "{{out_vad}}" "{{out_vad_indicator}}"

# Create a trimmed input by skipping the first quarter of the parallel-work sample.
trim-parallel-quarter:
  start="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "{{parallel_input}}" | awk '{print $1/4.0}')"
  ffmpeg -hide_banner -y -ss "${start}" -i "{{parallel_input}}" -c copy -movflags +faststart "{{parallel_trimmed}}"

# End-to-end sample: trim 1/4 off the front, then run VAD for a fixed window.
sample-parallel-vad: trim-parallel-quarter
  . "{{venv_dir}}/bin/activate"
  python "{{script}}" -i "{{parallel_trimmed}}" -o "{{parallel_vad_600}}" --vad --indicator --process-duration "{{parallel_process_duration}}"
