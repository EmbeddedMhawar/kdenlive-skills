---
name: kdenlive-rough-cut
description: Rough-cut video footage for Kdenlive by pruning retakes, repeated words, and false starts. Use when editing talking-head videos, pruning speech stumbles or retakes, or assembling an editable Kdenlive project timeline from raw video footage.
---

# Kdenlive Rough Cut

Assemble non-destructive Kdenlive timelines from raw talking-head footage by identifying speech repetitions, false starts, and retakes, keeping only the definitive take of each thought.

## Workflow

```
[Raw Video] ──> generate_proxies.py ──> [Proxies + Audio] ──> transcribe.py ──> [Word Timestamps] ──> Agent Semantic Pruning ──> assemble_timeline.py ──> [.kdenlive + .otio]
```

### Step 0: Generate Fast Editing Proxies (Hardware-Accelerated)

For high-resolution (4K UHD) or high-framerate footage, generate lightweight editing proxies before assembling timelines to ensure zero-lag scrubbing:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-rough-cut/scripts/generate_proxies.py \
  --input "/path/to/raw_videos/" \
  --output-dir "/path/to/proxies/" \
  --width 960
```

- **Hardware Acceleration**: Automatically uses Intel QuickSync / VAAPI GPU hardware decode and encode (`scale_vaapi` + `h264_vaapi -g 60 -bf 0`) for near-zero CPU load and >2x realtime encoding.
- **Intra-frame optimization**: Uses GOP=60 and zero B-frames (`-bf 0`) so Kdenlive can seek to any frame instantaneously.
- **CPU Fallback**: Gracefully falls back to `libx264 ultrafast` if no VAAPI device is present.

---

### Step 1: Transcribe with Word Timestamps

Run the transcription helper on the raw footage:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-rough-cut/scripts/transcribe.py \
  --input "/path/to/raw_video.mp4" \
  --output "/tmp/transcript.json" \
  --model base \
  --device auto
```

- Use `--model small` or `--model medium` when audio clarity is low or non-English speech is present.
- Pass `--language <code>` (e.g. `--language en`) to enforce language detection.

**Completion criterion**: `/tmp/transcript.json` exists, is non-empty, and contains `segments` with nested `words` arrays and timestamps.

---

### Step 2: Semantic Retake and Repetition Pruning

Read `/tmp/transcript.json`. Act as the senior editor by evaluating the text and word timestamps to classify every spoken section:

#### 1. The Final Iteration Rule (Golden Rule)
When a speaker attempts or repeats a thought, phrase, or sentence multiple times across retakes, false starts, or stutter loops:
- **ALWAYS take the FINAL (LAST) iteration of the speech in the transcript.**
- **Preserve the FULL complete sentence**: Keep the definitive final take from its clean initial word (capital letter or restart) through to its full natural conclusion.
- **Discard ALL previous attempts**: Completely cut out Attempt 1, Attempt 2, etc. Never retain an early take when a subsequent take of the same sentence exists.
- **Never franken-splice across takes**: Do not take the first half of Take 1 and splice it to the second half of Take 2 when Take 2 or Take 3 contains the complete thought delivered cleanly.
- *Example*:
  - Attempt 1: *"So, you want to lock in, right?"* (discard)
  - Attempt 2: *"So, you want to lock in this year."* (discard)
  - Attempt 3: *"So, you want to lock in this winter."* -> **KEEPER (Final Iteration, full sentence)**

#### 2. Word Stumbles & Mid-Sentence Restarts
When the speaker trips on a word and restarts from the beginning of the clause or sentence (e.g. *"We need to... we need to configure the database"*):
- Cut out the initial stumble.
- Start the keeper at the exact start timestamp of the clean restart in the `words` array (*"We need to configure the database"*).

#### 3. Self-Correction Clauses (Slip-and-Repair)
Speakers frequently repair a slip of the tongue inside coordinate clauses joined by *and*, *but*, or commas by restating the predicate (e.g. *"and I knew that I wanted to be a content creator, and I knew that I wanted to go into content creation for my career"*):
- Recognize that parallel coordinate clauses with minor lexical adjustments are **live speech corrections**, not additive thoughts.
- Discard the slipped clause; start the cut directly on the definitive repaired clause (*"And I knew that I wanted to go into content creation for my career"*).

#### 4. Idea-Collisions (Nearby Retakes & Cross-Clip Re-runs)
When two candidate cuts express the same core assertion, proposition, or premise (e.g. *"The fact you're here right now tells me that you were genuinely serious about changing your life"* vs *"The fact that you're here right now tells me that you genuinely want to change your life over these next three months"*):
- Treat the earlier take as an un-pruned retake.
- Retain ONLY the final, more specific iteration. Every cut on the timeline must deliver a new, distinct progression in the narrative.
- **Punchline Upgrades**: If Take 1 gives an initial joke/premise (*"kill you in one stroke"*) and Take 2 expands it with a superior tag (*"in fact not even level 10 boss because they'll just kill you"*), **never retain both**. Completely discard Take 1.
- **Cross-Clip Example Re-runs**: Speakers frequently stop recording, start a new camera take, stumble on a transition recap, and then re-explain the exact same concrete example or financial target (e.g. repeating *"make £1,000 to £2,000 online"* across Take 5 and Take 6).
  - Always audit across clip boundaries: if Take 5 already completed the example with superior phrasing, completely discard the opening retake of Take 6 and cut directly to the subsequent distinct thought (e.g. gym example).
- **Abstract Preambles vs Concrete Anchors**: When a speaker states an abstract, vague summary (*"what a lot of people do if they have a bad day is let themselves go..."*) right before a vivid concrete example (*"if their goal is to eat clean and they have a cheat meal..."*), discard the abstract preamble. The concrete example immediately hooks the viewer and delivers the point with greater momentum.

#### 5. Off-Camera Chatter & Director Remarks
Discard conversational meta-commentary, pauses, and self-direction (e.g. *"Let me restart that"*, *"Wait, let me say that again"*, *"What was the third point?"*).

#### 6. Razor-Split Mid-Sentence Dead Air & Thought Gaps
Never treat a long sentence (>6s) as a single monolithic cut when it contains an internal hesitation or pause (>0.8s) between clauses (e.g., *"then your time... [2s pause] ...and attention is going to be split"*).
- **Razor-split the cut**: Create two separate cuts around the pause (Cut A ends before the pause, Cut B starts on the next clean word).
- Excising internal silence keeps video rhythm tight and prevents viewer drop-off.

#### 7. Filler Preamble & Breath Pruning
Speakers frequently clear their throat or use conversational runway before delivering a point (e.g., *"I know that this..."*, *"Then put in all..."*, *"is you need to..."*):
- If followed by a breath or hesitation before the core point, prune the preamble and start the cut cleanly on the main assertion (*"your time commitments..."*, *"to focus on less goals"*).
- Always place the cut start on the silence floor immediately preceding the first speech consonant (0.04s–0.06s before speech onset), cutting out pre-speech gasps, lip smacks, and tongue clicks.

#### 8. Dead Air Between Takes
Skip dead air gaps (>0.5s) between takes and pauses between distinct thoughts.

Compile the selected cuts into a JSON structure:

```json
[
  {
    "start": 10.99,
    "end": 12.37,
    "label": "Hook Take 3",
    "reason": "Final clean iteration (full sentence) of the hook"
  },
  {
    "start": 38.61,
    "end": 42.75,
    "label": "Problem statement Take 2",
    "reason": "Final clean iteration (full sentence) after first attempt"
  }
]
```

Write this list to `/tmp/cuts.json`.

**Completion criterion**: Every segment in the raw transcript is accounted for; all earlier false starts, duplicate idea collisions, and self-correction clauses are discarded; only the definitive final iteration of each full sentence is selected with word-accurate boundaries.

---

### Step 2.5: The Verification & Refinement Loop

Before assembling the timeline, ALWAYS run the audio slice verification loop:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-rough-cut/scripts/verify_cuts.py \
  --media "/path/to/raw_video.mp4" \
  --cuts "/tmp/cuts.json"
```

The script evaluates 4 diagnostic gates on each cut slice:
1. **`STRETCHED-WORD`**: Words with duration $> 0.85\text{s}$ (flags hidden stammers/restarts that Whisper smoothed out). **Action**: Razor-split the clip or trim the internal hesitation.
2. **`ACOUSTIC-DEAD-AIR`**: Internal silences $> 0.6\text{s}$ (flags long awkward pauses mid-cut). **Action**: Split the cut into two sub-cuts and remove the silence gap.
3. **`REPEAT`**: Both adjacent word stutters (`STUTTER`) and non-adjacent repeated clauses (`CLAUSE`). **Action**: Locate the clean restart timestamp and prune the earlier attempt.
4. **`CLIPPED-ONSET`**: Cut starts mid-speech (RMS $> 1200$) rather than clean silence (flags clipped vowels/plosives). **Action**: Nudge `start` earlier (0.05s–0.15s) to the silence floor.

**Convergence Rule**:
- If any cut is flagged, inspect the exact word timestamps and acoustic boundaries.
- Adjust `start` to the clean restart point or nudge it to the silence floor.
- Re-run `verify_cuts.py` until **0 cuts are flagged**.

---

### Step 2.75: Substantive Passage Deletion Review (User Decision Gate)

**CRITICAL MANDATE**: The agent must NEVER silently delete substantive ideas, instructions, arguments, case studies, or explanations (>3s or >8 words). Only obvious micro-stammers, false starts, and repeated take iterations may be pruned automatically.

Whenever a multi-word thought, instruction, or narrative section is proposed for omission:
1. **Never Prune Instructional Prompts / Operational Commands**:
   - If the speaker delivers an action step or command (e.g., *"And then simply ask it based on your goals and your inputs to make you a calendar..."*), this is ESSENTIAL information. Even if surrounded by small hesitations or pauses, NEVER delete the action instruction. Razor-split the hesitations while strictly preserving the command.
2. **Present the Triad Context Before Final Assembly**:
   For any proposed deletion of a coherent passage, present the surrounding context to the user:
   - **PREVIOUS SENTENCE**: The exact words immediately preceding the cut on the timeline.
   - **PROPOSED OMITTED PASSAGE**: The exact quoted words and timestamps proposed for deletion.
   - **NEXT SENTENCE**: The exact words immediately following the cut on the timeline.
   - **EDITORIAL RATIONALE & PROS/CONS**: Why the algorithm flagged it (e.g. perceived redundancy, pacing) vs what the video loses if removed.
3. **Solicit User Approval**:
   Give the user the ability to review and decide whether to delete, keep, or trim each candidate passage before the final timeline is written.

---

### Step 3: Assemble Non-Destructive Timeline

Run the timeline assembly helper:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-rough-cut/scripts/assemble_timeline.py \
  --media "/path/to/raw_video.mp4" \
  --cuts "/tmp/cuts.json" \
  --output "/path/to/project_roughcut.kdenlive" \
  --padding 0.08
```

- `--padding 0.08`: Applies an 80ms buffer to cut tails, preventing abrupt audio clipping on trailing syllables while automatically preventing cut overlaps. Heads are never padded backwards into discarded speech.
- **Native `AVSplit` Grouping**: The assembler automatically links every cut on V1 with its audio on A1 in `kdenlive:sequenceproperties.groups`:
  ```json
  {
    "children": [
      { "data": "1:START_FRAME:-1", "leaf": "clip", "type": "Leaf" },
      { "data": "2:START_FRAME:-1", "leaf": "clip", "type": "Leaf" }
    ],
    "type": "AVSplit"
  }
  ```
  This ensures that in Kdenlive, the **Ripple Tool (`B`)** and edge trimming move both audio and video tracks in lockstep with zero track desync.

The script produces two files:
1. `project_roughcut.kdenlive`: Native MLT XML project file.
2. `project_roughcut.otio`: OpenTimelineIO interchange file.

**Completion criterion**: Both `.kdenlive` and `.otio` files exist on disk, verified by `melt` without syntax errors.

---

### Step 4: Report Edit Decisions and Launch

Present a concise summary to the user:
- Total raw duration vs rough-cut duration (and percentage cut).
- Total retakes and stumbles pruned.
- The command to launch Kdenlive directly:

```bash
kdenlive "/path/to/project_roughcut.kdenlive" &
```

In Kdenlive, the timeline opens with each keeper clip placed sequentially. Because this is non-destructive, the user can drag clip edges to adjust handles, refine cuts, or restore discarded takes at will.

---

## Editorial Pitfalls & Mitigation Playbook

| Observed Error | Root Cause | Mandatory Mitigation |
| :--- | :--- | :--- |
| **Instructional Prompt Loss** | Trimming an entire action step (*"And then simply ask it based on your goals..."*) due to surrounding pause or stumble. | **Action Step Preservation**: Never prune operational verbs/instructions. Razor-split around the stumble while keeping the core command. |
| **Silent Passage Deletion** | Deleting substantive thoughts, proofs, or case studies without consulting the user. | **User Decision Gate (Step 2.75)**: Always present the Triad Context (Previous sentence, Proposed cut, Next sentence) for non-stutter passages. |
| **Monolithic Sentence Dead Air** | Keeping an entire sentence (>8s) intact despite 1.5s–2.1s internal thought pauses. | **Razor-Split**: Detect internal word gaps $>0.8\text{s}$ or `ACOUSTIC-DEAD-AIR` $>0.6\text{s}$; split into two separate cuts and delete the dead air. |
| **Near-Neighbor Retake Collision** | Retaining Take 1 when Take 2 upgraded the delivery, joke, or punchline. | **Strict Final Take Rule**: When two adjacent candidate cuts share a proposition, completely delete Take 1. Never keep rehearsal runs. |
| **Cross-Take Example Duplication** | Assembling a subsequent camera take that re-explains an example already delivered in an earlier take. | **Cross-Clip Audit**: Check preceding clips; if the example/premise was already delivered cleanly, discard the opening re-run of the new clip. |
| **Throat-Clearing Preambles** | Keeping conversational run-ups (*"I know that this"*, *"Then put in all"*). | **Aggressive Front-Trim**: Snap start directly to the core content word consonant, cutting pre-speech gasps and tongue clicks. |
| **Unlinked Track Desync** | Writing `groups: []` in Kdenlive XML, causing Ripple edit to move only audio or only video. | **AVSplit Pair Mapping**: Compute `timeline_start_frame` and write native `AVSplit` JSON linking track 1 and track 2 for all cuts. |
| **Trailing Syllable Clipping** | Cutting off final plosives or word tails prematurely. | **Tail Padding Buffer**: Ensure `--padding 0.08` (80ms) is preserved on tails, but NEVER pad heads backwards into discarded speech. |


