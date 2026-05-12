"""End-to-end caption demo: TTS → WhisperX align → karaoke compose. No DB, no pipeline."""

import random
import sys

sys.path.insert(0, "src")

from pathlib import Path

from config import COMPUTE_DEVICE, WHISPER_MODEL
from merge_captions import compose, transcribe_and_align
from nodes.tts_node import _sanitize_for_tts

TEXT = (
    "Breaking news from Warsaw. Scientists have discovered that cats can accurately "
    "predict the weather up to 48 hours in advance. Researchers say the animals "
    "react to changes in atmospheric pressure that humans simply cannot detect."
)
SPEAKER = "Claribel Dervla"
LANGUAGE = "en"

audio_path = Path("/tmp/demo_speech.wav")
out_path = Path("/tmp/demo_captions_output.mp4")

# --- 1. TTS ---
print("Step 1/3 — generating speech…")
from TTS.api import TTS

tts = TTS(
    model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True
).to(COMPUTE_DEVICE)
tts.tts_to_file(
    text=_sanitize_for_tts(TEXT),
    file_path=str(audio_path),
    language=LANGUAGE,
    speaker=SPEAKER,
)

# --- 2. WhisperX alignment ---
print("\nStep 2/3 — aligning words…")
words = transcribe_and_align(
    audio_path, device=COMPUTE_DEVICE, model_size=WHISPER_MODEL
)
print(f"  got {len(words)} word timings")

# --- 3. Pick a random stock video and compose ---
all_clips = list(Path("media").rglob("*.mp4"))
if not all_clips:
    raise FileNotFoundError(
        "No .mp4 files found in media/. Add stock clips before running."
    )
bg_path = random.choice(all_clips)
print(f"\nStep 3/3 — composing with {bg_path}…")
compose(bg_path, audio_path, words, out_path)

print(f"\nDone → {out_path}")
