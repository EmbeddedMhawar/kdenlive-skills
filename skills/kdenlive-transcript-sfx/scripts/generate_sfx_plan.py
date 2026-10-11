#!/usr/bin/env python3
"""
generate_sfx_plan.py

Scans a linear timeline transcript (with word/segment timestamps) and/or user directives
to identify semantic, rhetorical, comedic, and literal sound design moments.
Generates an intermediate plan: /tmp/sfx_plan.json

Supports:
- Presets: youtube_dynamic (default), minecraft_theme, minimal_editorial
- Intensity levels: subtle, dynamic (default), energetic
- Word-accurate timing alignment
- Collision avoidance with pre-existing Track A3 clips (motion graphic titles)
- Pacing density limiter to prevent audio fatigue
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_SFX_DIR = Path(__file__).resolve().parent.parent / "resources" / "sfx"

# Default volumes (dB) calibrated psychoacoustically against dialogue at -12dB LUFS
DEFAULT_GAINS = {
    # Minecraft Pack (Official Mojang 48kHz WAVs)
    "minecraft/eating.wav": -14.0,
    "minecraft/eat_bite.wav": -15.0,
    "minecraft/burp.wav": -12.0,
    "minecraft/drink.wav": -14.0,
    "minecraft/classic_oof.wav": -11.0,
    "minecraft/hit_damage.wav": -12.0,
    "minecraft/fall_damage.wav": -12.0,
    "minecraft/crit_hit.wav": -13.0,
    "minecraft/shield_block.wav": -12.0,
    "minecraft/totem_pop.wav": -10.0,
    "minecraft/bow_shoot.wav": -13.0,
    "minecraft/bow_hit.wav": -13.0,
    "minecraft/level_up.wav": -12.0,
    "minecraft/orb_pickup.wav": -13.5,
    "minecraft/pop.wav": -17.0,
    "minecraft/click.wav": -18.0,
    "minecraft/wood_click.wav": -18.0,
    "minecraft/anvil_impact.wav": -11.5,
    "minecraft/anvil_break.wav": -11.0,
    "minecraft/item_break.wav": -12.0,
    "minecraft/glass_break.wav": -13.0,
    "minecraft/splash.wav": -13.0,
    "minecraft/fizz.wav": -15.0,
    "minecraft/chest_open.wav": -15.0,
    "minecraft/chest_close.wav": -15.0,
    "minecraft/door_open.wav": -15.0,
    "minecraft/door_close.wav": -15.0,
    "minecraft/tnt_fuse.wav": -12.0,
    "minecraft/tnt_explode.wav": -9.0,
    "minecraft/flint_and_steel.wav": -14.0,
    "minecraft/bell_ding.wav": -14.0,
    "minecraft/creeper_hiss.wav": -11.0,
    "minecraft/villager_huh.wav": -14.0,
    "minecraft/villager_yes.wav": -13.0,
    "minecraft/villager_no.wav": -13.0,
    "minecraft/villager_trade.wav": -13.0,
    "minecraft/zombie_groan.wav": -12.0,
    "minecraft/enderman_teleport.wav": -12.0,
    "minecraft/enderman_stare.wav": -14.0,
    "minecraft/ghast_screech.wav": -12.0,
    "minecraft/ghast_fireball.wav": -11.0,
    "minecraft/cow_moo.wav": -14.0,
    "minecraft/sheep_baa.wav": -14.0,

    # Accents Pack
    "accents/ding_bell.wav": -14.0,
    "accents/chime_subtle.wav": -15.0,
    "accents/ui_pop_clean.wav": -17.5,
    "accents/lightbulb_spark.wav": -14.0,

    # Foley Pack
    "foley/cash_register.wav": -12.5,
    "foley/camera_shutter.wav": -16.0,
    "foley/notification_ping.wav": -15.0,
    "foley/keyboard_tap.wav": -19.0,
    "foley/clock_tick.wav": -19.0,

    # Impacts Pack
    "impacts/sub_drop_heavy.wav": -8.5,
    "impacts/sub_boom_tight.wav": -9.0,
    "impacts/cinematic_hit.wav": -10.0,

    # Comedic Pack
    "comedic/record_scratch.wav": -10.5,
    "comedic/vinyl_spin_down.wav": -13.0,
    "comedic/cartoon_boing.wav": -13.0,
    "comedic/sad_trombone_wah.wav": -12.0,

    # Transitions Pack
    "transitions/whoosh_fast.wav": -13.0,
    "transitions/whoosh_deep.wav": -12.5,
    "transitions/riser_tension.wav": -14.0,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Generate semantic SFX sound design plan from transcript.")
    parser.add_argument("--transcript", "-t", type=str, required=True,
                        help="Path to timeline transcript JSON (e.g. /tmp/timeline_transcript.json).")
    parser.add_argument("--output", "-o", type=str, default="/tmp/sfx_plan.json",
                        help="Path to output sfx plan JSON.")
    parser.add_argument("--project", "-p", type=str, default=None,
                        help="Optional path to existing .kdenlive project to inspect existing Track A3 clips.")
    parser.add_argument("--motion-manifest", "-m", type=str, default=None,
                        help="Optional path to motion_manifest.json to cross-reference title SFX.")
    parser.add_argument("--preset", type=str, default="youtube_dynamic",
                        choices=["youtube_dynamic", "minecraft_theme", "minimal_editorial"],
                        help="Stylistic SFX preset profile.")
    parser.add_argument("--intensity", type=str, default="dynamic",
                        choices=["subtle", "dynamic", "energetic"],
                        help="Pacing intensity level.")
    parser.add_argument("--min-interval", type=float, default=None,
                        help="Override minimum seconds between consecutive sound effects.")
    parser.add_argument("--master-volume", type=float, default=1.0,
                        help="Master linear volume multiplier (default 1.0).")
    parser.add_argument("--custom-sfx-dir", type=str, default=None,
                        help="Optional path to custom SFX directory.")
    parser.add_argument("--user-prompts", type=str, default=None,
                        help="Optional path or JSON string of explicit user-requested SFX directives.")
    return parser.parse_args()


def parse_tc(tc_str: str, fps: float = 60.0) -> float:
    """Parse timecode string (HH:MM:SS.mmm or seconds string or frames) to float seconds."""
    tc_str = str(tc_str).strip()
    if ":" in tc_str:
        parts = tc_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    try:
        val = float(tc_str)
        # If integer-like and > 1000 without decimal point, likely frames
        return val / fps if ("." not in tc_str and val > 100) else val
    except ValueError:
        return 0.0


def parse_existing_a3_intervals(project_path: str) -> list[tuple[float, float]]:
    """Scan existing Kdenlive XML project for Track A3 (tractor7 / playlist10) entries."""
    intervals = []
    if not project_path or not os.path.exists(project_path):
        return intervals

    try:
        tree = ET.parse(project_path)
        root = tree.getroot()
        profile = root.find("profile")
        fps = 60.0
        if profile is not None:
            num = float(profile.get("frame_rate_num", "60"))
            den = float(profile.get("frame_rate_den", "1"))
            fps = num / den

        pl10 = root.find(".//playlist[@id='playlist10']")
        if pl10 is not None:
            cur_time = 0.0
            for child in pl10:
                if child.tag == "blank":
                    length_str = child.get("length", "0")
                    cur_time += parse_tc(length_str, fps)
                elif child.tag == "entry":
                    in_t = parse_tc(child.get("in", "0"), fps)
                    out_t = parse_tc(child.get("out", "0"), fps)
                    dur = max(0.02, out_t - in_t)
                    intervals.append((cur_time, cur_time + dur))
                    cur_time += dur
    except Exception as e:
        print(f"Warning: Failed to parse existing A3 clips from {project_path}: {e}", file=sys.stderr)

    return intervals


def parse_manifest_intervals(manifest_path: str) -> list[tuple[float, float]]:
    """Scan motion_manifest.json for existing title SFX intervals."""
    intervals = []
    if not manifest_path or not os.path.exists(manifest_path):
        return intervals

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for item in manifest:
            t = float(item.get("timeline_start", 0))
            dur = float(item.get("duration", 3.0))
            intervals.append((t, t + dur))
    except Exception as e:
        print(f"Warning: Failed to parse manifest from {manifest_path}: {e}", file=sys.stderr)

    return intervals


def get_sound_duration(file_path: Path) -> float:
    """Read duration from WAV file."""
    try:
        import wave
        with wave.open(str(file_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return round(frames / float(rate), 2)
    except Exception:
        return 0.5


def build_candidate_rules(preset: str):
    """Compile regex trigger rules based on selected preset."""
    rules = []

    # 1. Minecraft triggers
    if preset in ["youtube_dynamic", "minecraft_theme"]:
        rules.extend([
            # Eating & Drinking
            (
                r"\b(?:eat(?:ing)?|food|dinner|lunch|breakfast|snack|bite|chew(?:ing)?|devour(?:ing)?|taste|meal|hunger|hungry|delicious)\b",
                "minecraft/eating.wav",
                "minecraft",
                "Minecraft eating crunch sequence"
            ),
            (
                r"\b(?:burp|stuffed|satisfied|ate too much)\b",
                "minecraft/burp.wav",
                "minecraft",
                "Minecraft post-meal burp"
            ),
            (
                r"\b(?:drink(?:ing)?|coffee|sip(?:ping)?|tea|hydration|glass of water|potion)\b",
                "minecraft/drink.wav",
                "minecraft",
                "Minecraft drinking potion/bottle gulp"
            ),

            # Progression & Milestones
            (
                r"\b(?:level up|unlocked?|achievement|mastery|upgrade|next level|10x|get absurdly ahead|superpower)\b",
                "minecraft/level_up.wav",
                "minecraft",
                "Minecraft level-up celebratory chime"
            ),
            (
                r"\b(?:tiny habit|pick(?:ing)? up|grab(?:bing)?|collect(?:ing)?|small habit|tiny change|first habit)\b",
                "minecraft/orb_pickup.wav",
                "minecraft",
                "Minecraft XP orb pickup ping"
            ),
            (
                r"\b(?:quick tip|secret|hack|simple trick|one thing|rule \d+|habit \d+)\b",
                "minecraft/pop.wav" if preset == "minecraft_theme" else "accents/ding_bell.wav",
                "minecraft" if preset == "minecraft_theme" else "accents",
                "Minecraft pop / item drop tip"
            ),
            (
                r"\b(?:switch(?:ing)?|toggle|decide|make a choice|turn off|turn on)\b",
                "minecraft/click.wav",
                "minecraft",
                "Minecraft UI button click"
            ),

            # Combat, Damage & Resurrections
            (
                r"\b(?:ouch|took a hit|damage|pain|hurt|ouch|failed|lost everything|ruined|bruised|bleeding|rip)\b",
                "minecraft/classic_oof.wav",
                "minecraft",
                "Legendary Minecraft classic OOF damage grunt"
            ),
            (
                r"\b(?:critical|crit|direct hit|targeted|pinpoint|precision)\b",
                "minecraft/crit_hit.wav",
                "minecraft",
                "Minecraft critical hit strike"
            ),
            (
                r"\b(?:protect(?:ion)?|shield|defend|defense|guard(?:ed)?)\b",
                "minecraft/shield_block.wav",
                "minecraft",
                "Minecraft shield block"
            ),
            (
                r"\b(?:resurrect(?:ion)?|revive|saved (?:my|the) life|second chance|totem|miracle comeback)\b",
                "minecraft/totem_pop.wav",
                "minecraft",
                "Minecraft Totem of Undying resurrection"
            ),
            (
                r"\b(?:shoot|aim|target|arrow|bow|fired)\b",
                "minecraft/bow_shoot.wav",
                "minecraft",
                "Minecraft bow string twang"
            ),
            (
                r"\b(?:bullseye|target hit|arrow hit)\b",
                "minecraft/bow_hit.wav",
                "minecraft",
                "Minecraft arrow impact ding"
            ),

            # World & Obstacles
            (
                r"\b(?:hard truth|brutal|level 1 boss|destroy(?:ed|s)?|crush(?:ed)?|fatal mistake|punishment)\b",
                "minecraft/anvil_impact.wav",
                "minecraft",
                "Minecraft heavy anvil crash"
            ),
            (
                r"\b(?:explod(?:e|ing|ed)|blow up|bomb|blast|shattered|tnt)\b",
                "minecraft/tnt_explode.wav",
                "minecraft",
                "Minecraft TNT explosion"
            ),
            (
                r"\b(?:fuse|ticking away|about to blow|time bomb)\b",
                "minecraft/tnt_fuse.wav",
                "minecraft",
                "Minecraft TNT fuse hiss"
            ),
            (
                r"\b(?:creeper|sneaking up|disaster waiting|ambush)\b",
                "minecraft/creeper_hiss.wav",
                "minecraft",
                "Minecraft creeper hiss"
            ),
            (
                r"\b(?:splash|dive in|jumped in|water|swim(?:ming)?|plunge)\b",
                "minecraft/splash.wav",
                "minecraft",
                "Minecraft water splash"
            ),
            (
                r"\b(?:chest|unlocked? the box|treasure|vault|inventory)\b",
                "minecraft/chest_open.wav",
                "minecraft",
                "Minecraft chest open creak"
            ),
            (
                r"\b(?:door|walk in|stepped inside|welcome in)\b",
                "minecraft/door_open.wav",
                "minecraft",
                "Minecraft wooden door open"
            ),
            (
                r"\b(?:broke|broken tool|snapped|wore out)\b",
                "minecraft/item_break.wav",
                "minecraft",
                "Minecraft tool break crack"
            ),

            # Mobs & Reactions
            (
                r"\b(?:huh\??|makes no sense|why would you|wait what|makes zero sense|puzzled)\b",
                "minecraft/villager_huh.wav",
                "minecraft",
                "Minecraft puzzled villager 'huh'"
            ),
            (
                r"\b(?:deal|trade|agreed|sold|accepted|fair trade)\b",
                "minecraft/villager_trade.wav",
                "minecraft",
                "Minecraft villager trade haggle"
            ),
            (
                r"\b(?:no way|rejected|refused|declined|not happening)\b",
                "minecraft/villager_no.wav",
                "minecraft",
                "Minecraft disapproving villager 'no'"
            ),
            (
                r"\b(?:zombie|brainless|mindless|exhausted|sleepwalking|drained zombie)\b",
                "minecraft/zombie_groan.wav",
                "minecraft",
                "Minecraft zombie groan"
            ),
            (
                r"\b(?:teleport(?:ed)?|vanish(?:ed)?|disappear(?:ed)?|out of nowhere)\b",
                "minecraft/enderman_teleport.wav",
                "minecraft",
                "Minecraft Enderman teleport vwoop"
            ),
            (
                r"\b(?:screaming|screech|panic mode|nightmare)\b",
                "minecraft/ghast_screech.wav",
                "minecraft",
                "Minecraft Ghast screech"
            ),
            (
                r"\b(?:holy cow|cow|cattle)\b",
                "minecraft/cow_moo.wav",
                "minecraft",
                "Minecraft cow moo"
            ),
        ])

    # 2. Accents triggers
    if preset in ["youtube_dynamic", "minimal_editorial"]:
        rules.extend([
            (
                r"\b(?:the (?:golden )?rule is|key principle|core lesson|main takeaway|remember this|takeaway)\b",
                "accents/ding_bell.wav",
                "accents",
                "Key rule / principle desk bell"
            ),
            (
                r"\b(?:realiz(?:e|ed|ation)|suddenly understand|aha|it clicked|dawned on me)\b",
                "accents/chime_subtle.wav",
                "accents",
                "Aha moment realization chime"
            ),
            (
                r"\b(?:epiphany|lightbulb|idea struck|spark)\b",
                "accents/lightbulb_spark.wav",
                "accents",
                "Idea lightbulb spark"
            ),
            (
                r"\b(?:clean|smooth|seamless|effortless)\b",
                "accents/ui_pop_clean.wav",
                "accents",
                "Clean UI accent pop"
            ),
        ])

    # 3. Literal Foley Metaphors
    if preset in ["youtube_dynamic", "minecraft_theme"]:
        rules.extend([
            (
                r"\b(?:money|dollars?|cash|wealth|rich|profit|income|millions?|pay(?:ing)?|cost(?:s|ing)?|financial(?:ly)?)\b",
                "foley/cash_register.wav",
                "foley",
                "Financial metaphor cash register"
            ),
            (
                r"\b(?:photo(?:s)?|camera|instagram|screenshot|snapshot|picture)\b",
                "foley/camera_shutter.wav",
                "foley",
                "Visual capture camera shutter"
            ),
            (
                r"\b(?:phone|notifications?|text(?:ing)?|message|slack|inbox|email|dm)\b",
                "foley/notification_ping.wav",
                "foley",
                "Digital communication notification ping"
            ),
            (
                r"\b(?:writ(?:e|ing)|journal(?:ing)?|typ(?:e|ing)|code|coding|draft)\b",
                "foley/keyboard_tap.wav",
                "foley",
                "Writing / typing mechanical switch"
            ),
            (
                r"\b(?:every single day|clock|routine|schedule|deadline|time flies|seconds|hours)\b",
                "foley/clock_tick.wav",
                "foley",
                "Time / pacing clock tick"
            ),
        ])

    # 4. Dramatic & Comedic
    if preset in ["youtube_dynamic", "minecraft_theme"]:
        rules.extend([
            (
                r"\b(?:except (?:it doesn't|it isn't|no)|plot twist|wrong|here's the catch|worst part|actually no)\b",
                "comedic/record_scratch.wav",
                "comedic",
                "Plot twist / awkward realization record scratch"
            ),
            (
                r"\b(?:stop doing (?:this|that)|quit(?:ting)?|shut down|burnout|gave up)\b",
                "comedic/vinyl_spin_down.wav",
                "comedic",
                "Momentum halt turntable spin down"
            ),
            (
                r"\b(?:single most important|massive change|game changer|radical|life-changing)\b",
                "impacts/sub_drop_heavy.wav",
                "impacts",
                "Heavy emphasis sub-bass drop"
            ),
        ])

    # 5. Transitions
    rules.extend([
        (
            r"\b(?:now let's move|moving on|next up|the next step|step \d+|part \d+|chapter \d+)\b",
            "transitions/whoosh_fast.wav",
            "transitions",
            "Section pivot fast whip whoosh"
        ),
        (
            r"\b(?:and here is why|the real reason|what happens next|leading up to)\b",
            "transitions/riser_tension.wav",
            "transitions",
            "Narrative anticipation tension riser"
        ),
    ])

    return rules


def locate_word_timestamp(segment: dict, match_phrase: str) -> float:
    """Find exact start timestamp of matched phrase within segment."""
    seg_start = float(segment.get("start", 0.0))
    seg_end = float(segment.get("end", seg_start + 1.0))
    seg_text = segment.get("text", "")
    words = segment.get("words", [])

    if not words:
        # Interpolate proportionally based on character position
        m = re.search(re.escape(match_phrase), seg_text, re.IGNORECASE)
        if m and len(seg_text) > 0:
            ratio = m.start() / max(1, len(seg_text))
            return round(seg_start + ratio * (seg_end - seg_start), 2)
        return round(seg_start, 2)

    # Word-level matching
    first_word = match_phrase.split()[0].lower()
    for w in words:
        w_clean = re.sub(r"[^\w]", "", w.get("word", "").lower())
        if w_clean == first_word:
            return round(float(w.get("start", seg_start)), 2)

    return round(seg_start, 2)


def generate_plan():
    args = parse_args()
    transcript_path = Path(args.transcript)
    output_path = Path(args.output)
    sfx_base_dir = Path(args.custom_sfx_dir) if args.custom_sfx_dir else DEFAULT_SFX_DIR

    if not transcript_path.exists():
        print(f"Error: Transcript file not found at {transcript_path}", file=sys.stderr)
        sys.exit(1)

    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        segments = data
    else:
        segments = data.get("segments", [])

    # Minimum interval configuration
    if args.min_interval is not None:
        min_interval = float(args.min_interval)
    else:
        min_interval = {"subtle": 14.0, "dynamic": 8.0, "energetic": 4.5}[args.intensity]

    # Existing Track A3 intervals to avoid collision
    existing_a3 = parse_existing_a3_intervals(args.project)
    if args.motion_manifest:
        existing_a3.extend(parse_manifest_intervals(args.motion_manifest))

    rules = build_candidate_rules(args.preset)
    candidates = []

    # 1. Parse manual user prompts if provided
    if args.user_prompts:
        try:
            if os.path.exists(args.user_prompts):
                with open(args.user_prompts, "r", encoding="utf-8") as uf:
                    user_directives = json.load(uf)
            else:
                user_directives = json.loads(args.user_prompts)
            for d in user_directives:
                candidates.append({
                    "time": float(d.get("time", d.get("timeline_start", 0))),
                    "sfx_rel": d.get("sfx", d.get("sfx_path", "accents/ding_bell.wav")),
                    "category": d.get("category", "user"),
                    "phrase": d.get("phrase", "user prompt"),
                    "reason": d.get("reason", "Explicit user directive"),
                    "manual": True
                })
        except Exception as e:
            print(f"Warning: Failed to parse user prompts: {e}", file=sys.stderr)

    # 2. Scan transcript segments against rules
    for seg in segments:
        text = seg.get("text", "")
        for pat, sfx_rel, category, reason in rules:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                matched_phrase = m.group(0).strip()
                t_exact = locate_word_timestamp(seg, matched_phrase)
                candidates.append({
                    "time": t_exact,
                    "sfx_rel": sfx_rel,
                    "category": category,
                    "phrase": matched_phrase,
                    "reason": f"{reason} for '{matched_phrase}'",
                    "manual": False
                })

    # Sort candidates strictly by time
    candidates.sort(key=lambda c: c["time"])

    # 3. Pacing and collision filter
    plan = []
    last_placed_time = -999.0
    item_id = 1

    for cand in candidates:
        t = cand["time"]
        sfx_rel = cand["sfx_rel"]
        sfx_full = sfx_base_dir / sfx_rel

        # Check collision with existing A3 clips
        collision = False
        for ex_start, ex_end in existing_a3:
            if (ex_start - 1.5) <= t <= (ex_end + 1.5):
                collision = True
                break
        if collision and not cand.get("manual", False):
            continue

        # Check pacing interval
        if not cand.get("manual", False) and (t - last_placed_time) < min_interval:
            continue

        # Validated event
        dur = get_sound_duration(sfx_full) if sfx_full.exists() else 0.5
        default_db = DEFAULT_GAINS.get(sfx_rel, -14.0)

        plan.append({
            "id": f"sfx_{item_id:03d}",
            "timeline_start": round(t, 2),
            "duration": round(dur, 2),
            "sfx_path": str(sfx_rel),
            "full_path": str(sfx_full),
            "category": cand["category"],
            "volume_db": round(default_db, 1),
            "trigger_phrase": cand["phrase"],
            "reason": cand["reason"]
        })
        last_placed_time = t
        item_id += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    print(f"Generated sound design plan: {len(plan)} events written to {output_path}")
    print(f"Preset: {args.preset} | Pacing interval: {min_interval:.1f}s | Existing A3 collisions filtered: {len(existing_a3)}")


if __name__ == "__main__":
    generate_plan()
