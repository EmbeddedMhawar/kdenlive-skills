#!/usr/bin/env -S uv run --python 3.12 python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
verify_broll_plan.py - Linter and semantic validator for Kdenlive B-roll placement plans.
Validates timecode bounds, track collisions, source bounds, and file availability.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

VALID_MOTION_PRESETS = {"static", "subtle_push_in", "subtle_pull_out", "subtle_drift"}


def parse_args():
    parser = argparse.ArgumentParser(description="Lint and validate a Kdenlive B-roll plan JSON.")
    parser.add_argument(
        "--plan", "-p", type=str, required=True,
        help="Path to broll_plan.json to validate."
    )
    return parser.parse_args()


def get_clip_duration(clip_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(clip_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        return -1.0
    try:
        data = json.loads(res.stdout)
        return float(data.get("format", {}).get("duration", 0.0))
    except Exception:
        return -1.0


def main():
    args = parse_args()
    plan_path = Path(args.plan).resolve()

    if not plan_path.is_file():
        print(f"[ERROR] Plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON syntax in {plan_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(plan, list):
        print(f"[ERROR] Plan must be a JSON array of clip insertion objects.", file=sys.stderr)
        sys.exit(1)

    if len(plan) == 0:
        print(f"[WARN] Plan is empty (0 clips specified). Nothing to validate.")
        sys.exit(0)

    errors = []
    warnings = []

    last_end = -1.0
    clip_dur_cache = {}

    for idx, item in enumerate(plan):
        item_id = item.get("id", f"broll_{idx + 1}")
        clip_path_str = item.get("clip_path")
        tl_start = item.get("timeline_start")
        dur = item.get("duration")
        src_in = item.get("source_in", 0.0)
        motion = item.get("motion_preset", "static")
        audio_db = item.get("ambient_audio_db")

        # 1. Required fields check
        if clip_path_str is None or tl_start is None or dur is None:
            errors.append(f"[{item_id}] Missing required fields: 'clip_path', 'timeline_start', or 'duration'.")
            continue

        tl_start = float(tl_start)
        dur = float(dur)
        src_in = float(src_in)

        # 2. Timecode bounds check
        if tl_start < 0:
            errors.append(f"[{item_id}] `timeline_start` ({tl_start:.2f}s) must be non-negative.")
        if dur <= 0:
            errors.append(f"[{item_id}] `duration` ({dur:.2f}s) must be positive.")

        # 3. Chronological & Collision check on Track V2
        if tl_start < last_end:
            if tl_start < last_end - 0.01:
                errors.append(
                    f"[{item_id}] Track V2 Collision: Starts at {tl_start:.2f}s before previous clip finishes at {last_end:.2f}s."
                )
            else:
                warnings.append(
                    f"[{item_id}] Butt-cut against previous clip at {tl_start:.2f}s (acceptable for consecutive B-roll montage)."
                )

        last_end = max(last_end, tl_start + dur)

        # 4. File existence & Source range check
        clip_path = Path(clip_path_str).resolve()
        if not clip_path.is_file():
            errors.append(f"[{item_id}] Source clip does not exist on disk: {clip_path}")
        else:
            if clip_path not in clip_dur_cache:
                clip_dur_cache[clip_path] = get_clip_duration(clip_path)

            source_dur = clip_dur_cache[clip_path]
            if source_dur > 0:
                if src_in < 0:
                    errors.append(f"[{item_id}] `source_in` ({src_in:.2f}s) cannot be negative.")
                if src_in + dur > source_dur + 0.05:
                    errors.append(
                        f"[{item_id}] Source bounds overrun: source_in ({src_in:.2f}s) + duration ({dur:.2f}s) = "
                        f"{src_in + dur:.2f}s exceeds media duration ({source_dur:.2f}s)."
                    )

        # 5. Motion preset check
        if motion and motion not in VALID_MOTION_PRESETS:
            errors.append(
                f"[{item_id}] Invalid motion_preset '{motion}'. Must be one of: {', '.join(sorted(VALID_MOTION_PRESETS))}"
            )

        # 6. Audio dB check
        if audio_db is not None:
            try:
                db_val = float(audio_db)
                if db_val > 0.0 or db_val < -80.0:
                    errors.append(f"[{item_id}] `ambient_audio_db` ({db_val}) should typically be between -60.0 and 0.0 dB.")
            except ValueError:
                errors.append(f"[{item_id}] `ambient_audio_db` must be a numerical dB value.")

    print(f"\n==================================================")
    print(f" B-ROLL PLAN VALIDATION: {plan_path.name}")
    print(f" Verified clips: {len(plan)}")
    print(f" Total errors:   {len(errors)}")
    print(f" Total warnings: {len(warnings)}")
    print(f"==================================================")

    for w in warnings:
        print(f"  [WARN] {w}")

    if errors:
        for e in errors:
            print(f"  [ERROR] {e}", file=sys.stderr)
        print(f"\n[FAIL] Validation FAILED with {len(errors)} blocking errors.", file=sys.stderr)
        sys.exit(1)

    print(f"\n[SUCCESS] Verification PASSED: 0 blocking issues. Ready to apply to Kdenlive.")
    sys.exit(0)


if __name__ == "__main__":
    main()
