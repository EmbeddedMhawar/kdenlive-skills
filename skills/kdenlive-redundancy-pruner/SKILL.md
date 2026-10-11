---
name: kdenlive-redundancy-pruner
description: Audit assembled Kdenlive timelines for duplicate sequential ideas, repeated propositions, and rephrased retakes. Use when reviewing a rough-cut or final cut to eliminate duplicate sentences while preserving analogies, progressive elaborations, and structural recaps.
---

# Kdenlive Redundancy Pruner

Audit assembled Kdenlive timelines for duplicate sequential sentences, rephrased retakes, and redundant propositions. Ensure every spoken phrase advances narrative momentum while strictly preserving intentional rhetoric like analogies, progressive technical breakdowns, and section summaries.

## Workflow

```
[Kdenlive Project (.kdenlive)]
       │
       ▼ (Step 1: melt audio extraction)
[/tmp/timeline_audio.wav]
       │
       ▼ (Step 2: transcribe.py)
[/tmp/timeline_transcript.json] (Word-accurate Timeline Timestamps)
       │
       ▼ (Step 3: Chapter Context Audit & Proposition Collision Analysis)
[/tmp/candidate_redundancies.json]
       │
       ▼ (Step 4: Triad Review Gate - Dual-Lens Editorial Presentation)
[/tmp/approved_deletions.json]
       │
       ▼ (Step 5: Frame-Accurate apply_redundancy_pruning.py)
[project_deduped.kdenlive] (Multi-track synchronized ripple cut)
```

---

## Editorial Classification Principles

### 1. What to Flag: Proposition Collisions
Flag pairs of sentences where the speaker asserts the **same core claim, instruction, or conclusion** using slightly varied wording:
* **Core Claim Duplication**:
  * *Take A*: "You need to make sure your database is configured properly before launching."
  * *Take B*: "Setting up your database correctly is essential before you push to production."
  * *Decision*: **Flag as collision**. Keeping both drags video pacing and confuses the viewer.
* **Repetitive Pacing Loops & Abstract Throat-Clearing**:
  * *Take A*: "Because what a lot of people do if they've had a bad day is they let themselves go for the rest of the day."
  * *Take B*: "If they slip up on their streak, then the rest of the day they will fill it with bad habits."
  * *Decision*: **Flag as collision**. Take A is abstract throat-clearing; Take B introduces the concrete setup that anchors the subsequent examples.
* **Tautological Metaphor Recaps & Cross-Take Example Re-runs**:
  * *Take A (Complete Example)*: "Have the end goal be a thousand pounds a month or three thousand pounds... Don't make it so drastic that you'll never achieve it."
  * *Take B (Stumble & Duplicate Example)*: "Focus on the lower bosses first, then build your way up... If your goal is to make money online... have the goal be a thousand pounds or two thousand pounds a month. Don't be aiming for these crazy numbers."
  * *Decision*: **Flag as collision**. Take B repeats the exact same financial example across adjacent camera takes while re-explaining the level 1 boss opening metaphor, stacking repetitive negative imperatives ("Don't make it drastic... Don't aim for crazy numbers..."). Pruning Take B allows a direct, punchy hard cut from the online money example into the subsequent gym example.
* **Repeated Proposition Echoes before Transitions**:
  * *Sentence A*: "That is a reachable goal and those people can teach you the things that you need to learn."
  * *Sentence B (2 sentences later)*: "But the people who are just a few steps ahead can teach you valuable things that will then drag you up to their level."
  * *Decision*: **Flag as collision**. Repeating the identical mentor proposition within two sentences stalls forward momentum before a personal storytelling pivot. Excise Sentence B.

### 2. What to Preserve: Intentional Rhetoric (Do Not Flag)
Preserve statements fulfilling distinct rhetorical functions:
* **Analogies & Metaphors**:
  * *Concept*: "The database holds all your application state."
  * *Analogy*: "Think of it like the foundation of a skyscraper; if it cracks, the whole building collapses."
  * *Decision*: **Preserve both**. Analogies translate abstract concepts into tangible mental models.
* **Progressive Elaborations (General to Specific)**:
  * *General*: "We need a reliable database system."
  * *Specific*: "Specifically, PostgreSQL handles our JSON schemas and indexing requirements best."
  * *Decision*: **Preserve both**. The second sentence provides technical depth, not redundant repetition.
* **Structural Recaps & Chapter Conclusions**:
  * *Recap*: "So remember: configure the pool, set the credentials, and test the connection."
  * *Decision*: **Preserve**. Section summaries reinforce retention and mark topical transitions.
* **Dialectic Contrasts (Before vs After)**:
  * *Negative State*: "Before this setup, builds took 45 minutes."
  * *Positive State*: "With the new pipeline, builds finish in 3 minutes."
  * *Decision*: **Preserve both**.

---

## Execution Steps

### Step 1: Extract Linear Timeline Audio

Extract the master sequence audio track directly from the `.kdenlive` project file:

```bash
melt "/path/to/project.kdenlive" \
  -consumer avformat:/tmp/timeline_audio.wav \
  vn=1
```

* `-consumer avformat:... vn=1`: Renders the master audio mix with zero video decoding overhead.
* **Audio Cache Re-use**: If `/tmp/timeline_audio.wav` already exists and its duration matches the timeline sequence, reuse it directly.

**Completion criterion**: `/tmp/timeline_audio.wav` exists, is non-empty, and its duration matches the timeline sequence.

---

### Step 2: Linear Timeline Transcription

Run Whisper on the extracted timeline audio to obtain word timestamps indexed directly to timeline timecodes:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-rough-cut/scripts/transcribe.py \
  --input "/tmp/timeline_audio.wav" \
  --output "/tmp/timeline_transcript.json" \
  --model base \
  --device auto
```

* Pass `--model small` when audio clarity is low or non-English speech is present.
* **Transcript Cache Re-use**: If `/tmp/timeline_transcript.json` exists, is non-empty, and its total duration matches the project timeline, reuse it immediately to avoid redundant transcription runs.

**Completion criterion**: `/tmp/timeline_transcript.json` exists, is non-empty, and contains segments with word timestamps mapped to timeline time.

---

### Step 3: Chapter Context Audit & Proposition Collision Analysis

When a user flags a specific timecode range or asks whether a segment is justified or flow-deficient, perform a **Four-Stage Context Audit**:

#### 1. Chapter Arc Reconstruction
Never evaluate a candidate slice in isolation. Expand the transcript view across the entire chapter, rule, or thematic block. Map out the full narrative arc:
1. **Chapter Hook / Rule Statement** (e.g. *"The third rule... is to start on the level one boss."*)
2. **Conceptual Metaphor / Frame** (e.g. RPG spawning with level 1 gear vs level 100 boss).
3. **Core Principle** (e.g. Realism vs delusion; one step at a time).
4. **Concrete Example 1** (e.g. Online money: £100k goal vs £1k–£5k calibration).
5. **The Candidate Slice / Transition Bridge** (the flagged timecodes).
6. **Concrete Example 2** (e.g. Gym: 100kg bench vs 10–20 pushups).
7. **Chapter Conclusion / Key Takeaway** (e.g. Incremental progress; summary).

#### 2. Dual-Lens Editorial Diagnosis
Evaluate the flagged slice through both the creator's intent and the audience's experience:
* **Lens A: Why it Feels Justified (Speaker's Intent)**:
  * Identify what the speaker was attempting rhetorically: creating an umbrella anchor between two separate domains (e.g. bridging money to fitness), restating the metaphor, or rephrasing a point for emphasis.
* **Lens B: Why Flow Fails (Audience Experience)**:
  * **Verbatim Concept Duplication**: Repeating an opening concept without adding nuance creates dead air.
  * **Verbal Stumbles & Wrong Terms**: Mumbled words, false starts, or slip-ups (e.g. saying *"stop"* instead of *"start"*) that stall narrative momentum.
  * **Negative Imperative Pileup**: Stacking rapid negative commands within 10–15 seconds (e.g. *"Don't make it drastic..."* ➔ *"Don't aim for crazy numbers..."* ➔ *"Don't make your goal 100k bench..."*) causing listener fatigue.
  * **Pacing Contrast**: Compare the existing clunky delivery against a direct hard cut. When cutting directly from Example 1 into Example 2 produces a crisp, parallel rhythm, the bridge is redundant.

#### 3. Multi-Track Context Inspection
Inspect the `.kdenlive` MLT XML around the candidate timecodes:
* Check Track V2 (B-roll), Track A2 (ambient audio), Track V3 (motion titles), and Track A3 (SFX).
* Verify whether secondary media cues off the subsequent sentence (e.g., gym B-roll starting right at Example 2). Cutting directly to the subsequent sentence often lands secondary visuals and SFX on perfect sync cues.
* **Secondary Audio Bleed Audit (Track A2)**: If Track A2 ambient B-roll audio begins before the candidate cut boundary, verify that downstream ripple doesn't allow pre-roll audio to bleed across the cut into the preceding scene. Snap the audio in-point (`in`) and start position directly to the cut boundary ($t_{\text{cut}}$).
* **Outro Tail Decay Audit**: For final ambient B-roll audio on Track A2 near sequence end, allow the audio tail to naturally extend past the video cutaway by 2–3s with a gentle fade-out into the talking head.

#### 4. Frame-Accurate Boundary Snapping
In the project XML, inspect playlist entries (`playlist4` audio, `playlist6` video) around the candidate region. If the candidate collision corresponds to native clip cuts, snap the start and end timestamps to the exact frame boundaries of those entries:
$$\text{start\_time} = \frac{\text{start\_frame}}{\text{fps}}, \quad \text{end\_time} = \frac{\text{end\_frame}}{\text{fps}}$$

**Completion criterion**: Chapter narrative arc mapped, dual-lens diagnosis formulated, multi-track alignment verified, and exact deletion bounds snapped to clip/silence boundaries.

---

### Step 4: Triad Review Gate (User Decision)

Present each flagged collision in the structured **Triad Review Gate**. Always include full verbatim transcript text and the dual-lens diagnosis:

```markdown
### ✂️ Candidate Collision 1: [Topic Title]

**Verbatim Transcripts Side by Side**:
* **Preceding Context** `[05:37.8 ➔ 05:51.4]`:
  > *"If you've never made a penny online... Don't make it so drastic... that will just ruin your confidence."*
* **Flagged Window** `[00:05:51:24 ➔ 00:05:58:28]` (7.98s):
  * **Part A (Boss Recap)** `[05:51.4 ➔ 05:56.4]` (4.95s):
    > *"If you'll start on out a level one, focus on the lower bosses first, then build your way up to the level 100."*
  * **Part B (Verbal Stumble)** `[05:56.4 ➔ 05:59.4]` (3.03s):
    > *"So no matter what level you'll stop [start], don't be aiming for these crazy numbers."*
* **Subsequent Sentence** `[05:59.4 ➔ 06:07.4]`:
  > *"If your goal is to improve and get better in the gym, don't make your goal in a hundred K bench..."*

**Editorial Diagnosis**:
* **Why it feels justified**: Speaker attempts a conceptual callback to the video game metaphor to connect the money example to the gym example.
* **Why flow fails**: Re-explains what was stated 60 seconds earlier, contains a verbal stumble (*"stop"* for *"start"*), and produces three consecutive "Don't" commands in 15 seconds. Cutting directly from Money to Gym lands Track V2 Gym B-roll on a crisp hard cut.

**Options**:
1. Keep Take B / Prune Entire Slice (Recommended — saves 7.98s)
2. Surgical Prune (Excise Part B stumble only — saves 3.03s)
3. Keep Both (Preserve metaphor callback)
```

Collect user decisions and write the approved deletions into `/tmp/approved_deletions.json`:

```json
[
  {
    "start": 351.417,
    "end": 359.400,
    "label": "Collision 1 (Rule 3 Boss Recap & Stumble)",
    "reason": "Option 1: Prune redundant boss recap and verbal stumble between money and gym examples"
  }
]
```

**Completion criterion**: `/tmp/approved_deletions.json` exists, containing user-approved deletion entries with valid start and end timestamps.

---

### Step 5: Frame-Accurate Ripple Assembly

Execute the approved excisions using `apply_redundancy_pruning.py`:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-redundancy-pruner/scripts/apply_redundancy_pruning.py \
  --project "/path/to/project.kdenlive" \
  --deletions "/tmp/approved_deletions.json" \
  --output "/path/to/project_deduped.kdenlive"
```

The script enforces:
* **Frame-Accurate Discrete Math**: Calculates all element durations as integer frames:
  $$\text{dur\_frames} = \text{out\_frame} - \text{in\_frame} + 1$$
  Eliminates float second rounding errors and prevents accumulated frame drift across multi-track playlists.
* **Multi-Track Lockstep Slicing**: Slices all track playlists simultaneously (V1–V3, A1–A4) so B-roll and overlays remain synchronized with dialogue.
* **AVSplit Group Shifting**: Shifts frame references in `kdenlive:sequenceproperties.groups` (`track:frame:-1`) downstream of each cut so Kdenlive group pairings never drift.
* **Automated Backup**: Generates a `.bak` backup before modifying the project.

Validate the pruned output through MLT:

```bash
melt "/path/to/project_deduped.kdenlive" in=0 out=10 -consumer null
```

**Completion criterion**: `project_deduped.kdenlive` exists and executes cleanly through MLT.

---

### Step 6: Report and Launch

Present a concise summary to the user:
* Original duration vs new duration, and total time saved in seconds and frames.
* List of approved excisions with editorial rationale.
* Launch command:

```bash
kdenlive "/path/to/project_deduped.kdenlive" &
```

---

## Editorial Pitfalls & Mitigation Playbook

| Pitfall | Root Cause | Mandatory Mitigation |
| :--- | :--- | :--- |
| **Isolated Slice Fallacy** | Evaluating a 5-second candidate cut without reading the surrounding chapter arc. | **Chapter Arc Reconstruction**: Always audit the full chapter flow (Rule Hook ➔ Metaphor ➔ Example 1 ➔ Candidate ➔ Example 2 ➔ Conclusion). |
| **Accumulated Frame Drift** | Calculating entry duration as float seconds (`out - in`) without adding inclusive frame offset (`+ 1/fps`). | **Frame-Accurate Slicing**: Convert all timecodes to discrete integer frames before slicing playlists and updating tractor lengths. |
| **Analogy Erasure** | Confusing illustrative metaphors with redundant retakes. | **Rhetorical Rule**: If a sentence translates an idea into a physical or relatable comparison, preserve both. |
| **Technical Flattening** | Pruning a specific technical elaboration following a general statement. | **Depth Rule**: Preserve sentences that add specific libraries, flags, or actionable parameters. |
| **Secondary Layer Desync** | Slicing V1/A1 without checking V2 B-roll, V3 titles, and sequence groups. | **Multi-Track Inspection**: Inspect secondary tracks around cut boundaries and shift `kdenlive:sequenceproperties.groups` frame indices. |
| **Cross-Cut Audio Bleed** | Downstream B-roll audio on Track A2 pre-rolling across a cut boundary into an earlier topic. | **Cut Boundary Snapping**: Clamp Track A2 audio `in` and timeline start to the exact cut boundary $t_{\text{cut}}$, preventing acoustic bleed across edits. |
| **Abrupt Plosive Clipping** | Cutting start timestamp too close to speech onset. | **Silence Floor Snapping**: Snap deletion bounds to the audio silence floor (0.05s buffer) or exact clip entry bounds in XML. |
