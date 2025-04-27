import argparse
import os
import whisper
import whisper.utils

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio/video using OpenAI Whisper and save as VTT.")
    parser.add_argument("--input", "-i", required=True, help="Input audio/video file (e.g. input.mp4)")
    parser.add_argument("--output", "-o", required=True, help="Output VTT file (e.g. subs.vtt)")
    parser.add_argument("--model", "-m", default="large", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model size (default: large)")
    args = parser.parse_args()

    print(f"Loading Whisper model: {args.model}")
    model = whisper.load_model(args.model)

    print(f"Transcribing {args.input} ...")
    result = model.transcribe(
        args.input,
        task="transcribe",
        condition_on_previous_text=False,
        temperature=0.0,
        fp16=True
    )

    print(f"Saving VTT to {args.output}")
    output_dir = os.path.dirname(args.output) or "." # Use current dir if no path specified
    vtt_writer = whisper.utils.WriteVTT(output_dir)
    with open(args.output, "w", encoding="utf-8") as f:
        # The write_result method takes the full result dict and the file handle
        vtt_writer.write_result(result, file=f)

    print("Transcription complete.")

if __name__ == "__main__":
    main()