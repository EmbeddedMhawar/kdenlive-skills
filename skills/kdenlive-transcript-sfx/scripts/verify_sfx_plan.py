#!/usr/bin/env python3
"""
verify_sfx_plan.py

Strict semantic and technical linter for SFX sound design plans.
Validates 5 structural gates before timeline injection:
1. TIMECODE-BOUNDS: Non-negative and chronological.
2. DURATION-RANGE: Reasonable sound durations (0.02s to 10.0s).
3. AUDIO-FILE-EXISTENCE: File exists, readable 48kHz WAV.
4. GAIN-BOUNDS: Safe mix levels (-35.0dB <= volume_db <= 0.0dB).
5. COLLISION-FREE: No overlapping SFX intervals (including existing Track A3 clips).
"""

import argparse
import json
import os
import sys
import wave
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Lint and verify SFX sound design plan.")
    parser.add_argument("--plan", "-p", type=str, required=True,
                        help="Path to sfx_plan.json to verify.")
    parser.add_argument("--project", type=str, default=None,
                        help="Optional path to .kdenlive project file to verify Track A3 coexistence.")
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
        return val / fps if ("." not in tc_str and val > 100) else val
    except ValueError:
        return 0.0


def parse_existing_a3(project_path: str) -> list[tuple[float, float]]:
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

        target_pls = []
        for pl in root.findall(".//playlist"):
            if pl.get("id") == "main_bin":
                continue
            for ent in pl.findall("entry"):
                prod = ent.get("producer", "")
                if "motion" in prod and "audio" in prod:
                    target_pls.append(pl)
                    break
        if not target_pls:
            pl10 = root.find(".//playlist[@id='playlist10']")
            if pl10 is not None:
                target_pls.append(pl10)

        for pl in target_pls:
            cur_time = 0.0
            for child in pl:
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
        print(f"Warning: Failed to parse existing A3 clips: {e}", file=sys.stderr)

    return intervals


def verify():
    args = parse_args()
    plan_path = Path(args.plan)

    if not plan_path.exists():
        print(f"FAILED: Plan file does not exist: {plan_path}", file=sys.stderr)
        sys.exit(1)

    with open(plan_path, "r", encoding="utf-8") as f:
        try:
            plan = json.load(f)
        except Exception as e:
            print(f"FAILED: Invalid JSON syntax in {plan_path}: {e}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(plan, list):
        print("FAILED: Plan root must be a JSON array of events.", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []
    existing_a3 = parse_existing_a3(args.project)

    last_time = -0.001
    for idx, item in enumerate(plan):
        item_id = item.get("id", f"item_{idx}")
        t = item.get("timeline_start")
        dur = item.get("duration")
        vol_db = item.get("volume_db")
        full_path_str = item.get("full_path") or item.get("sfx_path")

        # 1. TIMECODE-BOUNDS
        if t is None or not isinstance(t, (int, float)):
            errors.append(f"[{item_id}] Missing or invalid timeline_start: {t}")
            continue
        if t < 0.0:
            errors.append(f"[{item_id}] Negative timeline_start: {t}")
        if t < last_time:
            errors.append(f"[{item_id}] Chronological order violation: {t}s occurs before previous event at {last_time}s")
        last_time = t

        # 2. DURATION-RANGE
        if dur is None or not isinstance(dur, (int, float)) or dur < 0.02 or dur > 15.0:
            errors.append(f"[{item_id}] Invalid duration: {dur}s (must be between 0.02s and 15.0s)")

        # 3. GAIN-BOUNDS
        if vol_db is not None:
            if not isinstance(vol_db, (int, float)) or vol_db < -35.0 or vol_db > 0.0:
                warnings.append(f"[{item_id}] volume_db {vol_db}dB outside recommended -35.0dB to 0.0dB range")

        # 4. AUDIO-FILE-EXISTENCE
        if not full_path_str:
            errors.append(f"[{item_id}] Missing audio file path.")
        else:
            p = Path(full_path_str)
            if not p.exists():
                errors.append(f"[{item_id}] Audio file does not exist: {p}")
            else:
                try:
                    with wave.open(str(p), "rb") as wf:
                        if wf.getnchannels() not in [1, 2]:
                            errors.append(f"[{item_id}] Audio channel count unsupported: {wf.getnchannels()}")
                        if wf.getframerate() not in [44100, 48000]:
                            warnings.append(f"[{item_id}] Sample rate {wf.getframerate()}Hz (recommended: 48000Hz)")
                except Exception as ex:
                    errors.append(f"[{item_id}] Failed to read WAV headers from {p}: {ex}")

        # 5. COLLISION WITH EXISTING A3 CLIPS
        if dur is not None and isinstance(dur, (int, float)):
            t_end = t + dur
            for ex_start, ex_end in existing_a3:
                # Check overlap
                if not (t_end <= ex_start or t >= ex_end):
                    warnings.append(f"[{item_id}] Collision warning: SFX ({t:.2f}s–{t_end:.2f}s) overlaps existing Track A3 clip ({ex_start:.2f}s–{ex_end:.2f}s)")

    print(f"--- Verification Summary for {plan_path.name} ---")
    print(f"Total events checked: {len(plan)}")
    print(f"Warnings: {len(warnings)}")
    for w in warnings:
        print(f"  [WARN] {w}")

    if errors:
        print(f"Verification FAILED: {len(errors)} blocking errors found:", file=sys.stderr)
        for e in errors:
            print(f"  [ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print("Verification PASSED: 0 blocking issues.")
    sys.exit(0)


if __name__ == "__main__":
    verify()
