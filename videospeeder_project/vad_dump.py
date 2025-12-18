#!/usr/bin/env python3

import argparse
import json
import sys

import videospeeder


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dump Silero VAD speech/non-speech segments for a video (no rendering)."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input video file.")
    parser.add_argument(
        "--vad-threshold",
        type=float,
        default=0.75,
        help="Speech probability threshold in [0.0, 1.0] (default: 0.75).",
    )
    parser.add_argument(
        "--offset", type=float, default=0.0, help="Start time offset in seconds (default: 0.0)."
    )
    parser.add_argument(
        "--process-duration",
        type=float,
        default=None,
        help="Duration to analyze in seconds (default: entire file from offset).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write output to a file (default: stdout).",
    )
    parser.add_argument(
        "--at",
        type=float,
        default=None,
        help="If set, print the segment containing this timestamp (seconds) and neighbors.",
    )
    return parser.parse_args()


def _write(text, out_path):
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


def main():
    args = parse_args()
    if not (0.0 <= args.vad_threshold <= 1.0):
        print("Error: --vad-threshold must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(2)

    if args.process_duration is not None:
        video_duration = float(args.process_duration)
    else:
        full_duration = videospeeder.get_video_duration(args.input)
        video_duration = max(0.0, float(full_duration) - float(args.offset))

    speech_raw = videospeeder.detect_speech_segments_silero(
        args.input,
        vad_threshold=args.vad_threshold,
        offset=args.offset,
        process_duration=args.process_duration,
    )
    speech = videospeeder.normalize_speech_segments(speech_raw, max_end=video_duration)
    silence_intervals = videospeeder.speech_segments_to_silence_intervals(
        speech, total_duration=video_duration
    )
    try:
        videospeeder.validate_silence_intervals(silence_intervals, max_end=video_duration)
    except ValueError as e:
        print(f"Error: invalid silence intervals computed: {e}", file=sys.stderr)
        sys.exit(1)

    segments = videospeeder.calculate_segments(silence_intervals, video_duration)

    payload = {
        "input": args.input,
        "offset": args.offset,
        "process_duration": args.process_duration,
        "analyzed_duration": video_duration,
        "vad_threshold": args.vad_threshold,
        "speech_segments": [{"start": s, "end": e} for s, e in speech],
        "non_speech_intervals": [{"start": s, "end": e} for s, e in silence_intervals],
        "pipeline_segments": [{"start": s, "end": e, "type": t} for s, e, t in segments],
    }

    if args.at is not None:
        at = float(args.at)
        hit_idx = None
        for idx, seg in enumerate(payload["pipeline_segments"]):
            if seg["start"] <= at < seg["end"]:
                hit_idx = idx
                break
        payload["debug_at"] = {
            "at": at,
            "hit_index": hit_idx,
            "neighbors": (
                payload["pipeline_segments"][max(0, (hit_idx or 0) - 2) : (hit_idx or 0) + 3]
                if hit_idx is not None
                else []
            ),
        }

    if args.format == "json":
        _write(json.dumps(payload, indent=2) + "\n", args.out)
        return

    # text
    lines = []
    lines.append(f"input: {args.input}")
    lines.append(f"offset: {args.offset}")
    lines.append(f"process_duration: {args.process_duration}")
    lines.append(f"analyzed_duration: {video_duration}")
    lines.append(f"vad_threshold: {args.vad_threshold}")
    lines.append("")
    lines.append("speech_segments:")
    for seg in payload["speech_segments"]:
        lines.append(f"  - {seg['start']:.3f} -> {seg['end']:.3f}")
    lines.append("")
    lines.append("non_speech_intervals:")
    for seg in payload["non_speech_intervals"]:
        lines.append(f"  - {seg['start']:.3f} -> {seg['end']:.3f}")
    lines.append("")
    lines.append("pipeline_segments:")
    for seg in payload["pipeline_segments"]:
        lines.append(f"  - {seg['type']:10s} {seg['start']:.3f} -> {seg['end']:.3f}")
    _write("\n".join(lines) + "\n", args.out)


if __name__ == "__main__":
    main()

