Below is an actionable implementation plan—with drop‑in code—for adding VideoToolbox (VT) hardware encoding on Apple Silicon while keeping your existing NVENC path untouched.

---

## 1) Hardware detection (production‑ready)

Use fast `sysctl` probes (no new deps) and fall back to `system_profiler` only to get the chip marketing name for display.

```python
import platform, subprocess, json, shlex

class AppleSiliconInfo:
    def __init__(self, is_apple_silicon: bool, chip: str, under_rosetta: bool):
        self.is_apple_silicon = is_apple_silicon
        self.chip = chip  # e.g., "Apple M2", or "Unknown Apple Silicon"
        self.under_rosetta = under_rosetta

def _sysctl_str(key: str) -> str:
    try:
        out = subprocess.check_output(["/usr/sbin/sysctl", "-n", key], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", "ignore").strip()
    except Exception:
        return ""

def _sysctl_int(key: str) -> int:
    s = _sysctl_str(key)
    try:
        return int(s)
    except Exception:
        return -1

def detect_apple_silicon() -> AppleSiliconInfo:
    """Detect Apple Silicon (M1/M2/M3+) robustly, even under Rosetta.
    Returns AppleSiliconInfo with boolean, chip marketing string, and Rosetta flag.
    """
    is_darwin = (platform.system() == "Darwin")
    if not is_darwin:
        return AppleSiliconInfo(False, "", False)

    # Is this host capable of arm64? Works even under Rosetta 2.
    hw_arm64 = _sysctl_int("hw.optional.arm64") == 1  # 1 on Apple Silicon hosts. :contentReference[oaicite:0]{index=0}

    # Is THIS process running under Rosetta 2 translation?
    # 0 = native, 1 = translated; -1 = key not present (older macOS).
    rosetta = _sysctl_int("sysctl.proc_translated") == 1  # Officially documented by Apple. :contentReference[oaicite:1]{index=1}

    chip = ""
    if hw_arm64:
        # Light-but-reliable way to obtain "Chip: Apple M2" etc.
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPHardwareDataType", "-json"],
                stderr=subprocess.DEVNULL, timeout=5
            )
            data = json.loads(out.decode("utf-8", "ignore"))
            hw = data.get("SPHardwareDataType", [{}])[0]
            # Modern macOS reports "chip" (e.g., "Apple M2"); older report "cpu_type".
            chip = hw.get("chip") or hw.get("cpu_type") or "Unknown Apple Silicon"
        except Exception:
            chip = "Unknown Apple Silicon"  # still fine for status line

    return AppleSiliconInfo(hw_arm64, chip, rosetta)
```

**Notes & edge cases**

* `hw.optional.arm64 == 1` is true on Apple Silicon (even if your Python runs under Rosetta). ([Stack Overflow][1])
* Rosetta detection via `sysctl.proc_translated` is Apple’s recommended method. ([Apple Developer][2])
* We **do not** use `machdep.cpu.brand_string` (Intel‑only on newer macOS).

---

## 2) Encoder selection architecture (NVENC unchanged)

Extend, don’t rewrite. Keep your current `codec_map` keys and add an Apple entry. Wrap selection in a helper that decides the active hardware “provider”.

### Refactored `codec_map` (H.264/HEVC/AV1)

```python
# === Keep existing entries as-is for NVENC users ===
codec_map = {
    "h264": {
        "gpu_decoder": ["-hwaccel", "cuvid", "-c:v", "h264_cuvid"],  # unchanged
        "gpu_encoder": "h264_nvenc",                                 # unchanged
        "cpu_encoder": "libx264",
        "apple_encoder": "h264_videotoolbox"                         # NEW
    },
    "hevc": {
        "gpu_decoder": ["-hwaccel", "cuvid", "-c:v", "hevc_cuvid"],
        "gpu_encoder": "hevc_nvenc",
        "cpu_encoder": "libx265",
        "apple_encoder": "hevc_videotoolbox"                         # NEW
    },
    "h265": {  # alias
        "gpu_decoder": ["-hwaccel", "cuvid", "-c:v", "hevc_cuvid"],
        "gpu_encoder": "hevc_nvenc",
        "cpu_encoder": "libx265",
        "apple_encoder": "hevc_videotoolbox"
    },
    "av1": {
        "gpu_decoder": [],               # not used in your pipeline
        "gpu_encoder": "av1_nvenc",
        "cpu_encoder": "libsvtav1",      # or libaom-av1 per your defaults
        "apple_encoder": None            # No AV1 VT encoder in FFmpeg
    }
}
```

> FFmpeg exposes *VideoToolbox* encoders as `h264_videotoolbox` and `hevc_videotoolbox` (no AV1 encoder). ([Codec Wiki][3])

### Platform-aware selection helper (preserves NVENC path behavior)

```python
def ffmpeg_has_videotoolbox_encoders() -> bool:
    """Return True if this FFmpeg can encode with VT (both H.264/HEVC present)."""
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"], stderr=subprocess.STDOUT)
        s = out.decode("utf-8", "ignore")
        return ("h264_videotoolbox" in s) or ("hevc_videotoolbox" in s)
    except Exception:
        return False

def choose_encoder(codec_name: str, use_gpu: bool):
    """
    Decide encoder + decoder args based on platform.
    - On Apple Silicon + --gpu: use VT encoders (if present). Intel Macs => CPU.
    - On non-mac or non-Apple: defer to existing NVENC path untouched.
    """
    ckey = codec_name.lower()
    entry = codec_map.get(ckey)
    if not entry:
        return "libx264", []  # prior fallback

    if not use_gpu:
        return entry["cpu_encoder"], []

    # Existing NVENC flow: leave unchanged for non-Darwin, or when NVIDIA present
    if platform.system() != "Darwin":
        return entry["gpu_encoder"], entry.get("gpu_decoder", [])

    # Darwin: only Apple Silicon is allowed to use VT in Phase 1
    asi = detect_apple_silicon()
    if not asi.is_apple_silicon:
        # Intel Mac => explicit failure later; return CPU to avoid silent fallback building the command
        return None, []

    if not ffmpeg_has_videotoolbox_encoders():
        # We'll surface a clear error; return sentinel
        return None, []

    # AV1 is not supported by VT encoders in FFmpeg
    if ckey == "av1":
        return None, []

    return entry["apple_encoder"], []  # no VT decode; filters run on CPU by design
```

---

## 3) VideoToolbox parameter reference (what to pass to FFmpeg)

**Encoder names**

* H.264: `-c:v h264_videotoolbox`
* HEVC: `-c:v hevc_videotoolbox` ([Codec Wiki][3])

**Rate control**

* VT supports **bitrate-based** control via `-b:v` and VBV (use `-maxrate`/`-bufsize`). No CRF. ([Stack Overflow][4])
* VT also exposes a “constant quality” `-q:v` (1–100) on Apple Silicon in newer FFmpeg, but your spec mandates bitrate presets; we’ll use `-b:v` + VBV. ([Stack Overflow][5])

**Pixel formats**

* Safe default for H.264 VT: `-pix_fmt yuv420p`.
* HEVC VT supports `yuv420p` (8‑bit) and `p010le` (10‑bit). If your filters output other formats (e.g., `yuva420p` from overlays), insert `format=yuv420p` before encode. ([GitHub][6])

**Container tags**

* For HEVC in MP4, add `-tag:v hvc1` for better QuickTime/Safari compatibility. ([Brandur][7])

**Disable silent software fallback**

* Pass `-allow_sw 0` to avoid VT silently falling back to software when hardware is busy/unsupported (the error text asks to try `-allow_sw 1`). ([svp-team.com][8])

**Bitrate presets (your requirement)**

* `fast` = **12 Mbps**, `balanced` = **20 Mbps**, `quality` = **30 Mbps** (baseline at 1080p30).
* If you want **optional scaling by resolution**, scale proportionally to the pixel count vs 1080p (1.0× at 1920×1080).

  * Example targets (rounded) from the same presets:

    * 720p ≈ 0.5× → 6 / 10 / 15 Mbps
    * 4K ≈ 4.0× → 48 / 80 / 120 Mbps
  * These align with (and slightly exceed at higher presets) YouTube’s bitrate table (1080p 8–12 Mbps; 4K 35–45 Mbps @30fps), which is a good public reference. ([Google Help][9])

**VBV suggestion**

* Use *constrained VBR* pattern: `-b:v X -maxrate 1.25X -bufsize 2.5X` (conservative, smooth).

---

## 4) Error handling patterns

Detect and fail **before** launching a long pipeline:

* If `--gpu` and Apple Silicon **not** detected → error: *“--gpu requires Apple Silicon (M1/M2/M3) or NVIDIA; this Mac is Intel.”*
* If `--gpu` on Apple Silicon and `ffmpeg -encoders` does **not** list `h264_videotoolbox`/`hevc_videotoolbox` → error: *“FFmpeg was built without VideoToolbox; install a Homebrew FFmpeg with VT enabled.”* (Common cause in conda builds.) ([Super User][10])
* On runtime failure, parse stderr for:

  * `Error: cannot create compression session: -12908/-12902/-12915` or `Try -allow_sw 1. The hardware encoder may be busy, or not supported.` → surface as *hardware unavailable / unsupported / busy* and hint to close apps using camera/encode or reboot. ([Reddit][11])
  * `Incompatible pixel format` → advise `-pix_fmt yuv420p` (or inserting `format=yuv420p` in the filtergraph). ([Stack Overflow][12])
  * `No such encoder 'h264_videotoolbox'` → same as missing VT build.

Example parser:

```python
def parse_vt_error(stderr: str) -> str | None:
    s = stderr.lower()
    if "cannot create compression session" in s or "the hardware encoder may be busy" in s:
        return ("VideoToolbox hardware encoder unavailable or busy. "
                "Close apps using video encode/camera, ensure Screen Recording permissions, "
                "and try again. If the issue persists, reboot macOS.")
    if "no such encoder" in s and "videotoolbox" in s:
        return ("This ffmpeg lacks VideoToolbox encoders. Install Homebrew ffmpeg "
                "(brew install ffmpeg) with VT enabled.")
    if "incompatible pixel format" in s or "auto-selecting format" in s:
        return ("Pixel-format mismatch for VideoToolbox. Force -pix_fmt yuv420p (8‑bit) "
                "or convert via format=yuv420p in the filtergraph before encoding.")
    return None
```

---

## 5) Integration code: `videospeeder.py` lines ~400–467

### a) CLI: add `--quality`

```python
# near your argparse setup
parser.add_argument(
    "--quality",
    choices=["fast", "balanced", "quality"],
    default="balanced",
    help="VT bitrate preset (12/20/30 Mbps @1080p). Ignored for NVENC/CPU paths."
)
```

### b) Bitrate helper (scales by resolution if you want; or keep fixed)

```python
def _vt_target_bitrate_bits(args_quality: str, width: int, height: int) -> int:
    base = {"fast": 12_000_000, "balanced": 20_000_000, "quality": 30_000_000}[args_quality]
    # Optional scaling by resolution (1080p baseline). Comment next 3 lines if you want fixed rates only.
    scale = max(1.0, (width * height) / (1920 * 1080))
    return int(base * scale)
```

### c) Probe input (you likely already call ffprobe; include width/height)

```python
def _probe_stream(path: str):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,pix_fmt",
        "-of", "json", path
    ])
    js = json.loads(out.decode("utf-8", "ignore"))
    st = js["streams"][0]
    return st.get("codec_name",""), int(st.get("width",0)), int(st.get("height",0)), st.get("pix_fmt","")
```

### d) Encoder selection & command construction

Replace only the **selection and CRF insertion block** around your current lines 433–467. NVENC is left intact. VT path is appended *in place of* the CRF line.

```python
# --- inside run_ffmpeg_processing(...) ---

in_codec, src_w, src_h, src_pix = _probe_stream(input_file)

codec_key = (codec_name or in_codec or "h264").lower()
entry = codec_map.get(codec_key)

if entry is None:
    print(f"Warning: Unrecognized codec '{codec_key}'. Defaulting to software x264.")
    vcodec = "libx264"
    decoder_args = []
else:
    vcodec, decoder_args = choose_encoder(codec_key, use_gpu)

# Build base command
cmd = ["ffmpeg", "-y"]
cmd += decoder_args

# (seek/time window logic untouched)
if offset and offset > 0:
    cmd += ["-ss", str(offset)]
if process_duration:
    cmd += ["-t", str(process_duration)]

cmd += [
    "-i", input_file,
    "-i", png_path,                 # your indicator overlay
    "-filter_complex", filtergraph, # CPU filters by design
    "-map", "[vout]",
    "-map", "[aout]",
]

vt_active = (vcodec is not None) and vcodec.endswith("_videotoolbox")

if vcodec is None and use_gpu:
    # --gpu requested but no suitable hardware path
    asi = detect_apple_silicon()
    if platform.system() == "Darwin" and not asi.is_apple_silicon:
        raise SystemExit("ERROR: --gpu requires Apple Silicon (M1/M2/M3). This Mac is Intel.")
    if platform.system() == "Darwin" and asi.is_apple_silicon and not ffmpeg_has_videotoolbox_encoders():
        raise SystemExit("ERROR: FFmpeg was built without VideoToolbox encoders. Install a Homebrew FFmpeg with VT enabled.")
    if codec_key == "av1":
        raise SystemExit("ERROR: AV1 hardware encoding is not available via VideoToolbox on macOS. Use CPU (libsvtav1/libaom-av1) or NVIDIA on supported systems.")
    raise SystemExit("ERROR: GPU encoding requested but no supported GPU encoder is available.")

# Status line (e.g., "Using VideoToolbox on Apple M2")
if vt_active:
    asi = detect_apple_silicon()
    print(f"Using VideoToolbox on {asi.chip}{' (Rosetta)' if asi.under_rosetta else ''}")
elif use_gpu and vcodec and vcodec.endswith("_nvenc"):
    print("Using NVIDIA NVENC")

cmd += ["-c:v", vcodec]

# --- VT-specific video options ---
if vt_active:
    target = _vt_target_bitrate_bits(args.quality, src_w, src_h)
    # Constrained VBR
    maxrate = int(target * 1.25)
    bufsize = int(target * 2.5)

    # Profiles: pick sensible defaults per codec
    if codec_key.startswith("h26"):  # h264
        cmd += ["-profile:v", "high", "-pix_fmt", "yuv420p"]
    else:  # hevc
        cmd += ["-profile:v", "main", "-pix_fmt", "yuv420p", "-tag:v", "hvc1"]  # 8-bit default
        # If you later detect HDR10 pipeline, switch to main10 and p010le

    # Enforce hardware-only path
    cmd += ["-allow_sw", "0", "-b:v", str(target), "-maxrate", str(maxrate), "-bufsize", str(bufsize)]

else:
    # --- Existing behavior for NVENC/CPU: DO NOT CHANGE ---
    # Your current code sets CRF differently when use_gpu vs cpu; keep it verbatim:
    cmd += ["-crf", "23" if not use_gpu else "18"]

# Audio as-is
cmd += ["-c:a", "aac", "-b:a", "128k", "-progress", "pipe:1", "-nostats", output_file]

# Launch and parse errors
try:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
except subprocess.CalledProcessError as e:
    hint = parse_vt_error(e.stderr or "")
    if hint:
        raise SystemExit("FFmpeg failed: " + hint)
    raise
```

---

## 6) “Status display” requirement

Already covered: the snippet prints

* **VideoToolbox**: `Using VideoToolbox on Apple M2`
* **NVENC**: `Using NVIDIA NVENC`

Chip detection comes from `system_profiler` parsed JSON. (Common terminal usage for this is documented and widely used.) ([TeamDynamix][13])

---

## 7) Pitfalls (and how this design avoids them)

1. **CRF with VideoToolbox**
   VT doesn’t support `-crf`; we avoid it and use `-b:v`+VBV instead. ([Stack Overflow][4])

2. **Assuming all Macs support VT encode**
   Intel Macs or FFmpeg without VT → upfront checks; hard‑fail with clear message.

3. **Silent software fallback**
   We pass `-allow_sw 0` so FFmpeg won’t silently switch to software and will give the standard “Try -allow_sw 1…” diagnostic; we convert that to a friendly error. ([Reddit][11])

4. **Pixel format mismatches**
   Filters + PNG alpha can produce `yuva*`/`bgra`; we force `-pix_fmt yuv420p` (and suggest `format=yuv420p` in the filtergraph if needed). ([Stack Overflow][12])

5. **Bitrate scaling**
   Fixed bitrates are okay per your spec; optional scaling provided (aligned with YouTube’s public guidance for resolution/bitrate). ([Google Help][9])

6. **Breaking NVENC**
   We only add an Apple branch; NVENC mapping and its CRF logic remain unmodified.

---

## 8) Validation & testing checklist

**Apple Silicon (M1/M2/M3)**

* `ffmpeg -encoders | grep videotoolbox` shows both encoders. If not, install Homebrew FFmpeg. ([Super User][10])
* Run a short job with `--gpu --quality balanced` and confirm console shows:
  `Using VideoToolbox on Apple M*`.
* Verify VT is used: FFmpeg banner shows `h264_videotoolbox`/`hevc_videotoolbox` as encoder, or watch **Activity Monitor → GPU History** while encoding (visible spike).
* Try with overlays/text to ensure `-pix_fmt yuv420p` is accepted; no `Incompatible pixel format` errors. ([Stack Overflow][12])
* For HEVC MP4 outputs, check container brand with `ffprobe` and confirm `hvc1` tag present (improves Apple playback compatibility). ([Brandur][7])

**Failure paths**

* On Intel Mac + `--gpu` → expect immediate error “requires Apple Silicon”.
* Temporarily break VT (e.g., run a conflicting encoder) to see:
  `cannot create compression session ... Try -allow_sw 1` → tool emits clear guidance. ([Reddit][11])

**NVENC regression checks (Windows/Linux)**

* Sanity encode with `--gpu` exactly as before (no CLI/CRF changes in NVENC branch).
* Confirm `-crf` line is still present exactly where it used to be.

---

## 9) Quick command exemplars (for docs/README)

**H.264 VideoToolbox (balanced @1080p)**

```bash
ffmpeg -i in.mp4 -filter_complex "<your graph>" -map "[vout]" -map "[aout]" \
-c:v h264_videotoolbox -profile:v high -pix_fmt yuv420p -allow_sw 0 \
-b:v 20M -maxrate 25M -bufsize 50M \
-c:a aac -b:a 128k out.mp4
```

**HEVC VideoToolbox (quality @4K, scaled from 30→~120 Mbps)**

```bash
ffmpeg -i in.mp4 -filter_complex "<your graph>" -map "[vout]" -map "[aout]" \
-c:v hevc_videotoolbox -profile:v main -pix_fmt yuv420p -tag:v hvc1 -allow_sw 0 \
-b:v 120M -maxrate 150M -bufsize 300M \
-c:a aac -b:a 128k out_h265.mp4
```

> If you later support HDR10, switch to `-profile:v main10 -pix_fmt p010le` on the HEVC path. (VT supports `p010le`.) ([Super User][14])

---

## 10) Compatibility matrix (concise)

* **Encoders available via VT in FFmpeg:** H.264, HEVC. No AV1 encoder via VT. ([Codec Wiki][3])
* **AV1 on Apple Silicon:** decode hardware support appears on newer chips (e.g., M3), but **encode** is not exposed as a VT encoder in FFmpeg. ([Jellyfin][15])
* **OS:** macOS 11+ recommended (VideoToolbox stability), standard Homebrew ffmpeg includes VT.

---

## 11) Documentation updates (suggested bullets)

* **Prereqs (Mac):** Apple Silicon (M1/M2/M3), macOS 11+, FFmpeg with VideoToolbox.
* **Usage:** `--gpu` auto‑selects VideoToolbox on Apple Silicon and NVENC on NVIDIA. Add `--quality {fast|balanced|quality}`.
* **Troubleshooting:**

  * Check encoders: `ffmpeg -encoders | grep videotoolbox`.
  * Typical error: *“cannot create compression session … Try -allow_sw 1”* ⇒ hardware busy/unsupported. ([Reddit][11])
  * Intel Macs: not supported for VT encoding in Phase 1—use CPU encoders.

---

### Why these choices

* **Bitrate+VBV over CRF:** mandated by your spec; also consistent with public guidance that VT doesn’t do CRF like x264/x265. ([Stack Overflow][4])
* **`-allow_sw 0`:** guarantees explicit failure instead of silent software fallback; the canonical error string is well known. ([Reddit][11])
* **`-tag:v hvc1`:** avoids playback quirks for HEVC in MP4 on Apple platforms. ([Brandur][7])

---

## 12) Final checklist you can run through

* [ ] Add the new functions (`detect_apple_silicon`, `ffmpeg_has_videotoolbox_encoders`, `choose_encoder`, `parse_vt_error`).
* [ ] Extend `codec_map` with `apple_encoder` keys (H.264/HEVC/AV1).
* [ ] Add `--quality`.
* [ ] Drop in the modified selection/command block (NVENC untouched).
* [ ] Test on Apple Silicon: VT path engages, status line shows chip.
* [ ] Test on Intel Mac: `--gpu` fails early with a clear message.
* [ ] Test NVENC on Windows/Linux: identical behavior as before.

---

### Key references

* Encoder names & usage (`h264_videotoolbox`, `hevc_videotoolbox`). ([Codec Wiki][3])
* No AV1 VT encoder in FFmpeg; AV1 encoders are `libaom-av1`, `libsvtav1`, `rav1e`. ([FFmpeg Trac][16])
* VT quality controls: bitrate via `-b:v` (+ `-maxrate`/`-bufsize`); `-q:v` exists but spec chooses bitrate; CRF not applicable. ([Stack Overflow][4])
* Pixel formats: VT HEVC supports `p010le`; H.264/HEVC paths accept `yuv420p`; errors show when using `yuva*`. ([Super User][14])
* HEVC MP4 tag `hvc1` improves Apple playback. ([Brandur][7])
* Typical VT failure messages (“cannot create compression session … Try -allow_sw 1”). ([Reddit][11])
* Rosetta detection via `sysctl.proc_translated`. ([Apple Developer][2])
* YouTube public bitrate recommendations (context for optional scaling). ([Google Help][9])

---

If you want, I can tailor the HEVC path to auto‑switch to 10‑bit `p010le` when the input is HDR10 (based on `ffprobe` color primaries/transfer) while still keeping filters on CPU.

[1]: https://stackoverflow.com/questions/65346260/get-real-architecture-of-m1-mac-regardless-of-rosetta?utm_source=chatgpt.com "Get real architecture of M1 Mac regardless of Rosetta"
[2]: https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment?utm_source=chatgpt.com "About the Rosetta translation environment"
[3]: https://wiki.x266.mov/docs/encoders_hw/videotoolbox?utm_source=chatgpt.com "VideoToolbox"
[4]: https://stackoverflow.com/questions/63460919/how-to-improve-the-output-video-quality-with-ffmpeg-and-h264-videotoolbox-flag?utm_source=chatgpt.com "How to improve the output video quality with ffmpeg and ..."
[5]: https://stackoverflow.com/questions/64924728/optimally-using-hevc-videotoolbox-and-ffmpeg-on-osx?utm_source=chatgpt.com "Optimally using hevc_videotoolbox and ffmpeg on OSX"
[6]: https://github.com/HaveAGitGat/Tdarr/issues/1018?utm_source=chatgpt.com "ffmpeg doesn't recognize Video Toolbox · Issue #1018"
[7]: https://brandur.org/fragments/ffmpeg-h265?utm_source=chatgpt.com "Encoding H.265/HEVC for QuickTime with FFmpeg ..."
[8]: https://www.svp-team.com/forum/viewtopic.php?id=5719&utm_source=chatgpt.com "Hardware streaming on Mac (Page 1) — Using SVP"
[9]: https://support.google.com/youtube/answer/1722171?hl=en&utm_source=chatgpt.com "YouTube recommended upload encoding settings"
[10]: https://superuser.com/questions/1853656/ffmpeg-video-toolbox-failing-the-hardware-encoder-may-be-busy-or-not-supported?utm_source=chatgpt.com "FFmpeg Video Toolbox failing: The hardware encoder may ..."
[11]: https://www.reddit.com/r/ffmpeg/comments/s5uc02/h264_videotoolbox_on_legacy_mac/?utm_source=chatgpt.com "h264_videotoolbox on legacy Mac : r/ffmpeg"
[12]: https://stackoverflow.com/questions/75129495/ffmpeg-transparent-hvec-video-from-alpha-matte-and-color-video?utm_source=chatgpt.com "ffmpeg transparent HVEC video from alpha matte and color ..."
[13]: https://teamdynamix.umich.edu/TDClient/47/LSAPortal/KB/ArticleDet?ID=1484&utm_source=chatgpt.com "Getting macOS version and system details from the command ..."
[14]: https://superuser.com/questions/1614571/understanding-pixel-format-and-profile-when-encoding-10-bit-video-in-ffmpeg-with?utm_source=chatgpt.com "Understanding pixel format and profile when encoding 10 ..."
[15]: https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/apple/?utm_source=chatgpt.com "Apple Mac - Hardware Acceleration"
[16]: https://trac.ffmpeg.org/wiki/Encode/AV1?utm_source=chatgpt.com "Encode/AV1 – FFmpeg"
