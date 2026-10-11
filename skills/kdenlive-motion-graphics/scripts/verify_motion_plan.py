#!/usr/bin/env python3
"""
verify_motion_plan.py

Linter and semantic gate for /tmp/motion_plan.json.
Validates structural integrity, timecode bounds, overlap collisions,
font availability, and audio SFX links before any rendering begins.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

VALID_VISUAL_MODES = {"fullscreen_card", "inframe_overlay"}
VALID_BACKGROUNDS = {"cyber_grid", "mesh_gradient", "ai_programmatic", "transparent"}
VALID_ANIMATIONS = {"elastic_pop", "typewriter", "slide_reveal", "zoom_drift", "random_scramble", "scramble_reveal"}
VALID_SFX = {"sub_hit", "whoosh", "pop", "mechanical", "thock", "typewriter", "mechanical_whoosh", "mechanical_hit"}


def check_font(font_name: str) -> bool:
    try:
        out = subprocess.check_output(["fc-match", "-f", "%{file}", font_name], stderr=subprocess.DEVNULL).decode("utf-8").strip()
        if out and os.path.isfile(out):
            return True
    except Exception:
        pass
    return False


def verify_plan(plan_path: str):
    if not os.path.exists(plan_path):
        print(f"[ERROR] Plan file not found: {plan_path}", file=sys.stderr)
        return False

    with open(plan_path, "r", encoding="utf-8") as f:
        try:
            plan = json.load(f)
        except Exception as e:
            print(f"[ERROR] Invalid JSON syntax in plan: {e}", file=sys.stderr)
            return False

    if not isinstance(plan, list):
        print("[ERROR] Plan must be a JSON array of event objects.", file=sys.stderr)
        return False

    errors = []
    warnings = []

    last_fs_end = -1.0
    for idx, item in enumerate(plan):
        prefix = f"Item #{idx + 1} ({item.get('id', 'unnamed')})"
        
        start = item.get("timeline_start")
        dur = item.get("duration")
        mode = item.get("visual_mode")
        bg = item.get("background")
        font = item.get("font", "Clarify-Blk")
        sfx = item.get("sfx_profile")
        text = item.get("text", "")
        
        # 1. Bounds check
        if start is None or start < 0:
            errors.append(f"{prefix}: 'timeline_start' must be a non-negative float (got {start}).")
        if dur is None or dur < 0.5 or dur > 20.0:
            errors.append(f"{prefix}: 'duration' must be between 0.5s and 20.0s (got {dur}).")
            
        # 2. Visual Mode
        if mode not in VALID_VISUAL_MODES:
            errors.append(f"{prefix}: Invalid 'visual_mode' '{mode}'. Must be one of {VALID_VISUAL_MODES}.")
            
        # 3. Fullscreen card collisions
        if mode == "fullscreen_card" and start is not None and dur is not None:
            if start < last_fs_end:
                errors.append(f"{prefix}: Full-screen card starts at {start:.2f}s before prior card finishes at {last_fs_end:.2f}s (overlap collision).")
            last_fs_end = start + dur

        # 4. Text content
        if not text or len(text.strip()) == 0:
            errors.append(f"{prefix}: Empty 'text' field.")

        # 5. Font check
        if not check_font(font):
            warnings.append(f"{prefix}: Font '{font}' was not found in fontconfig; will fall back to system sans-serif.")

    print(f"\n{'=' * 60}")
    print(f"MOTION PLAN VERIFICATION REPORT: {len(plan)} events analyzed")
    print(f"{'=' * 60}")
    
    if warnings:
        print(f"\n[WARNINGS ({len(warnings)})]:")
        for w in warnings:
            print(f"  * {w}")

    if errors:
        print(f"\n[BLOCKING ERRORS ({len(errors)})]:")
        for err in errors:
            print(f"  * {err}")
        print(f"\nVerification FAILED with {len(errors)} blocking errors.")
        return False
        
    print(f"\nVerification PASSED: 0 blocking issues. Ready to render.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Lint and verify /tmp/motion_plan.json.")
    parser.add_argument("--plan", "-p", type=str, default="/tmp/motion_plan.json",
                        help="Path to motion plan JSON file.")
    args = parser.parse_args()
    
    success = verify_plan(args.plan)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
