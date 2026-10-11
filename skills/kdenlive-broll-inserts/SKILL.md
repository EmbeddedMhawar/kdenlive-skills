---
name: kdenlive-broll-inserts
description: Insert contextual B-roll footage, thematic cutaways, and title backdrops onto Track V2 in Kdenlive video projects. Use when enriching talking-head footage with visual cutaways, illustrating spoken topics, or framing kinetic titles and hooks over B-roll.
---

# Kdenlive B-Roll Inserts & Thematic Cutaways

Enrich talking-head Kdenlive timelines by inserting contextual B-roll footage, illustrative cutaways, and title backdrops onto **Track V2** without interrupting spoken dialogue on **Track A1**.

---

## Timeline Architecture & MLT Track Model

In Kdenlive (Timeline 2 / Generation 5), each timeline track is an MLT `<tractor>` consisting of **two subplaylists**:
- **Subtrack 0**: Primary playlist for clips and blanks.
- **Subtrack 1**: Secondary playlist used **exclusively for same-track transition mixes / crossfades**.

Clips placed on Subtrack 1 without an active mix transition are automatically flagged as corrupted and deleted by Kdenlive's loader (`meltBuilder.cpp`). Always target **Subtrack 0**:

```
Timeline Layout:
  V3 ── tractor6 (Subtrack 0: playlist8 / Subtrack 1: playlist9) ── Overlays, Titles & Chapter Cards
  V2 ── tractor3 (Subtrack 0: playlist6 / Subtrack 1: playlist7) ── B-Roll Cutaways & Backdrops
  V1 ── tractor2 (Subtrack 0: playlist4 / Subtrack 1: playlist5) ── Master A-Roll (rough-cut & zooms)
  ─────────────────────────────────────────────────────────────────────────────────────────────────
  A1 ── tractor1 (Subtrack 0: playlist2 / Subtrack 1: playlist3) ── Primary Dialogue Speech
  A2 ── tractor0 (Subtrack 0: playlist0 / Subtrack 1: playlist1) ── B-Roll Ambient Foley (-20dB to -24dB)
  A3 ── Motion Graphics SFX (whooshes, pops, typewriter clicks)
  A4 ── Music Bed
```

---

## Workflow

```
[B-roll Footage Dir]
       │
       ▼ (Step 1: extract_broll_keyframes.py [--generate-proxies])
[Thumbnails + broll_inventory.json + Proxies]
       │
       ▼ (Step 2: Agent Visual Cataloging & User Gate)
[broll_catalog.json]
       │
       ▼ (Step 3: Agent Semantic Placement Planning)
[broll_plan.json]
       │
       ▼ (Step 4: verify_broll_plan.py)
[Linted B-Roll Plan]
       │
       ▼ (Step 5: apply_broll.py [--generate-missing-proxies])
[project_roughcut_broll.kdenlive] (Clean Master Bin, V2, A2, & V3)
```

---

### Step 1: Extract Keyframe Thumbnails, Technical Inventory & Proxies

Run the keyframe extraction helper on the local B-roll folder to probe video dimensions, framerates, durations, audio streams, generate representative keyframe images, and transcode fast editing proxies:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-broll-inserts/scripts/extract_broll_keyframes.py \
  --input-dir "/path/to/broll_clips/" \
  --output-dir "/path/to/project/broll_thumbs/" \
  --proxies-dir "/path/to/project/proxies/" \
  --generate-proxies \
  --num-keyframes 3
```

- `--num-keyframes 3`: Generates 3 thumbnails per clip (at 15%, 50%, and 85% duration) for rapid visual indexing.
- `--proxies-dir`: Directory storing 540p editing proxies.
- `--generate-proxies`: Automatically transcodes fast 540p H.264 proxies for any clips missing them in `--proxies-dir`.

**Completion criterion**: `/path/to/project/broll_thumbs/broll_inventory.json` exists, is non-empty, thumbnails exist on disk, and all B-roll clips have valid proxies in `/path/to/project/proxies/`.

---

### Step 2: Visual Cataloging & User Approval Gate

Inspect the extracted keyframes and technical inventory to generate a semantic `broll_catalog.json`:

1. **Visual Tagging**: Describe each clip's visual setting, subject, actions, props, and lighting (e.g. *"Young man writing in black journal at cafe chair with soft daylight"*).
2. **Thematic Keywords**: Assign high-intent search tags (e.g. `["writing", "journal", "habits", "studying", "coffee", "deep work", "focus"]`).
3. **Usable Ranges**: Note stable, focused camera segments within the clip (cutting out camera repositioning or refocusing wobbles).
4. **Foley Quality**: Note if natural sound contains desirable ambient texture (e.g. keyboard typing, gym weights, nature ambience) suitable for a ducked bed on **Track A2**.

Format `broll_catalog.json`:

```json
[
  {
    "file_name": "IMG_5642.MOV",
    "file_path": "/path/to/broll/IMG_5642.MOV",
    "proxy_path": "/path/to/proxies/IMG_5642_proxy.mov",
    "duration": 58.2,
    "description": "Medium angle of young man writing in black journal at cafe chair with soft daylight",
    "tags": ["writing", "journal", "niche habits", "studying", "cafe", "focus", "planning"],
    "usable_ranges": [{"start": 2.0, "end": 28.0, "vibe": "calm_focused"}],
    "has_good_foley": true
  }
]
```

**User Confirmation Gate**: Present the summary table of cataloged clips and tags to the user. Await approval or tag adjustments before drafting placement.

**Completion criterion**: User confirms the catalog summary, and `broll_catalog.json` exists on disk.

---

### Step 3: Semantic Placement Planning

Analyze the timeline transcript (`timeline_transcript.json` or roughcut dialogue) alongside planned titles or motion graphics to build `/tmp/broll_plan.json`.

Follow the **Editorial Execution Principles**:

1. **The 2-Second Retention Sweet Spot (Pacing & Duration)**:
   - **Standard Cutaways (Workstation, Lifestyle, Tech, Gestures, Intros)**: Set duration strictly between **`1.8s` and `2.5s`**. Never hold standard cutaways for 5–6 seconds, as extended cutaways cause the audience to disconnect from the speaker's face and narrative energy.
   - **Physical Action / Exercise Repetitions**: Set duration to **`4.5s`–`6.0s`** only when showing continuous physical movement (compound lifts, pull-ups, cable reps) to capture the natural mechanical cycle of the exercise.

2. **The Action Apex Rule (Source In-Point Selection)**:
   - Never cut into the first $0.0\text{s}$–$2.0\text{s}$ of a raw camera take. Raw head handles often contain camera stabilization wobbles, operator refocusing, or the subject getting into position.
   - Advance `source_in` directly to the **action apex** (e.g. curtains actively being parted, weight mid-curl, fingers actively writing/typing) so the cut lands with immediate momentum.

3. **Dialogue Keyword Snapping (Timeline In-Point Alignment)**:
   - Do NOT pre-roll B-roll into preceding sentences. Pre-rolling creates awkward sentence overlap where the visual does not match what the speaker is currently finishing.
   - Snap timeline onset directly to the **accented keyword, punchline, or clause start** within the active sentence.
   - Cut out cleanly right as the spoken point completes, returning to the talking-head before the transition to the next topic.

4. **Motion Transform Rules**:
   - **Handheld Footage**: Always use `motion_preset: "static"`. Handheld footage already possesses organic physical camera movement; applying digital software zooms (`qtblend`) causes conflicting optical parallax.
   - **Static / Tripod Footage**: Use `subtle_push_in`, `subtle_pull_out`, or `subtle_drift` exclusively on locked-off tripod or static table shots to inject gentle cinematic drift.

5. **Audio Bed Lock & Boundary Isolation**:
   - When ambient foley sound is enabled on Track A2, strictly synchronize its in/out boundaries to the video cutaway duration.
   - **Cut Boundary Snapping**: If B-roll is placed at or immediately following a cut point on the main A-roll dialogue (e.g. after a pruned redundancy), the ambient audio bed on Track A2 must NEVER pre-roll across the cut boundary into the preceding scene. Snap the audio in-point (`in`) and start position directly to the cut boundary ($t_{\text{cut}}$) so gym/lifestyle foley does not bleed backward into an unrelated previous topic.
   - **Outro Tail Natural Decay**: On final B-roll inserts concluding a video or major sequence, allow the Track A2 ambient foley to extend past the visual video cutaway by 2–3 seconds with a smooth volume fade ramp down to silence under the talking-head outro.

Draft `/tmp/broll_plan.json`:

```json
[
  {
    "id": "broll_01",
    "clip_path": "/path/to/broll/IMG_5936.MOV",
    "proxy_path": "/path/to/proxies/IMG_5936_proxy.mov",
    "timeline_start": 17.03,
    "duration": 1.93,
    "source_in": 17.68,
    "motion_preset": "static",
    "ambient_audio_db": -22.0,
    "description": "Opening curtains B-roll snapping to intro hook sentence"
  }
]
```

**Completion criterion**: `/tmp/broll_plan.json` exists, is non-empty, and contains valid chronological insertion objects following the 2-second sweet spot and action apex rules.

---

### Step 4: Lint & Verify Plan

Execute the B-roll semantic linter to validate structural compliance before modifying the project:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-broll-inserts/scripts/verify_broll_plan.py \
  --plan "/tmp/broll_plan.json"
```

The linter verifies:
1. **`TIMECODE-BOUNDS`**: `timeline_start` $\ge 0.0\text{s}$ and strictly chronological.
2. **`COLLISION-CHECK`**: No overlapping clips on Track V2 (`timeline_start + duration \le next_start`).
3. **`FILE-EXISTS`**: Every referenced video file exists on disk.
4. **`SOURCE-RANGE`**: `source_in + duration \le source_media_duration`.
5. **`MOTION-PRESET`**: Valid motion preset (`static`, `subtle_push_in`, `subtle_pull_out`, `subtle_drift`).
6. **`AUDIO-PARAM`**: Valid dB attenuation values between `-60.0` and `0.0`.

**Completion criterion**: `verify_broll_plan.py` reports `Verification PASSED: 0 blocking issues`.

---

### Step 5: Non-Destructive Timeline Assembly

Inject the verified B-roll cuts and ambient beds into the Kdenlive project XML:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-broll-inserts/scripts/apply_broll.py \
  --project "/path/to/project_roughcut_zoomed.kdenlive" \
  --plan "/tmp/broll_plan.json" \
  --output "/path/to/project_roughcut_broll.kdenlive" \
  --proxies-dir "/path/to/project/proxies/" \
  --generate-missing-proxies
```

#### What `apply_broll.py` Guarantees:
- **Master Clip Bin Registration**: Registers each unique source file **once** in `main_bin` with full duration and proxy link (`kdenlive:proxy`).
- **Unified Identifiers**: Bin master chain (`c_bin`), video track chain (`c_vid`), and audio track chain (`c_aud`) share the **exact same `kdenlive:control_uuid`** and `kdenlive:id`, preventing Kdenlive from dropping timeline clips as orphaned.
- **Track V2 Insertion**: Places video cutaways onto Track V2 primary subtrack (`playlist6`).
- **Track A2 Insertion**: Places ducked ambient audio beds onto Track A2 primary subtrack (`playlist0`) with 15-frame edge volume ramps.
- **Track V3 Scaffolding**: Dynamically creates Track V3 (`tractor6` with `playlist8`/`playlist9`) and wires the `qtblend` compositing transition (`transition4`) into `tractor4` so overlay skills have Track V3 pre-configured.
- **Empty Mix Subtracks**: Keeps secondary mix playlists (`playlist1`, `playlist3`, `playlist5`, `playlist7`, `playlist9`) empty to prevent Kdenlive mixed-track errors.
- **Timeline Viewport Optimization**: Sets playhead position to `00:00:00`, scroll position to `0`, zoom to fit, and track heights to 48px for clean GUI visibility.
- **MLT Verification**: Executes `melt` syntax check on the output file with 0 errors.

**Completion criterion**: Output `.kdenlive` project exists and passes `melt` validation with 0 errors.

---

### Step 6: Review in Kdenlive GUI

Present the B-roll placement summary to the user:
- Total B-roll inserts applied on Track V2.
- Title hooks covered and ambient audio beds added to Track A2.
- Launch the project:

```bash
kdenlive "/path/to/project_roughcut_broll.kdenlive" &
```

---

## The Motion & Ken Burns Palette

| Preset | Motion Description | Scale Geometry | Best Used For |
| :--- | :--- | :--- | :--- |
| **`static`** | Native 1.0x frame without transform | Fixed $1.0\text{x}$ | Handheld footage with organic camera movement, screen captures, dynamic action. |
| **`subtle_push_in`** | Slow forward creep toward frame center | $1.00\text{x} \to 1.05\text{x}$ | Static tripod shots, contemplative moments, drawing viewer focus into details. |
| **`subtle_pull_out`** | Slow unzoom releasing frame tension | $1.05\text{x} \to 1.00\text{x}$ | Revealing broader context, concluding an illustrative point, breath resets. |
| **`subtle_drift`** | Gentle lateral pan across frame | $1.04\text{x}$ scale, $X: 0.47 \to 0.53$ | Wide interior shots, desk arrangements, cinematic landscape cutaways. |

---

## Editorial Playbook & Pitfalls

| Potential Error | Root Cause | Mandatory Mitigation |
| :--- | :--- | :--- |
| **"Timeline clip without bin reference found and removed"** | Track chain `kdenlive:control_uuid` differs from master bin chain `control_uuid`. Kdenlive's `meltBuilder.cpp` fails lookup in `binIdCorresp`. | **Unified Control UUID**: In `apply_broll.py`, generate `clip_uuid` once per master clip and share it across `c_bin`, `c_vid`, and `c_aud`. |
| **"Invalid clip found on track without mix and removed"** | Placing timeline clips on Subtrack 1 (`playlist5` or `playlist3`) instead of Subtrack 0. Subtrack 1 is reserved exclusively for same-track mixes. | **Subtrack 0 Targeting**: Target `playlist6` for Track V2 and `playlist0` for Track A2. Leave all mix playlists empty. |
| **Missing Proxies / Project Bin Warning Icons** | Referencing proxy files that do not exist on disk, or omitting `kdenlive:proxy` property. | **Automated Proxy Generation**: Use `--generate-proxies` in Step 1 or `--generate-missing-proxies` in `apply_broll.py` to guarantee proxy files exist before project assembly. |
| **Track V3 Missing in GUI** | Adding Track V3 without adding track element and compositing transition to sequence tractor `tractor4`. | **Scaffold Track V3**: Add `tractor6` (with `playlist8`/`playlist9`) to `tractor4` with `qtblend` compositing `transition4` and set sequence track counts to 5. |
| **Extended Cutaway Drag** | Holding generic lifestyle/tech B-roll for 5–6 seconds, causing viewer disengagement from the speaker. | **The 2-Second Sweet Spot**: Enforce $1.8\text{s}$–$2.5\text{s}$ duration for standard cutaways; reserve $\ge 5\text{s}$ strictly for continuous physical exercise sets. |
| **Setup Wobble Cuts** | Cutting at `source_in = 0.0s` where camera operator is settling, framing, or refocusing. | **Action Apex Rule**: Advance `source_in` past the first $1$–$2\text{s}$ of handle directly into the peak motion. |
| **Parallax Motion Clash** | Applying digital software zoom/pan onto handheld footage that already has organic camera movement. | **Handheld Static Rule**: Keep handheld footage strictly on `static` motion preset; reserve Ken Burns transforms for locked-off tripod shots. |
| **Pre-Roll Dialogue Clashing** | Starting B-roll during preceding sentence lead-in before the concept is spoken. | **Keyword Snapping**: Snap cut onset directly to the accented keyword or punchline clause inside the active sentence. |
| **Dialogue Interruption** | Splicing B-roll onto Track V1/A1, overwriting talking-head dialogue. | **Isolated Track V2**: Place B-roll exclusively on Track V2; Master speech dialogue flows continuously on A1. |
| **Acoustic Audio Clashing** | Playing B-roll audio at 0dB, drowning out the speaker. | **Selective Ducking**: Mute B-roll by default; place foley sound on Track A2 attenuated to $-20\text{dB}$ to $-24\text{dB}$ with 15-frame edge ramps. |
| **Cross-Cut Audio Bleed** | Track A2 ambient B-roll foley starting prior to a main dialogue cut point and bleeding backwards. | **Cut Boundary Clamping**: Snap audio `in` and timeline start to the exact cut boundary $t_{\text{cut}}$, preventing pre-roll bleed into earlier scenes. |
| **Track V2 Collisions** | Overlapping two B-roll clips at the same timecode. | **Collision Linter**: Run `verify_broll_plan.py` prior to assembly to guarantee strict chronological placement. |
