.PHONY: run install clean help test

# Default: show help
help:
	@echo "VideoSpeeder Makefile"
	@echo "Usage:"
	@echo "  make install        Install Python dependencies"
	@echo "  make run ARGS='...' Run videospeeder.py with arguments"
	@echo "  make test           Run videospeeder.py on the provided test file"
	@echo "  make clean          Remove output video files (*.mp4)"
	@echo "  make help           Show this help message"
	@echo "  make test-segment   Run videospeeder.py on a segment of the test file (with --offset and --process-duration)"
	@echo "  make transcribe INPUT=input.mp4 OUTPUT=subs.vtt [MODEL=large]   Transcribe input file to VTT using Whisper"
	@echo "  make transcript-segment      Transcribe output_test_segment.mp4 to output_test_segment.vtt using Whisper"

install:
	pip install -r requirements.txt

run:
	python videospeeder.py $(ARGS)

# To use GPU acceleration (NVIDIA NVENC), run: make test ARGS="--gpu"
test:
	python videospeeder.py --input "/mnt/c/Users/jorkni/Downloads/test speed upper.mp4" --output output_test.mp4 --indicator --gpu --gpu-decode

test-segment:
	python videospeeder.py --input "/mnt/c/Users/jorkni/OneDrive - Microsoft/Documents/ShareX/Screenshots/2025-04/msedge_oXFMOctKmD.mp4" --output output_test_segment.mp4 --indicator --gpu --gpu-decode

transcribe:
	python transcribe.py --input "$(INPUT)" --output "$(OUTPUT)" --model "$(MODEL)"

transcript-segment:
	$(MAKE) transcribe INPUT=output_test_segment.mp4 OUTPUT=output_test_segment.vtt MODEL=large

clean:
	rm -f *.mp4
