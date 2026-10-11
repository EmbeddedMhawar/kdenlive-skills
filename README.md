# Kdenlive Skills for Google Antigravity

[![Validate Kdenlive Skills](https://github.com/EmbeddedMhawar/kdenlive-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/EmbeddedMhawar/kdenlive-skills/actions/workflows/validate.yml)
[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-4285F4?logo=google&logoColor=white)](https://antigravity.google)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready **Google Antigravity Plugin** providing a full video editing suite for [Kdenlive](https://kdenlive.org). Automate rough cuts, semantic retake pruning, transcript-driven zoom cuts, motion graphics, B-roll insertion, and speech-synchronized sound design—all generating native, non-destructive `.kdenlive` project timelines.

---

## ⚡ Quick Install (1-Line Command)

Run this command in your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/EmbeddedMhawar/kdenlive-skills/main/install.sh | bash
```

Antigravity will discover the plugin in `~/.gemini/config/plugins/kdenlive` and activate all 6 skills across your sessions.

---

## 📦 Alternative Installation Options

### Option A: Standard Git Clone (Global)
```bash
git clone --depth 1 https://github.com/EmbeddedMhawar/kdenlive-skills.git ~/.gemini/config/plugins/kdenlive
```

### Option B: Per-Project / Team Repository (Version Controlled)
If you want to pin these skills to a specific repository:
```bash
git submodule add https://github.com/EmbeddedMhawar/kdenlive-skills.git .agents/plugins/kdenlive
```

---

## 📐 Timeline Architecture

Every skill in this suite targets a unified, non-destructive MLT track layout:

```
Video Tracks:
  V3 ── Motion Graphics, Chapter Cards & Kinetic Titles (Alpha Overlays)
  V2 ── Contextual B-Roll Footage & Cutaways
  V1 ── Master A-Roll (Talking-head footage from rough-cut & zoom-cuts)
─────────────────────────────────────────────────────────────────────────────
Audio Tracks:
  A1 ── Primary Dialogue Speech (Continuous & Uninterrupted)
  A2 ── B-Roll / Ambient Secondary Foley (-20dB to -24dB)
  A3 ── Synchronized SFX (Motion hits + Punctuation accents + Minecraft cues)
  A4 ── Music Bed (Optional)
```

---

## 🎬 Included Skills

| Skill | Description | Primary Inputs & Outputs |
| :--- | :--- | :--- |
| **`kdenlive-rough-cut`** | Assembles rough-cut timelines by pruning retakes, stumbles, and false starts using the Final Iteration Rule. | Raw video $\rightarrow$ `/tmp/transcript.json` $\rightarrow$ `project_roughcut.kdenlive` |
| **`kdenlive-zoom-cuts`** | Applies semantic, transcript-driven camera framing shifts (punch-ins, push-ins, unzooms) matching emotional/rhetorical beats. | `project_roughcut.kdenlive` $\rightarrow$ `project_roughcut_zoomed.kdenlive` |
| **`kdenlive-motion-graphics`** | Generates animated chapter cards, kinetic typography overlays, and synchronized SFX. | Timeline transcript $\rightarrow$ Rendered alpha overlays $\rightarrow$ Track V3 / A3 |
| **`kdenlive-broll-inserts`** | Catalogs B-roll media, generates keyframe thumbnails, and places cutaways onto Track V2. | B-roll folder + Rough-cut $\rightarrow$ Track V2 cutaways |
| **`kdenlive-redundancy-pruner`** | Audits timelines for duplicate proposition collisions and performs frame-accurate ripple cuts while preserving intentional analogies. | Assembled `.kdenlive` $\rightarrow$ `project_deduped.kdenlive` |
| **`kdenlive-transcript-sfx`** | Speech-synchronized Foley, punctuation accents, and iconic Minecraft cues placed on Track A3. | Speech transcript $\rightarrow$ Linted sound plan $\rightarrow$ Track A3 SFX |

---

## 🛠️ Workflows & Capabilities

### 1. Rough Cut (`kdenlive-rough-cut`)
- **Hardware-Accelerated Proxies**: Intel QuickSync / VAAPI GPU hardware transcode (`scale_vaapi`, `h264_vaapi -g 60 -bf 0`) for lag-free scrubbing.
- **Word-Level Transcription**: Whisper integration producing word-level timestamps.
- **The Final Iteration Rule**: Automatically identifies stutter loops and false starts, retaining only the definitive final delivery.
- **Acoustic Verification Loop**: Validates cut boundaries against acoustic dead air ($>0.6\text{s}$), stretched words ($>0.85\text{s}$), and clipped onsets.

### 2. Semantic Zoom Cuts (`kdenlive-zoom-cuts`)
- **Emotional & Rhetorical Shifts**: Scales frames by $1.15\times$ (punch-in) or $1.25\times$ (deep emphasis) at topic pivots, punchlines, and rhetorical climaxes.
- **Pacing Protection**: Enforces minimum hold durations and cooldown intervals to avoid visual fatigue.
- **Native MLT Transforms**: Directly manipulates Kdenlive's `qtblend` / transform filter keyframes.

### 3. Motion Graphics & Chapter Cards (`kdenlive-motion-graphics`)
- **Kinetic Typography**: Word-by-word reveals, typewriter animations, and lower-third overlays rendered with ProRes 4444 / WebM alpha transparency.
- **Procedural Backgrounds**: Dynamic gradient sweeps, cyber-dark cards, and minimal chapter bumpers.
- **SFX Pairing**: Automatically inserts matching whooshes, clicks, and sub-hits onto Track A3.

### 4. Contextual B-Roll Inserts (`kdenlive-broll-inserts`)
- **Automated Cataloging**: Probes durations, aspect ratios, framerates, and extracts representative keyframe thumbnails.
- **Subtrack 0 Targeting**: Adheres strictly to Kdenlive's MLT track model (Timeline 2 / Generation 5), avoiding corrupted Subtrack 1 crossfade slots.
- **Audio Ducking**: Ambient audio placed onto Track A2 calibrated to $-20\text{dB}$ to $-24\text{dB}$.

### 5. Redundancy Pruning (`kdenlive-redundancy-pruner`)
- **Proposition Collisions**: Detects sentences expressing duplicate core instructions or re-explained examples across adjacent camera takes.
- **Editorial Preservation**: Explicitly protects intentional rhetoric (metaphors, analogies, progressive technical elaborations).
- **Multi-Track Ripple Cut**: Synchronously ripples across all video and audio tracks to preserve perfect timeline alignment.

### 6. Transcript-Driven Sound Design (`kdenlive-transcript-sfx`)
- **Bundled Sound Pack**: High-fidelity 48kHz WAV library including punctuation accents (chimes, pops, bells), literal Foley (cash register, camera shutter, clock ticks), and impacts.
- **Official Minecraft SFX**: Mojang 48kHz sound effects (level-up orb, item break, chest open, bell ding, creeper hiss, anvil land).
- **Psychoacoustic Gain Calibration**: Pre-calibrated against dialogue at $-12\text{dB}$ LUFS to prevent masking speech.

---

## 📋 Prerequisites

To run all scripts and features, ensure the following tools are available on your system:

- **Kdenlive** $\ge 23.08$
- **MLT Framework** (`melt`)
- **FFmpeg** (with `ffprobe`)
- **Python 3.10+**
- Recommended Python packages:
  ```bash
  pip install faster-whisper numpy Pillow
  ```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

```bash
# Validate skill frontmatter and directory structure
./scripts/validate.sh
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
