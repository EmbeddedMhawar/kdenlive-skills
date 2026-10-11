#!/usr/bin/env python3
"""
generate_motion_plan.py

Scans a linear timeline transcript (with word timestamps) and/or user directives
to identify key editorial moments (hooks, chapter transitions, rule introductions,
recap lists, and user callouts). Generates an intermediate semantic plan:
/tmp/motion_plan.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate semantic motion graphics plan from timeline transcript.")
    parser.add_argument("--transcript", "-t", type=str, required=True,
                        help="Path to timeline transcript JSON (e.g. /tmp/timeline_transcript.json).")
    parser.add_argument("--output", "-o", type=str, default="/tmp/motion_plan.json",
                        help="Path to output motion plan JSON.")
    parser.add_argument("--font", type=str, default="Clarify-Blk",
                        help="Default typography font family (e.g. Clarify-Blk, Montserrat, Cabinet Grotesk).")
    parser.add_argument("--theme", type=str, default="cyber_dark",
                        choices=["cyber_dark", "mesh_blue", "ai_hybrid", "minimal_white"],
                        help="Default visual theme profile.")
    parser.add_argument("--bg-engine", type=str, default="programmatic",
                        choices=["programmatic", "ai_programmatic"],
                        help="Background generator mode for full-screen cards.")
    parser.add_argument("--user-prompts", type=str, default=None,
                        help="Optional JSON file or string of explicit user-requested titles.")
    return parser.parse_args()


# Common trigger patterns in productivity / talking-head videos
CHAPTER_PATTERNS = [
    r"\b(?:rule|habit|step|principle|tip|lesson|secret|hack)\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b",
    r"\bchapter\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b",
    r"\bpart\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b",
    r"\bfirst(?:ly)?\b",
    r"\bsecond(?:ly)?\b",
    r"\bthird(?:ly)?\b",
    r"\bfourth(?:ly)?\b",
    r"\bfifth(?:ly)?\b",
]

HOOK_PATTERNS = [
    r"\b(\d+\s+[\w\s]{4,35}\s+(?:ahead|life|years|productive|change|habits|mistakes|rules))\b",
    r"\b(how to\s+[\w\s]{6,35})\b",
    r"\b(the single most important\s+[\w\s]{4,30})\b",
]


def clean_text(text: str) -> str:
    text = re.sub(r"[^\w\s\-\'\"]", "", text).strip()
    return " ".join(text.split())


def extract_key_moments(segments, default_font="Clarify-Blk", theme="cyber_dark", bg_engine="programmatic"):
    plan = []
    
    # 1. Check Hook (first 30 seconds)
    first_30s_text = " ".join([s.get("text", "") for s in segments if s.get("start", 0) < 30.0])
    for pat in HOOK_PATTERNS:
        m = re.search(pat, first_30s_text, re.IGNORECASE)
        if m:
            hook_text = m.group(1).strip()
            # Find approximate start
            hook_start = 1.5
            for s in segments:
                if hook_text.lower()[:15] in s.get("text", "").lower():
                    hook_start = max(0.5, s.get("start", 1.5))
                    break
            
            plan.append({
                "id": "item_001_hook",
                "timeline_start": round(hook_start, 2),
                "duration": 4.5,
                "visual_mode": "inframe_overlay",
                "background": "transparent",
                "layout": "kinetic_multiscale",
                "tag": "",
                "text": hook_text.title(),
                "font": default_font,
                "accent_color": "#FFD700",
                "text_color": "#FFFFFF",
                "animation_style": "elastic_pop",
                "sfx_profile": "whoosh",
                "sfx_volume": 0.85,
                "reason": f"Video hook emphasis: '{hook_text}'"
            })
            break

    # 2. Check Chapters, Rules, and Habits
    item_counter = 2
    for seg in segments:
        text = seg.get("text", "")
        start = seg.get("start", 0.0)
        
        for pat in CHAPTER_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                matched_label = m.group(0).strip().upper()
                # Find context words following the label
                idx = text.lower().find(m.group(0).lower())
                sub_text = text[idx + len(m.group(0)):].strip()
                words = sub_text.split()
                headline = " ".join(words[:6]) if words else matched_label
                headline = clean_text(headline).title()
                if not headline:
                    headline = matched_label
                
                # Determine background based on user theme & engine
                if bg_engine == "ai_programmatic":
                    bg = "ai_programmatic"
                else:
                    bg = "cyber_grid" if theme == "cyber_dark" else "mesh_gradient"
                
                plan.append({
                    "id": f"item_{item_counter:03d}_chapter",
                    "timeline_start": round(start, 2),
                    "duration": 3.0,
                    "visual_mode": "fullscreen_card",
                    "background": bg,
                    "layout": "stacked_card",
                    "tag": matched_label,
                    "text": headline,
                    "font": default_font,
                    "accent_color": "#38BDF8" if theme == "cyber_dark" else "#00D2FF",
                    "text_color": "#FFFFFF",
                    "animation_style": "elastic_pop",
                    "sfx_profile": "sub_hit",
                    "sfx_volume": 0.90,
                    "reason": f"Chapter transition introducing {matched_label}"
                })
                item_counter += 1
                break

    return plan


def main():
    args = parse_args()
    
    with open(args.transcript, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    if not segments and isinstance(data, list):
        segments = data
        
    plan = extract_key_moments(
        segments,
        default_font=args.font,
        theme=args.theme,
        bg_engine=args.bg_engine
    )
    
    # Merge explicit user prompts if provided
    if args.user_prompts:
        try:
            if os.path.isfile(args.user_prompts):
                with open(args.user_prompts, "r", encoding="utf-8") as f:
                    user_items = json.load(f)
            else:
                user_items = json.loads(args.user_prompts)
            
            if isinstance(user_items, list):
                plan.extend(user_items)
        except Exception as e:
            print(f"[Warning] Failed to parse user-prompts: {e}", file=sys.stderr)
            
    # Sort by timeline_start
    plan.sort(key=lambda x: x.get("timeline_start", 0))
    
    # Deduplicate items starting within 2.5s of each other
    deduped = []
    last_end = -1.0
    for item in plan:
        start = item.get("timeline_start", 0)
        dur = item.get("duration", 3.0)
        if start >= last_end - 0.5:
            deduped.append(item)
            last_end = start + dur
        else:
            # Shift slightly if it's an overlay
            if item.get("visual_mode") == "inframe_overlay":
                item["timeline_start"] = round(last_end + 0.2, 2)
                deduped.append(item)
                last_end = item["timeline_start"] + dur

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2)
        
    print(f"[Success] Generated motion plan with {len(deduped)} events at: {output_path}")


if __name__ == "__main__":
    main()
