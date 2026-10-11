#!/usr/bin/env -S uv run --python 3.12 python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
apply_zoom_cuts.py - Apply semantic dynamic zoom cuts and razor-splits to a Kdenlive project timeline.

Supports a rich palette of semantic zoom variations:
- Instant Micro-Punches (1.05x - 1.08x) for subtle clause progression
- Instant Medium Punches (1.12x - 1.18x) for core thesis assertions and rhetorical questions
- Instant Tight Punches (1.24x - 1.35x) for punchlines, disbelief, and critical warnings
- Slow Push-Ins (creep) for vulnerability, intimate storytelling, and suspense build-up
- Slow Pull-Outs (unzoom) for tension release, big-picture conclusions, and resolution
- Lateral Re-Anchoring (X-offset) for dialectic A/B contrasts
- Grounding Wides (1.0x) for natural unhurried delivery
"""

import argparse
import copy
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_tc(tc_str: str) -> float:
    """Parse timecode string (HH:MM:SS.mmm or seconds string) to float seconds."""
    tc_str = tc_str.strip()
    if ":" in tc_str:
        parts = tc_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    return float(tc_str)


def format_tc(seconds: float) -> str:
    """Format seconds into Kdenlive-compatible HH:MM:SS.mmm format."""
    seconds = max(0.0, float(seconds))
    secs = int(seconds)
    mins = secs // 60
    hours = mins // 60
    mins = mins % 60
    secs = secs % 60
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        secs += 1
        ms -= 1000
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{ms:03d}"


def compute_rect(
    width: int,
    height: int,
    scale: float,
    eye_level: float = 0.38,
    x_anchor: float = 0.50,
) -> tuple[int, int, int, int]:
    """
    Calculate bounding box (X, Y, W, H) for scaling with eye-level and lateral anchors.
    scale: 1.0 is 100% wide.
    eye_level: vertical anchor normalized to frame height (0.38 is upper-third).
    x_anchor: horizontal anchor (0.50 is center, 0.46 left-bias, 0.54 right-bias).
    """
    if abs(scale - 1.0) < 0.001 and abs(x_anchor - 0.50) < 0.001:
        return 0, 0, width, height

    w_scaled = int(round(width * scale))
    h_scaled = int(round(height * scale))

    x = int(round(width * x_anchor * (1.0 - scale)))
    y = int(round(height * eye_level * (1.0 - scale)))

    return x, y, w_scaled, h_scaled


def create_qtblend_filter(
    filter_id: str,
    width: int,
    height: int,
    motion: str,
    scale: float,
    scale_start: float | None,
    scale_end: float | None,
    duration_frames: int,
    eye_level: float = 0.38,
    x_anchor: float = 0.50,
    x_anchor_start: float | None = None,
    x_anchor_end: float | None = None,
) -> ET.Element:
    """Construct an MLT qtblend filter XML element for instant, push-in, or pull-out zoom."""
    filter_elem = ET.Element("filter")
    filter_elem.attrib["id"] = filter_id

    prop_svc = ET.SubElement(filter_elem, "property")
    prop_svc.attrib["name"] = "mlt_service"
    prop_svc.text = "qtblend"

    prop_kid = ET.SubElement(filter_elem, "property")
    prop_kid.attrib["name"] = "kdenlive_id"
    prop_kid.text = "qtblend"

    prop_comp = ET.SubElement(filter_elem, "property")
    prop_comp.attrib["name"] = "compositing"
    prop_comp.text = "0"

    prop_rect = ET.SubElement(filter_elem, "property")
    prop_rect.attrib["name"] = "rect"

    is_dynamic = motion in ["push_in", "pull_out", "drift"] or (scale_start is not None and scale_end is not None and abs(scale_start - scale_end) > 0.005)

    if is_dynamic:
        s0 = scale_start if scale_start is not None else (1.0 if motion != "pull_out" else 1.15)
        s1 = scale_end if scale_end is not None else (1.10 if motion != "pull_out" else 1.0)
        xa0 = x_anchor_start if x_anchor_start is not None else x_anchor
        xa1 = x_anchor_end if x_anchor_end is not None else x_anchor

        x0, y0, w0, h0 = compute_rect(width, height, s0, eye_level, xa0)
        x1, y1, w1, h1 = compute_rect(width, height, s1, eye_level, xa1)
        last_frame = max(1, duration_frames - 1)
        prop_rect.text = f"0={x0} {y0} {w0} {h0} 1; {last_frame}={x1} {y1} {w1} {h1} 1"
    else:
        # Instant punch or lateral shift
        x, y, w, h = compute_rect(width, height, scale, eye_level, x_anchor)
        prop_rect.text = f"{x} {y} {w} {h} 1"

    return filter_elem


def classify_zoom_style(motion: str, scale: float, scale_start: float | None, scale_end: float | None, x_anchor: float) -> str:
    """Classify zoom segment into human-readable variation categories."""
    if motion == "pull_out" or (scale_start is not None and scale_end is not None and scale_start > scale_end):
        return "Slow Pull-Out (Unzoom)"
    if motion == "push_in" or (scale_start is not None and scale_end is not None and scale_start < scale_end):
        return "Slow Push-In (Creep)"
    if abs(x_anchor - 0.50) >= 0.02:
        return f"Lateral Re-Anchor ({'Left' if x_anchor < 0.5 else 'Right'}, {scale:.2f}x)"
    if scale <= 1.01:
        return "Grounding Wide (1.0x)"
    if scale < 1.10:
        return f"Micro-Punch ({scale:.2f}x)"
    if scale < 1.22:
        return f"Medium Punch ({scale:.2f}x)"
    return f"Tight Punch ({scale:.2f}x)"


def main():
    parser = argparse.ArgumentParser(description="Apply dynamic semantic zoom cuts to Kdenlive project")
    parser.add_argument("--project", "-p", required=True, type=Path, help="Input .kdenlive project file")
    parser.add_argument("--plan", "-l", required=True, type=Path, help="Path to zoom_plan.json")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output .kdenlive project file")
    parser.add_argument("--eye-level", type=float, default=0.38, help="Eye-level anchor ratio (default: 0.38)")
    parser.add_argument("--min-split-gap", type=float, default=0.25, help="Minimum gap (s) to existing cut to allow split")
    args = parser.parse_args()

    project_path = args.project.resolve()
    if not project_path.exists():
        sys.exit(f"Error: Project file not found: {project_path}")

    plan_path = args.plan.resolve()
    if not plan_path.exists():
        sys.exit(f"Error: Zoom plan file not found: {plan_path}")

    out_path = args.output
    if out_path is None:
        out_path = project_path.parent / f"{project_path.stem}_zoomed.kdenlive"
    out_path = out_path.resolve()

    with open(plan_path, "r", encoding="utf-8") as f:
        zoom_plan = json.load(f)

    if not isinstance(zoom_plan, list) or len(zoom_plan) == 0:
        sys.exit("Error: zoom_plan.json must be a non-empty list of intervals.")

    tree = ET.parse(project_path)
    root = tree.getroot()

    # 1. Profile information
    profile = root.find("profile")
    if profile is None:
        sys.exit("Error: <profile> tag not found in Kdenlive project.")

    width = int(profile.attrib.get("width", 1920))
    height = int(profile.attrib.get("height", 1080))
    fps_num = int(profile.attrib.get("frame_rate_num", 60))
    fps_den = int(profile.attrib.get("frame_rate_den", 1))
    fps = fps_num / fps_den

    # 2. Locate playlists
    pl_audio = root.find('.//playlist[@id="playlist2"]')
    pl_video = root.find('.//playlist[@id="playlist4"]')
    if pl_audio is None or pl_video is None:
        sys.exit("Error: Could not locate playlist2 (Audio) or playlist4 (Video) in XML.")

    audio_entries = [ch for ch in list(pl_audio) if ch.tag == "entry"]
    video_entries = [ch for ch in list(pl_video) if ch.tag == "entry"]

    if len(audio_entries) != len(video_entries):
        sys.exit(f"Error: Audio entries count ({len(audio_entries)}) != Video entries count ({len(video_entries)})")

    # 3. Extract existing timeline segments
    existing_clips = []
    cur_timeline = 0.0

    for idx, (ae, ve) in enumerate(zip(audio_entries, video_entries)):
        a_in = parse_tc(ae.attrib["in"])
        a_out = parse_tc(ae.attrib["out"])
        v_in = parse_tc(ve.attrib["in"])
        v_out = parse_tc(ve.attrib["out"])

        dur = v_out - v_in
        if dur <= 0:
            dur = max(0.01, a_out - a_in)

        tl_start = cur_timeline
        tl_end = cur_timeline + dur
        cur_timeline = tl_end

        existing_clips.append({
            "idx": idx,
            "tl_start": tl_start,
            "tl_end": tl_end,
            "dur": dur,
            "v_producer": ve.attrib["producer"],
            "v_in": v_in,
            "v_out": v_out,
            "v_props": list(ve.findall("property")),
            "a_producer": ae.attrib["producer"],
            "a_in": a_in,
            "a_out": a_out,
            "a_props": list(ae.findall("property")),
        })

    total_timeline_duration = cur_timeline
    print(f"Loaded {len(existing_clips)} timeline clips, total duration: {total_timeline_duration:.2f}s ({format_tc(total_timeline_duration)})")

    # 4. Determine valid razor-split points from zoom plan
    plan_split_points = set()
    for item in zoom_plan:
        s = float(item["timeline_start"])
        e = float(item["timeline_end"])
        if 0.05 < s < total_timeline_duration - 0.05:
            plan_split_points.add(s)
        if 0.05 < e < total_timeline_duration - 0.05:
            plan_split_points.add(e)

    active_splits = []
    for sp in sorted(plan_split_points):
        too_close = False
        for clip in existing_clips:
            if abs(sp - clip["tl_start"]) < args.min_split_gap or abs(sp - clip["tl_end"]) < args.min_split_gap:
                too_close = True
                break
        if not too_close:
            active_splits.append(sp)

    print(f"Identified {len(active_splits)} valid mid-clip semantic razor split points to inject.")

    # 5. Perform synchronized razor splits on clips
    new_clips = []
    for clip in existing_clips:
        clip_splits = [sp for sp in active_splits if clip["tl_start"] + args.min_split_gap < sp < clip["tl_end"] - args.min_split_gap]
        if not clip_splits:
            new_clips.append(clip)
            continue

        clip_splits.sort()
        slice_points = [clip["tl_start"]] + clip_splits + [clip["tl_end"]]

        for i in range(len(slice_points) - 1):
            s_tl = slice_points[i]
            e_tl = slice_points[i + 1]
            offset_s = s_tl - clip["tl_start"]
            offset_e = e_tl - clip["tl_start"]

            new_v_in = clip["v_in"] + offset_s
            new_v_out = clip["v_in"] + offset_e
            new_a_in = clip["a_in"] + offset_s
            new_a_out = clip["a_in"] + offset_e

            new_clips.append({
                "tl_start": s_tl,
                "tl_end": e_tl,
                "dur": e_tl - s_tl,
                "v_producer": clip["v_producer"],
                "v_in": new_v_in,
                "v_out": new_v_out,
                "v_props": copy.deepcopy(clip["v_props"]),
                "a_producer": clip["a_producer"],
                "a_in": new_a_in,
                "a_out": new_a_out,
                "a_props": copy.deepcopy(clip["a_props"]),
            })

    print(f"Timeline sliced: {len(existing_clips)} clips -> {len(new_clips)} clips.")

    # 6. Assign zoom plan properties to each clip
    filter_counter = 1
    variation_stats: dict[str, int] = {}

    for child in list(pl_audio):
        if child.tag == "entry":
            pl_audio.remove(child)
    for child in list(pl_video):
        if child.tag == "entry":
            pl_video.remove(child)

    cur_timeline_frame = 0
    av_groups = []

    for clip in new_clips:
        mid_time = (clip["tl_start"] + clip["tl_end"]) / 2.0
        dur_frames = max(1, int(round(clip["dur"] * fps)))

        matched_plan = None
        for item in zoom_plan:
            if float(item["timeline_start"]) - 0.05 <= mid_time <= float(item["timeline_end"]) + 0.05:
                matched_plan = item
                break

        motion = "instant"
        scale = 1.0
        scale_start = None
        scale_end = None
        x_anchor = 0.50
        eye_level = args.eye_level

        if matched_plan is not None:
            motion = matched_plan.get("motion", "instant")
            scale = float(matched_plan.get("scale", 1.0))
            if "scale_start" in matched_plan:
                scale_start = float(matched_plan["scale_start"])
            if "scale_end" in matched_plan:
                scale_end = float(matched_plan["scale_end"])
            if "x_anchor" in matched_plan:
                x_anchor = float(matched_plan["x_anchor"])
            if "eye_level" in matched_plan:
                eye_level = float(matched_plan["eye_level"])

        style_label = classify_zoom_style(motion, scale, scale_start, scale_end, x_anchor)
        variation_stats[style_label] = variation_stats.get(style_label, 0) + 1

        # Build Video Entry
        ve = ET.SubElement(pl_video, "entry")
        ve.attrib["producer"] = clip["v_producer"]
        ve.attrib["in"] = format_tc(clip["v_in"])
        ve.attrib["out"] = format_tc(clip["v_out"])
        for p in clip["v_props"]:
            ve.append(copy.deepcopy(p))

        # Check if filter needed
        needs_filter = (
            motion in ["push_in", "pull_out", "drift"]
            or (scale_start is not None and scale_end is not None and abs(scale_start - scale_end) > 0.005)
            or scale > 1.001
            or abs(x_anchor - 0.50) >= 0.01
        )

        if needs_filter:
            filt = create_qtblend_filter(
                f"zoom_filter_{filter_counter}",
                width,
                height,
                motion=motion,
                scale=scale,
                scale_start=scale_start,
                scale_end=scale_end,
                duration_frames=dur_frames,
                eye_level=eye_level,
                x_anchor=x_anchor,
            )
            ve.append(filt)
            filter_counter += 1

        # Build Audio Entry
        ae = ET.SubElement(pl_audio, "entry")
        ae.attrib["producer"] = clip["a_producer"]
        ae.attrib["in"] = format_tc(clip["a_in"])
        ae.attrib["out"] = format_tc(clip["a_out"])
        for p in clip["a_props"]:
            ae.append(copy.deepcopy(p))

        # AVSplit grouping
        av_groups.append({
            "children": [
                {
                    "data": f"1:{cur_timeline_frame}:-1",
                    "leaf": "clip",
                    "type": "Leaf",
                },
                {
                    "data": f"2:{cur_timeline_frame}:-1",
                    "leaf": "clip",
                    "type": "Leaf",
                },
            ],
            "type": "AVSplit",
        })

        cur_timeline_frame += dur_frames

    # 7. Update tractor4 sequenceproperties.groups
    tractor4 = root.find('.//tractor[@id="tractor4"]')
    if tractor4 is not None:
        for p in tractor4.findall("property"):
            if p.attrib.get("name") == "kdenlive:sequenceproperties.groups":
                p.text = json.dumps(av_groups, indent=4)
                break
        else:
            p = ET.SubElement(tractor4, "property")
            p.attrib["name"] = "kdenlive:sequenceproperties.groups"
            p.text = json.dumps(av_groups, indent=4)

    # 8. Save updated project
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"Saved zoomed project to: {out_path}")
    print("\nZoom Variation Breakdown:")
    for style, count in sorted(variation_stats.items()):
        print(f"  • {style}: {count} clip(s)")

    # 9. Verify syntax with melt (1 frame only for instantaneous validation)
    print("\nVerifying MLT syntax with melt...")
    res = subprocess.run(["melt", str(out_path), "in=0", "out=1", "-consumer", "null"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Warning: melt verification failed: {res.stderr[:500]}", file=sys.stderr)
    else:
        print("✓ melt verification passed with 0 errors!")


if __name__ == "__main__":
    main()
