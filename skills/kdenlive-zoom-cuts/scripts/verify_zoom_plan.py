#!/usr/bin/env -S uv run --python 3.12 python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
verify_zoom_plan.py - Lint and verify semantic zoom cut plans.

Diagnostic gates:
1. MISSING-SEMANTIC-REASON: Any cut/zoom interval lacking an explicit editorial reason or recognized category.
2. DRIFT-TOO-SHORT: Continuous dynamic zoom (push_in or pull_out) applied to a clip < 2.0s (causes jitter).
3. MICRO-CLIP: Any clip duration < 0.25s (causes visual flash artifact).
4. SCALE-BOUNDS: Any scale factor outside allowed range [1.0, 1.35].
5. LATERAL-BOUNDS: Horizontal anchor (x_anchor) outside safe framing range [0.42, 0.58].
6. ZOOM-EXHAUSTION-WARNING: Sustained zoom without wide grounding for > 12.0s.
"""

import argparse
import json
import sys
from pathlib import Path

VALID_CATEGORIES = {
    "grounding_wide",
    "micro_punch",
    "thesis",
    "contrast_pivot",
    "punchline",
    "comedic_beat",
    "critical_warning",
    "rhetorical_question",
    "vulnerability",
    "suspense_buildup",
    "resolution",
    "big_picture_unzoom",
    "lateral_contrast",
}


def main():
    parser = argparse.ArgumentParser(description="Verify and lint semantic zoom cut plan")
    parser.add_argument("--plan", "-p", required=True, type=Path, help="Path to zoom_plan.json")
    parser.add_argument("--min-drift-dur", type=float, default=2.0, help="Min duration for push_in / pull_out (default: 2.0)")
    parser.add_argument("--zoom-exhaustion-threshold", type=float, default=12.0, help="Warning threshold for continuous zoom (default: 12.0)")
    args = parser.parse_args()

    plan_path = args.plan.resolve()
    if not plan_path.exists():
        sys.exit(f"Error: Plan file not found: {plan_path}")

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    if not isinstance(plan, list) or len(plan) == 0:
        sys.exit("Error: Plan must be a non-empty list of intervals.")

    issues = []
    warnings = []
    consecutive_zoom_dur = 0.0

    for idx, item in enumerate(plan):
        s = float(item.get("timeline_start", 0.0))
        e = float(item.get("timeline_end", 0.0))
        dur = e - s
        motion = item.get("motion", "instant")
        scale = float(item.get("scale", 1.0))
        reason = item.get("reason", "").strip()
        category = item.get("category", "").strip().lower()
        x_anchor = float(item.get("x_anchor", 0.50))

        # Gate 1: Micro clip
        if dur < 0.25:
            issues.append(f"[{idx}] MICRO-CLIP ({dur:.2f}s < 0.25s): [{s:.2f} -> {e:.2f}] '{reason}'")

        # Gate 2: Semantic Reason and Category
        is_active = (motion in ["push_in", "pull_out", "drift"]) or scale > 1.01 or abs(x_anchor - 0.50) >= 0.02
        if is_active:
            if not reason:
                issues.append(f"[{idx}] MISSING-SEMANTIC-REASON: Non-wide cut [{s:.2f} -> {e:.2f}] must provide an editorial 'reason' explaining why speech demands a camera shift.")
            if category and category not in VALID_CATEGORIES:
                warnings.append(f"[{idx}] UNKNOWN-CATEGORY: '{category}' is not in standard lexicon ({', '.join(sorted(VALID_CATEGORIES))})")

        # Gate 3: Dynamic Drift bounds
        if motion in ["push_in", "pull_out", "drift"]:
            s_start = float(item.get("scale_start", 1.0))
            s_end = float(item.get("scale_end", 1.10))
            if s_start < 0.99 or s_end > 1.35 or s_start > 1.35 or s_end < 0.99:
                issues.append(f"[{idx}] SCALE-BOUNDS: Dynamic scale out of bounds [{s_start} -> {s_end}]")
            if dur < args.min_drift_dur:
                issues.append(f"[{idx}] DRIFT-TOO-SHORT ({dur:.2f}s < {args.min_drift_dur}s): [{s:.2f} -> {e:.2f}] - Dynamic {motion} requires >= {args.min_drift_dur}s to avoid camera jitter.")
            is_zoomed = True
        else:
            if scale < 0.99 or scale > 1.35:
                issues.append(f"[{idx}] SCALE-BOUNDS ({scale}): Outside supported range [1.0, 1.35]")
            is_zoomed = scale > 1.01

        # Gate 4: Lateral bounds
        if x_anchor < 0.42 or x_anchor > 0.58:
            issues.append(f"[{idx}] LATERAL-BOUNDS ({x_anchor}): Safe framing range is [0.42, 0.58] to prevent clipping subject shoulders.")

        # Gate 5: Zoom exhaustion warning
        if is_zoomed:
            consecutive_zoom_dur += dur
            if consecutive_zoom_dur > args.zoom_exhaustion_threshold:
                warnings.append(f"[{idx}] ZOOM-EXHAUSTION: Camera zoomed for {consecutive_zoom_dur:.1f}s continuously. Consider returning to Wide grounding on the next sentence.")
        else:
            consecutive_zoom_dur = 0.0

    print("=" * 65)
    print(f"Verified {len(plan)} semantic zoom segments.")
    if warnings:
        print(f"⚠️ {len(warnings)} editorial advisory warning(s):")
        for w in warnings:
            print(f"  • {w}")

    if issues:
        print(f"❌ {len(issues)} structural issue(s) detected:")
        for iss in issues:
            print(f"  • {iss}")
        print("=" * 65)
        sys.exit(1)
    else:
        print("✅ 0 blocking issues detected! Plan conforms to semantic grammar.")
        print("=" * 65)


if __name__ == "__main__":
    main()
