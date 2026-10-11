---
name: kdenlive-zoom-cuts
description: Semantic transcript-driven zoom cuts, expressive punch-ins, push-ins, and unzooms for Kdenlive video projects. Use when adding dynamic camera framing, punch-ins/punch-outs, or pacing cuts to a rough-cut Kdenlive project timeline based on speech meaning and rhetoric.
---

# Kdenlive Semantic Zoom Cuts

Enhance rough-cut Kdenlive timelines with dynamic, transcript-driven framing shifts that mirror the speaker's emotional, rhetorical, and narrative beats. Every camera movement answers a single question: *Why does the speech demand a visual shift here?*

## Workflow

```
[Rough Cut .kdenlive]
       │
       ▼ (Step 1: melt audio extraction)
[/tmp/timeline_audio.wav]
       │
       ▼ (Step 2: transcribe.py)
[/tmp/timeline_transcript.json] (Word Timestamps on Timeline)
       │
       ▼ (Step 3: Agent Semantic Planning)
[/tmp/zoom_plan.json]
       │
       ▼ (Step 4: verify_zoom_plan.py)
[Linted Semantic Plan]
       │
       ▼ (Step 5: apply_zoom_cuts.py)
[project_roughcut_zoomed.kdenlive]
```

---

### Step 1: Extract Linear Timeline Audio

Extract the audio of the assembled sequence from the `.kdenlive` project file:

```bash
melt "/path/to/project_roughcut.kdenlive" \
  -consumer avformat:/tmp/timeline_audio.wav \
  vn=1
```

- `-consumer avformat:... vn=1`: Extracts the master sequence audio track with zero video decoding overhead.

**Completion criterion**: `/tmp/timeline_audio.wav` exists, is non-empty, and duration matches the sequence duration in Kdenlive.

---

### Step 2: Linear Timeline Transcription

Run the Whisper transcription helper on the extracted timeline audio to obtain word timestamps indexed directly to timeline timecode:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-rough-cut/scripts/transcribe.py \
  --input "/tmp/timeline_audio.wav" \
  --output "/tmp/timeline_transcript.json" \
  --model base \
  --device auto
```

- Timestamps in `/tmp/timeline_transcript.json` map $1:1$ to timeline seconds starting from `0.00s`.

**Completion criterion**: `/tmp/timeline_transcript.json` exists, is non-empty, and contains `segments` with word-level timestamps.

---

### Step 3: Semantic Zoom & Split Planning

Read `/tmp/timeline_transcript.json`. Act as an elite human editor by analyzing speech meaning, cadence, and rhetorical devices.

#### The Golden Law: Meaning Precedes Motion
**Never cut or zoom on a timer.** An unhurried, thoughtful sentence of 5–7 seconds delivered calmly belongs on a **Grounding Wide (`1.0x`)**—cutting without semantic purpose feels robotic and distracts the viewer. A camera shift earns its place *only* when speech changes direction, emotional intensity peaks, or a rhetorical device triggers emphasis.

---

#### The Expressive Zoom Palette

| Variation | Scale Range | Motion Mode | Anchor Framing | Semantic Role |
| :--- | :--- | :--- | :--- | :--- |
| **Grounding Wide** | `1.0x` | `instant` | Centered (`0.50`) | Neutral baseline. Context-setting, breath pauses, relaxed storytelling. Let speech breathe here. |
| **Micro-Punch** | `1.05x` – `1.08x` | `instant` | Upper-third (`Y=0.38`) | Nuanced sub-clauses, technical specifics, list-item progressions (*"First... second..."*). Subtly refreshes attention without jarring. |
| **Thesis Medium-Punch** | `1.12x` – `1.18x` | `instant` | Upper-third (`Y=0.38`) | Core advice, imperatives (*"You must..."*), contrast pivots (*"However"*, *"The problem is"*), and rhetorical questions directed at the viewer. |
| **Tight Dramatic Punch** | `1.24x` – `1.34x` | `instant` | Upper-third (`Y=0.38`) | Comedic tags, sarcastic deadpans, punchlines, moments of disbelief, critical warnings (*"Never do this"*). Snap back to wide on the following breath/pause. |
| **Slow Creep Push-In** | `1.0x` $\to$ `1.10x` | `push_in` ($\ge 2.5\text{s}$) | Upper-third (`Y=0.38`) | Vulnerability, intimate confessions, escalating suspense, or serious realizations. Subconsciously draws the viewer into the speaker's eyes. |
| **Slow Pull-Out (Unzoom)** | `1.15x` $\to$ `1.0x` | `pull_out` ($\ge 2.5\text{s}$) | Upper-third (`Y=0.38`) | Tension release, zooming out to the "big picture", sigh of relief, or concluding a major chapter before resetting. |
| **Lateral Re-Anchor** | `1.14x` | `instant` | Left (`0.46`) vs Right (`0.54`) | Dialectic A/B contrasts (*"On one hand [left-bias]... but on the other hand [right-bias]"*). Mimics an intentional multi-angle perspective switch. |

---

#### Semantic Trigger Taxonomy

When reading `/tmp/timeline_transcript.json`, identify the exact word onset for these rhetorical triggers:

1. **Cognitive Contrast ("The Twist")**:
   - Triggers: *"But"*, *"However"*, *"Here's the catch"*, *"Except"*, *"In reality"*.
   - Action: Razor-split $0.04\text{s}$ before the conjunction onset and punch in to **Medium-Punch (`1.15x`)**.
2. **Core Imperative & Thesis Statements**:
   - Triggers: *"The single most important rule is..."*, *"Stop doing X"*, *"This changes everything"*.
   - Action: Cut directly to **Medium-Punch (`1.14x` – `1.18x`)** on the main proposition.
3. **Punchlines, Sarcasm & Comedic Tags**:
   - Triggers: Sarcastic taglines, climactic joke words, deadpan understatements.
   - Action: Cut to **Tight Punch (`1.26x` – `1.32x`)** on the punchline delivery; reset to **Wide (`1.0x`)** immediately when the punchline concludes.
4. **Intimacy & Deep Narrative**:
   - Triggers: Personal struggle stories, sincere confessions, deep instructional build-up.
   - Action: Apply **Slow Creep Push-In (`push_in`, $1.0\times \to 1.10\times$)** across the continuous thought ($\ge 2.5\text{s}$).
5. **Resolution & Big Picture Summaries**:
   - Triggers: *"And that is how..."*, *"So at the end of the day..."*, *"When you step back..."*.
   - Action: Apply **Slow Pull-Out (`pull_out`, $1.15\times \to 1.0\times$)** as the argument concludes.
6. **Dualities & Two-Sided Comparisons**:
   - Triggers: *"Option A versus Option B"*, *"What beginners think... versus what pros do"*.
   - Action: Lateral offset **Left (`x_anchor: 0.46`)** on Option A, switching to **Right (`x_anchor: 0.54`)** on Option B.
7. **Nuanced Elaboration**:
   - Triggers: Secondary qualifying remarks inside an explanation (*"specifically regarding..."*, *"and this part is key"*).
   - Action: **Micro-Punch (`1.06x`)** to maintain subtle energy.

---

#### Intermediate Plan Schema (`zoom_plan.json`)

Compile the editorial decisions across the entire timeline into `/tmp/zoom_plan.json`:

```json
[
  {
    "timeline_start": 0.00,
    "timeline_end": 4.50,
    "motion": "instant",
    "scale": 1.0,
    "category": "grounding_wide",
    "reason": "Calm introductory premise setting the scene"
  },
  {
    "timeline_start": 4.50,
    "timeline_end": 7.80,
    "motion": "instant",
    "scale": 1.15,
    "category": "contrast_pivot",
    "reason": "Punch-in on cognitive pivot: 'However, almost nobody understands why...'"
  },
  {
    "timeline_start": 7.80,
    "timeline_end": 9.20,
    "motion": "instant",
    "scale": 1.28,
    "category": "punchline",
    "reason": "Tight punch on comedic tag: '...and that crashed the entire company'"
  },
  {
    "timeline_start": 9.20,
    "timeline_end": 14.50,
    "motion": "push_in",
    "scale_start": 1.0,
    "scale_end": 1.12,
    "category": "suspense_buildup",
    "reason": "Slow push-in on intimate lesson breakdown"
  },
  {
    "timeline_start": 14.50,
    "timeline_end": 18.20,
    "motion": "pull_out",
    "scale_start": 1.12,
    "scale_end": 1.00,
    "category": "big_picture_unzoom",
    "reason": "Slow pull-out de-escalating tension as macro conclusion is reached"
  }
]
```

**Completion criterion**: `/tmp/zoom_plan.json` covers the entire timeline from `0.00s` to project end, with valid `category` and explicit `reason` on every non-wide segment.

---

### Step 4: Verification & Semantic Linting Loop

Before modifying the timeline project, run the semantic plan linter:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-zoom-cuts/scripts/verify_zoom_plan.py \
  --plan "/tmp/zoom_plan.json"
```

The linter validates 6 structural gates:
1. **`MISSING-SEMANTIC-REASON`**: Every non-wide segment must provide an editorial `reason`.
2. **`DRIFT-TOO-SHORT`**: Dynamic drifts (`push_in` / `pull_out`) must be $\ge 2.0\text{s}$ to prevent visual stutter.
3. **`MICRO-CLIP`**: Rejects accidental micro-clips $<0.25\text{s}$.
4. **`SCALE-BOUNDS`**: Restricts zoom scaling to the cinematic safe range `[1.0, 1.35]`.
5. **`LATERAL-BOUNDS`**: Restricts `x_anchor` to safe framing range `[0.42, 0.58]`.
6. **`ZOOM-EXHAUSTION-WARNING`**: Flags continuous zoomed states sustained for $>12.0\text{s}$ without grounding relief.

**Convergence Rule**: Fix any structural issues in `/tmp/zoom_plan.json` until `verify_zoom_plan.py` reports **0 blocking issues detected**.

---

### Step 5: Apply Non-Destructive Slices & Transforms

Run the timeline transformation helper:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-zoom-cuts/scripts/apply_zoom_cuts.py \
  --project "/path/to/project_roughcut.kdenlive" \
  --plan "/tmp/zoom_plan.json" \
  --output "/path/to/project_roughcut_zoomed.kdenlive" \
  --eye-level 0.38
```

- Injects synchronized A/V razor-splits at semantic pivot timestamps.
- Computes upper-third eye-line biased (`Y=0.38`) and lateral-biased (`x_anchor`) MLT `qtblend` geometry.
- Constructs keyframes for slow push-ins and slow pull-outs.
- **Clip-Boundary Keyframe Clamping**: Clamps all `qtblend` keyframes (`rect`, `rotation`, `rotate_anchor`) strictly to relative clip timecodes (`00:00:00.000` through clip duration). Anchors rotation center (`rotate_anchor: 00:00:00.000=0.5 0.5`) across all keyframes to prevent rotational wobble or timecode drift when cuts ripple.
- Rebuilds native Kdenlive `sequenceproperties.groups` (`AVSplit`) so Ripple tool (`B`) keeps video and audio in lockstep.
- Validates the resulting MLT project with `melt`.

**Completion criterion**: `project_roughcut_zoomed.kdenlive` exists on disk and passes `melt` validation with 0 errors.

---

### Step 6: Report Edit Decisions and Launch

Present a concise summary to the user:
- Total cuts before vs. after semantic splits.
- Breakdown of applied variations: Grounding Wides, Micro-Punches, Medium-Punches, Tight Punches, Slow Push-Ins, Slow Pull-Outs, and Lateral Re-Anchors.
- Launch command:

```bash
kdenlive "/path/to/project_roughcut_zoomed.kdenlive" &
```

---

## Editorial Playbook

| Scenario | Editorial Rationale | Recommended Motion |
| :--- | :--- | :--- |
| **Speaker explains calmly for 6 seconds** | Do NOT cut just to "add movement". Respect the calm delivery. | Grounding Wide (`1.0x`) |
| **Speaker drops a sharp, unexpected joke** | Punctuate the humor visually. Cut tight, then immediately reset. | Tight Punch (`1.28x`) $\to$ Wide (`1.0x`) on laugh/pause |
| **Speaker contrasts two methods** | Shift perspective between the two alternatives. | Lateral Left (`x_anchor: 0.46`) $\to$ Lateral Right (`0.54`) |
| **Speaker shares an introspective struggle** | Match emotional intimacy with subtle camera approach. | Slow Creep Push-In (`1.0x \to 1.10x` over $\ge 3\text{s}$) |
| **Speaker wraps up an intense chapter** | Visual release of tension matching the verbal takeaway. | Slow Pull-Out (`1.15x \to 1.0x`) |
| **Speaker lists 3 steps rapidly** | Maintain brisk energy without jarring camera leaps. | Micro-Punch (`1.06x`) on Step 1, reset Wide on Step 2, Micro-Punch on Step 3 |
