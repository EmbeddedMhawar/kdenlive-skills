---
name: kdenlive-motion-graphics
description: Add animated full-screen chapter cards, transparent in-frame kinetic titles, procedural/AI motion backgrounds, and synchronized SFX to Kdenlive video projects. Use when enhancing talking-head videos with dynamic typography, chapter bumpers, sound effects (whooshes, pops, typewriter clicks, sub-hits), or visual viewer retention hooks.
---

# Kdenlive Motion Graphics & SFX

Enhance Kdenlive timelines with dynamic typography, full-screen chapter cards, and paired sound effects (SFX) that punctuate speech milestones without disrupting narrative flow.

## Timeline Architecture

```
Tracks:
  V3 ── Motion Graphics, Chapter Cards & Kinetic Titles (overrides or overlays)
  V2 ── B-Roll Footage & Inserts (preserved)
  V1 ── Master A-Roll (talking head footage from rough-cut & zoom-cuts)
  ─────────────────────────────────────────────────────────────────────────────
  A1 ── Primary Dialogue Speech (continues uninterrupted)
  A2 ── B-Roll / Secondary Audio
  A3 ── Synchronized Motion SFX (sub-hits, whooshes, pops, typewriter clicks)
  A4 ── Music Bed
```

---

## Workflow

```
[Master Rough-Cut .kdenlive]
       │
       ▼ (Step 1: Ingest Transcript & Directives)
[timeline_transcript.json] ──> generate_motion_plan.py
       │
       ▼ (Step 2: User Approval Gate)
[/tmp/motion_plan.json]
       │
       ▼ (Step 3: verify_motion_plan.py)
[Linted Motion Plan]
       │
       ▼ (Step 4: render_motion_graphics.py)
[motion_manifest.json + .mp4 / .webm + .wav]
       │
       ▼ (Step 5: apply_motion_graphics.py)
[project_roughcut_motion.kdenlive] (V3 & A3 Injected)
```

---

### Step 1: Detect Key Moments & Draft Plan

Run the motion plan generator on the timeline transcript:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-motion-graphics/scripts/generate_motion_plan.py \
  --transcript "/tmp/timeline_transcript.json" \
  --output "/tmp/motion_plan.json" \
  --font "Clarify-Blk" \
  --theme "cyber_dark" \
  --bg-engine "programmatic"
```

- `--font <name>`: Sets the typography font family (e.g. `Clarify-Blk`, `Montserrat`, `Cabinet Grotesk`, `Bebas Neue`).
- `--theme <name>`: Visual theme profile (`cyber_dark`, `mesh_blue`, `ai_hybrid`, `minimal_white`).
- `--bg-engine <mode>`: Background generation mode (`programmatic` for procedural 3D grid and flowing gradients; `ai_programmatic` for AI concept images with 2.5D camera drift).
- `--user-prompts <json|path>`: Optional explicit timestamp directives requested by the user.

**Completion criterion**: `/tmp/motion_plan.json` exists, is non-empty, and contains structured event entries.

---

### Step 2: Semantic Review & User Approval Gate

Review `/tmp/motion_plan.json` before rendering. Ensure every title event has an editorial rationale:

1. **Full-Screen Chapter Cards (`fullscreen_card`)**:
   - Used for chapter shifts, topic pivots, and major list milestones (e.g., *“Step 1: Set Up Basics”* or *“Habit 1: Start 'idea walking'”*).
   - Card displays for 2.5s–3.5s on **Track V3** while speech dialogue flows continuously on **Track A1**.
   - Punctuated by a cinematic sub-impact / riser on **Track A3** (cinematic 808 sub-hits are strictly reserved for full-screen card bumpers; never use raw sub-drops during naked talking-head speech).
2. **In-Frame Kinetic Overlays (`inframe_overlay`)**:
   - Used for quick in-flow hooks, rules, and punchy statements (e.g., *“10 niche habits to get absurdly ahead in your 20s”*).
   - Rendered as transparent alpha video over the speaker footage on **Track V3**.
   - Paired with mechanical typewriter clicks, clean UI pops, or airy whooshes on **Track A3** (unobtrusive mid-to-high frequency accents that leave dialogue completely legible).

Present the draft plan summary to the user for approval. If the user requests edits to wording, timestamps, or fonts, update `/tmp/motion_plan.json`.

---

### Step 3: Lint & Verify Plan

Run the semantic linter before initiating video rendering:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-motion-graphics/scripts/verify_motion_plan.py \
  --plan "/tmp/motion_plan.json"
```

The linter validates 5 structural gates:
1. **`TIMECODE-BOUNDS`**: `timeline_start` $\ge 0.0\text{s}$ and strictly chronological.
2. **`CARD-OVERLAP`**: No full-screen cards collide or overlap.
3. **`DURATION-RANGE`**: Durations are between $0.5\text{s}$ and $20.0\text{s}$.
4. **`FONT-AVAILABILITY`**: Verifies font exists in `fontconfig` or local user font paths.
5. **`SFX-RESOLUTION`**: Confirms requested audio profile exists in `resources/sfx`.

**Completion criterion**: `verify_motion_plan.py` reports `Verification PASSED: 0 blocking issues`.

---

### Step 4: Render Motion Graphics & Synthesize SFX

Execute the high-performance rendering engine:

```bash
uv run --with pillow \
  ~/.gemini/config/plugins/kdenlive/skills/kdenlive-motion-graphics/scripts/render_motion_graphics.py \
  --plan "/tmp/motion_plan.json" \
  --output-dir "/path/to/project/titles/" \
  --fps 60
```

The renderer outputs:
1. **Video Clips**:
   - `fullscreen_card`: 1080p 60fps MP4 with animated 3D cyber grid, flowing liquid mesh gradient, or AI concept drift.
   - `inframe_overlay`: 1080p 60fps WebM VP9 with transparent alpha channel (`yuva420p`).
2. **Synchronized Audio**:
   - 48kHz 16-bit mono WAV audio clips with sample-accurate SFX alignment.
3. **Manifest**:
   - `/path/to/project/titles/motion_manifest.json` mapping each item to its exact timeline start and generated media paths.

**Completion criterion**: All video and audio assets exist on disk, verified by `motion_manifest.json`.

---

### Step 5: Non-Destructive Timeline Assembly

Inject the generated assets into the master Kdenlive timeline XML:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-motion-graphics/scripts/apply_motion_graphics.py \
  --project "/path/to/project_roughcut_zoomed.kdenlive" \
  --manifest "/path/to/project/titles/motion_manifest.json" \
  --output "/path/to/project_roughcut_motion.kdenlive"
```

- Injects video assets onto **Track V3** (`playlist6`).
- Injects synchronized SFX onto **Track A3** (`playlist1`).
- Preserves A-Roll cuts (V1/A1) and B-Roll (V2/A2) with zero track desync.
- Runs `melt` validation to ensure syntax compliance.

**Completion criterion**: `project_roughcut_motion.kdenlive` exists on disk and passes `melt` validation with 0 errors.

---

### Step 6: Launch & Editorial Review

Report the applied motion graphics summary to the user:
- Total chapter cards and in-frame titles added.
- Fonts and visual themes applied.
- Launch command:

```bash
kdenlive "/path/to/project_roughcut_motion.kdenlive" &
```

---

## The Motion & SFX Palette

| Preset | Visual Mode | Background Mode | Typography Layout | Paired SFX Profile | Best Used For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cyber Chapter** | `fullscreen_card` | `cyber_grid` (3D Curved Wireframe) | `stacked_card` (Eyebrow + Bold Title) | `sub_hit` (Cinematic Sub-Boom) | Tech/productivity chapters, rules, steps (*Step 1: Set Up Basics*) |
| **Mesh Bumper** | `fullscreen_card` | `mesh_gradient` (Liquid Color Mesh) | `stacked_card` (Eyebrow + Bold Title) | `sub_hit` / `whoosh` | Modern lifestyle, habits (*Habit 1: Start 'idea walking'*) |
| **AI Concept Drift**| `fullscreen_card` | `ai_programmatic` (Thematic Concept + 2.5D Drift) | `stacked_card` | `sub_hit` + `riser` | Storytelling pivots, case studies, thematic shifts |
| **Kinetic Multi-Scale** | `inframe_overlay` | `transparent` (Alpha Video) | `kinetic_multiscale` (Huge Number + Italic Accent) | `whoosh` / `pop` | Video hooks, high-retention stats (*10 niche habits to get absurdly ahead*) |
| **Typewriter Badge**| `inframe_overlay` | `transparent` (Alpha Video) | `typewriter_badge` (Cursor Blink) | `mechanical` / `thock` | Rules, quotes, code snippets, precise instructions |

---

## Editorial Playbook & Pitfalls

| Potential Error | Root Cause | Mandatory Mitigation |
| :--- | :--- | :--- |
| **Dialogue Interruption** | Splitting A-roll video/audio to insert chapter cards, halting speech. | **Continuous A1 Flow**: Place cards on V3; dialogue audio on A1 continues completely uninterrupted. |
| **Track Collision / Clutter** | Putting titles on V2, overriding user B-roll footage. | **Strict Track V3 Placement**: Reserve V1 for A-roll, V2 for B-roll, V3 exclusively for motion graphics/titles. |
| **SFX Pacing Clash** | SFX triggering before or after visual text appears. | **Sample-Accurate Sync**: Lock audio SFX onset to exact visual text pop ($t = 0.05\text{s}$) or typewriter character unroll. |
| **Font Inconsistency** | Using multiple mismatched font styles across titles. | **Project Typography Anchor**: Enforce user's primary font (e.g. `Clarify-Blk` or `Montserrat`) across all titles. |
| **Overlapping Cards** | Placing two full-screen cards within $<3.0\text{s}$ of each other. | **Collision Linter**: `verify_motion_plan.py` strictly rejects overlapping full-screen card timecodes. |
| **Sequence Builder Crash on Launch** | Injecting $>6$ programmatic timeline tracks (e.g. V4/V5, A4/A5) or rewriting `kdenlive:sequenceproperties.groups` with custom group trees. Kdenlive GUI (`TimelineModel::loadGroups` / OpenTimelineIO) segfaults on uninitialized track indices. | **Strict 6-Track Schema**: Enforce the stable 6-track timeline architecture (V1–V3, A1–A3). Composite concurrent/multi-line kinetic typography into single transparent VP9 WebM clips on Track V3 with paired WAV on Track A3. Shift existing camera group track numbers by exactly $+1$ when inserting Track A3 (`tractor7`). |
| **Excessive Line Spacing Gap** | Applying generic typography leading (`line_size * 1.25`) to bold display fonts (e.g., `Clarify-Blk`) leaves a 35–40px blank gap between stacked title lines. | **Tight Optical Leading**: Use `line_h = int(line_size * 0.80)` in kinetic layouts to produce a cohesive 2–8px visual separation between stacked lines. |
| **Preamble vs. Punchline Desync** | Setting `timeline_start` solely to the punchline vocal hit (missing the spoken rule intro) or cutting duration short before the concept explanation ends. | **Two-Stage Speech Anchoring**: Anchor `timeline_start` to the preamble onset (*"The third rule is..."*) for immediate Eyebrow/Badge entry ($t=0.0\text{s}$), stagger lines on punchline vocal hits, and hold duration through the explanation. |
