---
name: kdenlive-transcript-sfx
description: Add transcript-driven sound effects, punctuation accents, literal Foley, and Minecraft cues to Kdenlive video projects. Use when sound-designing talking-head speech, punctuating punchlines and rules, or adding audio retention hooks.
---

# Kdenlive Transcript Sound Design & SFX

Enrich Kdenlive timelines with speech-synchronized sound effects, semantic punctuation, literal Foley metaphors, and iconic Minecraft cues placed on **Track A3** without interrupting dialogue on **Track A1**.

## Timeline Architecture

```
Tracks:
  V3 ── Motion Graphics, Chapter Cards & Kinetic Titles
  V2 ── B-Roll Footage & Inserts
  V1 ── Master A-Roll (talking-head footage from rough-cut & zoom-cuts)
  ─────────────────────────────────────────────────────────────────────────────
  A1 ── Primary Dialogue Speech (continues uninterrupted)
  A2 ── B-Roll / Secondary Audio Foley (-20dB to -24dB)
  A3 ── Synchronized SFX (Motion title hits + Transcript accents & Minecraft SFX)
  A4 ── Music Bed (optional)
```

---

## Workflow

```
[Master Timeline .kdenlive]
       │
       ▼ (Step 1: Ingest Transcript & Directives)
[timeline_transcript.json] ──> generate_sfx_plan.py
       │
       ▼ (Step 2: User Approval Gate)
[/tmp/sfx_plan.json]
       │
       ▼ (Step 3: verify_sfx_plan.py)
[Linted Sound Plan]
       │
       ▼ (Step 4: apply_sfx.py)
[project_roughcut_sfx.kdenlive] (Track A3 Injected & Coexisting)
       │
       ▼ (Step 5: Editorial Review)
[kdenlive project_roughcut_sfx.kdenlive]
```

---

### Step 1: Detect Key Moments & Draft Plan

Scan the linear timeline transcript to detect rhetorical milestones, punchlines, comedic pauses, literal metaphors, and Minecraft progression cues:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-transcript-sfx/scripts/generate_sfx_plan.py \
  --transcript "/path/to/timeline_transcript.json" \
  --output "/tmp/sfx_plan.json" \
  --project "/path/to/project.kdenlive" \
  --preset "youtube_dynamic" \
  --intensity "dynamic"
```

- `--transcript <path>`: Linear timeline transcript with word or segment timestamps.
- `--project <path>`: Existing `.kdenlive` project file. The script reads Track A3 (`playlist10`) to identify existing title SFX and enforce a $\pm 1.5\text{s}$ buffer preventing audio clutter.
- `--preset <name>`: Stylistic profile:
  - `youtube_dynamic`: Balanced modern YouTube sound design (accents + literal Foley + iconic Minecraft pops/level-ups).
  - `minecraft_theme`: Richer gaming/productivity palette featuring Minecraft XP orbs, anvils, clicks, and pops.
  - `minimal_editorial`: Elegant desk bells, subtle chimes, and gentle air whooshes for corporate or quiet storytelling.
- `--intensity <mode>`: Pacing density budget:
  - `subtle`: Conservative sound design ($\ge 14.0\text{s}$ spacing).
  - `dynamic`: Default balanced pacing ($\ge 8.0\text{s}$ spacing).
  - `energetic`: High-engagement punchy pacing ($\ge 4.5\text{s}$ spacing).
- `--min-interval <sec>`: Explicit spacing override in seconds.
- `--master-volume <float>`: Global linear gain multiplier (default: `1.0`).
- `--custom-sfx-dir <path>`: Path to user's personal SFX library directory.
- `--user-prompts <json|path>`: Explicit timestamp sound directives requested by the user.

**Completion criterion**: `/tmp/sfx_plan.json` exists, is non-empty, and contains structured sound event entries.

---

### Step 2: Semantic Review & User Approval Gate

Review `/tmp/sfx_plan.json` before applying to the project timeline. Ensure every sound cue serves a clear editorial purpose:

1. **Rhetorical Accents (`accents/`)**:
   - Hotel desk bells (`ding_bell.wav`) land on spoken rules (*"Rule 1"*, *"The golden rule"*).
   - Sparkling chimes (`chime_subtle.wav`) punctuate realizations (*"I finally realized"*, *"It clicked"*).
2. **Minecraft Sound Design (`minecraft/`)**:
   - Triumphant level-up (`level_up.wav`) on milestones (*"get absurdly ahead"*, *"superpower"*, *"10x"*).
   - XP orb ding (`orb_pickup.wav`) on small daily wins (*"tiny habit"*, *"pick up this one trick"*).
   - Anvil impact (`anvil_impact.wav`) on hard truths or obstacles (*"fatal mistake"*, *"level 1 boss"*).
   - Villager 'huh' (`villager_huh.wav`) on comedic skepticism (*"makes zero sense"*, *"wait what"*).
   - Item break (`item_break.wav`) on broken habits or shattered streaks (*"if you fail one day"*, *"streak breaks"*).
3. **Literal Foley Metaphors (`foley/`)**:
   - Cash register (`cash_register.wav`) on financial terms (*"money"*, *"millions"*, *"cost"*).
   - Notification ping (`notification_ping.wav`) on digital cues (*"phone"*, *"message"*, *"slack"*).
   - Mechanical keyboard (`keyboard_tap.wav`) on writing (*"journal"*, *"code"*, *"typing"*).
   - Clock tick (`clock_tick.wav`) on relentless daily discipline (*"every single day"*).
   - Beverage sip (`drink.wav`) on warm contextual lifestyle moments (*"coffee with your grandparents"*).
4. **Dramatic & Comedic (`comedic/`, `impacts/`)**:
   - Vinyl record scratch (`record_scratch.wav`) on sudden plot twists (*"wrong"*, *"actually no"*).
   - 808 sub-bass drop (`sub_drop_heavy.wav`) on heavyweight emphasis (*"single most important"*).

---

### Step 2.5: The Editorial Curation & Pruning Gate (The 60% Rule)

In high-retention video editing, **less is more**. Automated draft scans frequently over-populate the timeline with sound cues (e.g. drafting 18 cues across a 10-minute video). A mandatory second-pass audit must prune candidate cues down to a curated core (~60% reduction, leaving 6–8 total cues).

#### The Five Laws of Sound Pruning (Why Drafted Cues Are Cut):
1. **The SFX Fatigue Law (No Asset Repetition)**:
   - *Draft Mistake*: Spreading `cash_register.wav` across 4 separate financial mentions (hook at 12s, 118s, 343s, 572s).
   - *Why It Fails*: Repeating the same novelty sound effect trains the audience's brain to hear it as cheap, spammy soundboard clutter.
   - *Editorial Decision*: **Keep only the first instance in the hook** to establish energy and stakes. Delete all 3 subsequent occurrences.
2. **The Tonal Incongruity Law (Anti-Cringe / Tone Protection)**:
   - *Draft Mistake*: Inserting Minecraft `eating.wav` on phrases like *"eat clean"* or *"cheat meal and had a burger"*.
   - *Why It Fails*: Literal cartoon chewing sounds during a serious discussion about fitness discipline undermine the creator's authority and sound juvenile/cringe.
   - *Editorial Decision*: **Delete cartoonish/literal eating sounds** during serious advice. Sound must match the speaker's emotional gravity.
3. **The Trope Elimination Law (Banish Outdated Clichés)**:
   - *Draft Mistake*: Placing `record_scratch.wav` on casual conversational hedges like *"Now don't get me wrong"*.
   - *Why It Fails*: Vinyl record scratches are an overused 2016 YouTube meme trope. In modern, premium educational video, they stall rhythm and feel dated.
   - *Editorial Decision*: **Delete record scratches** unless the creator delivers a sharp, deliberate comedic sketch.
4. **The Acoustic Low-End Hygiene Law**:
   - *Draft Mistake*: Dropping `sub_drop_heavy.wav` on spoken words like *"life-changing"* without a visual scene transition.
   - *Why It Fails*: Heavy 808 sub drops produce low-frequency acoustic mud that clouds vocal clarity unless paired with an impactful full-screen graphic or chapter card transition.
   - *Editorial Decision*: **Prune standalone sub-drops** during continuous talking-head speech. Reserve sub-hits strictly for full-screen chapter card bumpers.
5. **The Unobtrusive Organic Foley Law (What Survives)**:
   - What survived the cut in master production:
     - `cash_register.wav` (1x in hook): Delivers punchy opening hook retention.
     - `classic_oof.wav` (1x on *"fail and give up"*): Relatable, punchline humor that punctuates the fail state.
     - `item_break.wav` (1x on *"streak breaks"*): Perfect auditory metaphor for a shattered discipline streak.
     - `clock_tick.wav` (2x on *"every single day"*): Subtle, rhythmic, unobtrusive Foley reinforcing routine without competing with speech.
     - `drink.wav` (1x on *"coffee"*): Quiet, warm, natural lifestyle atmosphere.
     - `keyboard_tap.wav` (1x on *"two minutes to write"*): Ultra-short tactile Foley grounding the action.

Present the curated summary table (timestamp, trigger phrase, sound choice, and volume) to the user for approval. If the user requests tweaks to timing, volume, or sound selection, edit `/tmp/sfx_plan.json`.

---

### Step 3: Lint & Verify Plan

Validate the sound plan through the structural linter before modifying the project file:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-transcript-sfx/scripts/verify_sfx_plan.py \
  --plan "/tmp/sfx_plan.json" \
  --project "/path/to/project.kdenlive"
```

The linter verifies 5 structural gates:
1. **`TIMECODE-BOUNDS`**: All timestamps are $\ge 0.0\text{s}$ and chronological.
2. **`DURATION-RANGE`**: Durations are within valid audio bounds ($0.02\text{s}$ to $15.0\text{s}$).
3. **`GAIN-BOUNDS`**: Target gains reside in safe range ($-35.0\text{dB} \le \text{gain} \le 0.0\text{dB}$).
4. **`AUDIO-FILE-EXISTENCE`**: Every sound file exists on disk as a readable 48kHz WAV.
5. **`COLLISION-FREE`**: No two sound effects collide, and no overlap exists with existing Track A3 clips.

**Completion criterion**: `verify_sfx_plan.py` reports `Verification PASSED: 0 blocking issues`.

---

### Step 4: Non-Destructive Timeline Assembly

Inject the sound effects into the master Kdenlive timeline XML:

```bash
~/.gemini/config/plugins/kdenlive/skills/kdenlive-transcript-sfx/scripts/apply_sfx.py \
  --project "/path/to/project_motion.kdenlive" \
  --plan "/tmp/sfx_plan.json" \
  --output "/path/to/project_sfx.kdenlive"
```

- Injects audio producer chains and entries onto **Track A3** (`tractor7` / `playlist10`).
- Interleaves new transcript SFX into gaps around existing motion graphics clips without deleting or clipping existing titles.
- Enforces the stable 6-track timeline schema (V1–V3, A1–A3) to ensure Kdenlive GUI stability.
- Attaches sample-accurate MLT volume filters calibrated to target dB levels.
- Runs `melt` syntax validation to verify XML integrity.

**Completion criterion**: `project_sfx.kdenlive` exists on disk and passes `melt` validation with 0 errors.

---

### Step 5: Launch & Editorial Review

Launch the assembled timeline in Kdenlive for visual and auditory review:

```bash
kdenlive "/path/to/project_sfx.kdenlive" &
```

Report to the user:
- Total transcript sound effects injected.
- Category breakdown (Minecraft, Accents, Foley, Comedic, Impacts).
- Coexistence status with pre-existing Track A3 clips.

---

## Sound Palette & Library

| Category | File | Trigger Context | Default Gain | Sound Character |
| :--- | :--- | :--- | :--- | :--- |
| **Minecraft** | `minecraft/eating.wav` | Food, hunger, meals (*"food"*, *"eat"*, *"delicious"*) | `-14.0 dB` | Authentic multi-bite crunchy eating sequence |
| **Minecraft** | `minecraft/burp.wav` | Post-meal satisfaction (*"burp"*, *"stuffed"*) | `-12.0 dB` | Classic Minecraft post-meal burp |
| **Minecraft** | `minecraft/drink.wav` | Hydration, coffee, tea (*"coffee"*, *"drink"*, *"sip"*) | `-14.0 dB` | Potion / bottle gulping sound |
| **Minecraft** | `minecraft/classic_oof.wav` | Damage, failure, pain (*"ouch"*, *"failed"*, *"ruined"*) | `-11.0 dB` | Legendary original Minecraft player damage grunt |
| **Minecraft** | `minecraft/totem_pop.wav` | Miracles, revivals (*"saved my life"*, *"second chance"*) | `-10.0 dB` | Majestic Totem of Undying resurrection fanfare |
| **Minecraft** | `minecraft/crit_hit.wav` | Precision, sharp focus (*"critical"*, *"targeted"*) | `-13.0 dB` | Swept particle critical hit sound |
| **Minecraft** | `minecraft/shield_block.wav`| Defense, protection (*"shield"*, *"protect"*) | `-12.0 dB` | Solid shield impact block |
| **Minecraft** | `minecraft/tnt_explode.wav` | Sudden blowups, chaos (*"explode"*, *"blast"*) | `-9.0 dB` | Deep TNT explosion rumble |
| **Minecraft** | `minecraft/creeper_hiss.wav`| Lurking dangers (*"sneaking up"*, *"creeper"*) | `-11.0 dB` | Iconic primed creeper hiss |
| **Minecraft** | `minecraft/orb_pickup.wav` | Small habits, micro-wins (*"tiny habit"*) | `-13.5 dB` | High-pitched dual-tone XP orb ping |
| **Minecraft** | `minecraft/level_up.wav` | Mastery, breakthroughs (*"get ahead"*, *"10x"*) | `-12.0 dB` | 5-note rising arpeggiated celebratory chime |
| **Minecraft** | `minecraft/pop.wav` | Fast tips, idea drops (*"quick tip"*, *"hack"*) | `-17.0 dB` | Hollow wooden/bubble item drop chirp |
| **Minecraft** | `minecraft/click.wav` | Choices, toggles (*"switch"*, *"decide"*) | `-18.0 dB` | Wooden UI button mechanical click |
| **Minecraft** | `minecraft/anvil_impact.wav` | Hard obstacles, harsh truths (*"brutal"*) | `-11.5 dB` | Heavy metallic ring and low thud |
| **Minecraft** | `minecraft/splash.wav` | Diving in, immersion (*"dive in"*, *"plunge"*) | `-13.0 dB` | Water surface impact splash |
| **Minecraft** | `minecraft/villager_huh.wav` | Skepticism, confusion (*"makes no sense"*) | `-14.0 dB` | Puzzled nasal acoustic vocalization |
| **Minecraft** | `minecraft/villager_trade.wav`| Agreements, closed deals (*"deal"*, *"trade"*) | `-13.0 dB` | Affirmative villager haggle chime |
| **Minecraft** | `minecraft/villager_no.wav` | Rejections, refusals (*"no way"*, *"declined"*) | `-13.0 dB` | Grumbling disapproving villager 'no' |
| **Accents** | `accents/ding_bell.wav` | Rules, principles (*"the golden rule"*) | `-14.0 dB` | Crystalline hotel desk bell ring |
| **Accents** | `accents/chime_subtle.wav` | Realizations (*"it clicked"*, *"aha"*) | `-15.0 dB` | Gentle sparkling harmonic shimmer |
| **Accents** | `accents/ui_pop_clean.wav` | Clean execution, modern UI actions | `-17.5 dB` | Crisp minimalist glass bubble pop |
| **Foley** | `foley/cash_register.wav` | Wealth, costs (*"money"*, *"millions"*) | `-12.5 dB` | Mechanical drawer roll + bright bell |
| **Foley** | `foley/camera_shutter.wav` | Visuals, photos (*"instagram"*, *"screenshot"*) | `-16.0 dB` | Dual-curtain DSLR mirror flip |
| **Foley** | `foley/notification_ping.wav`| Devices, messages (*"phone"*, *"slack"*) | `-15.0 dB` | Clean two-tone marimba notification |
| **Foley** | `foley/keyboard_tap.wav` | Writing, studying (*"journal"*, *"code"*) | `-19.0 dB` | Tactile switch mechanical keypress |
| **Foley** | `foley/clock_tick.wav` | Time pressure, schedules (*"every day"*) | `-19.0 dB` | Precision mechanical clock escapement |
| **Impacts** | `impacts/sub_drop_heavy.wav` | Huge emphasis (*"single most important"*) | `-8.5 dB` | Deep 808 sub-bass frequency drop |
| **Comedic** | `comedic/record_scratch.wav`| Plot twists, awkward stops (*"actually no"*) | `-10.5 dB` | Vinyl needle scrape / sudden stop |
| **Transitions** | `transitions/whoosh_fast.wav`| Topic pivots (*"next up"*, *"step two"*) | `-13.0 dB` | Quick airy whip-pan whoosh |

---

## Editorial Playbook & Pitfalls

| Potential Error | Root Cause | Mandatory Mitigation |
| :--- | :--- | :--- |
| **Dialogue Drowning** | SFX mixed at default $0\text{dB}$, competing with spoken dialogue at $-12\text{dB}$ LUFS. | **Psychoacoustic Calibration**: Enforce category target gains ($-8.5\text{dB}$ to $-19.0\text{dB}$). High-pitched dings sit at $-14\text{dB}$; subtle clicks sit at $-19\text{dB}$. |
| **Sound Fatigue** | Placing SFX on every minor word, creating a chaotic wall of noise. | **Pacing Density Limiter**: Enforce `--intensity dynamic` ($\ge 8\text{s}$ spacing) or `--intensity subtle` ($\ge 14\text{s}$ spacing). |
| **Repeated Asset Fatigue** | Spamming the same sound effect (e.g. 4x `cash_register.wav`) across a video. | **The SFX Fatigue Law**: Keep maximum 1 occurrence in the hook; delete subsequent repetitions to prevent soundboard fatigue. |
| **Tonal Incongruity / Cartoon Foley** | Playing comedic/cartoon sounds (e.g. Minecraft `eating.wav`) over serious discipline/diet advice. | **Anti-Cringe Tone Protection**: Delete comical eating/burping Foley during serious advice; sound must match creator gravity. |
| **Acoustic Low-End Mud** | Dropping raw 808 sub-bass drops under continuous talking-head speech. | **Acoustic Low-End Hygiene**: Reserve sub-drops strictly for full-screen chapter transitions (Track V3), never naked speech. |
| **Track Collision on A3** | Overwriting existing motion title whooshes on Track A3 (`playlist10`). | **Collision Detection & Interleaving**: `generate_sfx_plan.py` checks existing A3 clips and yields ($\pm 1.5\text{s}$ buffer); `apply_sfx.py` cleanly interleaves entries into blanks. |
| **Kdenlive GUI Crash on Launch** | Creating Track A4 or custom track indices $>6$, triggering OpenTimelineIO `loadGroups` segfault. | **Strict 6-Track Schema**: Always target Track A3 (`tractor7` / `playlist10`) within the stable 6-track architecture (V1–V3, A1–A3). |
| **Word Misalignment** | Triggering SFX at the start of a multi-second sentence rather than when the trigger word is spoken. | **Word-Level Timestamping**: `locate_word_timestamp()` pinpoints exact sub-second word start times within transcript segments. |
