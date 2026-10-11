# Kdenlive Skills Antigravity Plugin

Project repository for the **Kdenlive Video Suite** plugin for Google Antigravity.

## Timeline Architecture

Every workflow in this repository adheres to this MLT track model:

```
Tracks:
  V3 ── Motion Graphics, Chapter Cards & Kinetic Titles (overrides or overlays)
  V2 ── Contextual B-Roll Footage & Inserts (preserved)
  V1 ── Master A-Roll (talking-head footage from rough-cut & zoom-cuts)
  ─────────────────────────────────────────────────────────────────────────────
  A1 ── Primary Dialogue Speech (continues uninterrupted)
  A2 ── B-Roll / Secondary Ambient Audio (-20dB to -24dB)
  A3 ── Synchronized SFX (Motion title hits + Transcript accents & Minecraft SFX)
  A4 ── Music Bed (optional)
```

## Skills Directory Layout

- `skills/kdenlive-rough-cut/`: Automated speech-driven rough cuts, VAAPI GPU proxy transcode, Whisper word-timestamp transcription, retake pruning, and MLT/OTIO assembly.
- `skills/kdenlive-zoom-cuts/`: Semantic transcript-driven camera punch-ins, push-ins, and unzooms.
- `skills/kdenlive-motion-graphics/`: Chapter cards, kinetic titles, procedural motion backgrounds, and paired SFX.
- `skills/kdenlive-broll-inserts/`: Contextual B-roll keyframe cataloging and Track V2 insertion.
- `skills/kdenlive-redundancy-pruner/`: Proposition collisions audit, deduplication, and frame-accurate ripple cut.
- `skills/kdenlive-transcript-sfx/`: Speech-synchronized Foley, punctuation accents, and official Minecraft SFX on Track A3.

## Common Commands

- **Validate Skills**: `./scripts/validate.sh`
- **Install/Update Locally**: `./install.sh`
- **Check Python Syntax**: `find skills/ -name "*.py" -exec python3 -m py_compile {} +`
