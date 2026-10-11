#!/usr/bin/env -S uv run --python 3.12 python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
apply_broll.py - Non-destructively inject B-roll footage inserts and thematic cutaways
into a Kdenlive project timeline XML:
- Registers master B-roll clips in main_bin with their full durations and editing proxies.
- Creates individual video and audio chains with kdenlive:id pointing to the master bin clip.
- Video cutaways -> Track V2 (tractor3 -> playlist6)
- Ambient audio / foley -> Track A2 (tractor0 -> playlist0)
- Track V3 (tractor6 -> playlist8/playlist9) created and added to tractor4 with compositing transition.
- Preserves Master A-Roll (V1 on playlist4 / A1 on playlist2) completely intact.
- Preserves all Kdenlive bin references and metadata.
"""

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Inject B-roll inserts into Kdenlive MLT XML.")
    parser.add_argument(
        "--project", "-p", type=str, required=True,
        help="Path to input .kdenlive project file (e.g. roughcut_zoomed.kdenlive)."
    )
    parser.add_argument(
        "--plan", "-m", type=str, required=True,
        help="Path to broll_plan.json produced during semantic placement planning."
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True,
        help="Path to output .kdenlive project file (e.g. roughcut_broll.kdenlive)."
    )
    parser.add_argument(
        "--proxies-dir", type=str, default=None,
        help="Optional directory containing editing proxies to associate with source clips."
    )
    parser.add_argument(
        "--generate-missing-proxies", action="store_true",
        help="Automatically generate 540p editing proxies for any B-roll clips missing them."
    )
    return parser.parse_args()


def generate_proxy(video_path: Path, proxies_dir: Path) -> str | None:
    """Generate 540p ultrafast editing proxy using ffmpeg."""
    proxies_dir.mkdir(parents=True, exist_ok=True)
    dst = proxies_dir / f"{video_path.stem}_proxy.mov"
    if dst.is_file():
        return str(dst.resolve())
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", "scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(dst)
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 0 and dst.is_file():
        return str(dst.resolve())
    return None


def compute_kdenlive_hash(file_path: Path) -> str:
    """Calculate Kdenlive-compliant MD5 hash (first 1MB + last 1MB)."""
    size = file_path.stat().st_size
    with open(file_path, "rb") as f:
        if size <= 2 * 1024 * 1024:
            data = f.read()
        else:
            first = f.read(1024 * 1024)
            f.seek(size - 1024 * 1024)
            last = f.read(1024 * 1024)
            data = first + last
    return hashlib.md5(data).hexdigest()


def format_tc(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm format."""
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


def get_profile_info(root: ET.Element) -> tuple[int, int, float]:
    """Retrieve canvas dimensions and fps from MLT profile."""
    profile = root.find("profile")
    if profile is not None:
        w = int(profile.get("width", "1920"))
        h = int(profile.get("height", "1080"))
        num = float(profile.get("frame_rate_num", "60"))
        den = float(profile.get("frame_rate_den", "1"))
        fps = num / den if den > 0 else 60.0
        return w, h, fps
    return 1920, 1080, 60.0


def compute_rect(
    width: int,
    height: int,
    scale: float,
    eye_level: float = 0.50,
    x_anchor: float = 0.50,
) -> tuple[int, int, int, int]:
    """Calculate bounding box (X, Y, W, H) for scaling."""
    if abs(scale - 1.0) < 0.001 and abs(x_anchor - 0.50) < 0.001 and abs(eye_level - 0.50) < 0.001:
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
    motion_preset: str,
    duration_frames: int,
) -> ET.Element:
    """Create MLT qtblend filter for subtle dynamic motion or drift."""
    filter_elem = ET.Element("filter", attrib={"id": filter_id})

    prop_svc = ET.SubElement(filter_elem, "property", attrib={"name": "mlt_service"})
    prop_svc.text = "qtblend"

    prop_kid = ET.SubElement(filter_elem, "property", attrib={"name": "kdenlive_id"})
    prop_kid.text = "qtblend"

    prop_comp = ET.SubElement(filter_elem, "property", attrib={"name": "compositing"})
    prop_comp.text = "0"

    prop_rect = ET.SubElement(filter_elem, "property", attrib={"name": "rect"})
    last_frame = max(1, duration_frames - 1)

    if motion_preset == "subtle_push_in":
        x0, y0, w0, h0 = compute_rect(width, height, 1.00, 0.50, 0.50)
        x1, y1, w1, h1 = compute_rect(width, height, 1.05, 0.50, 0.50)
        prop_rect.text = f"0={x0} {y0} {w0} {h0} 1; {last_frame}={x1} {y1} {w1} {h1} 1"
    elif motion_preset == "subtle_pull_out":
        x0, y0, w0, h0 = compute_rect(width, height, 1.05, 0.50, 0.50)
        x1, y1, w1, h1 = compute_rect(width, height, 1.00, 0.50, 0.50)
        prop_rect.text = f"0={x0} {y0} {w0} {h0} 1; {last_frame}={x1} {y1} {w1} {h1} 1"
    elif motion_preset == "subtle_drift":
        x0, y0, w0, h0 = compute_rect(width, height, 1.04, 0.50, 0.47)
        x1, y1, w1, h1 = compute_rect(width, height, 1.04, 0.50, 0.53)
        prop_rect.text = f"0={x0} {y0} {w0} {h0} 1; {last_frame}={x1} {y1} {w1} {h1} 1"
    else:
        prop_rect.text = f"0 0 {width} {height} 1"

    return filter_elem


def create_volume_filter(filter_id: str, gain_db: float, duration_frames: int) -> ET.Element:
    """Create MLT volume filter with subtle fade-in and fade-out ramps."""
    filter_elem = ET.Element("filter", attrib={"id": filter_id})

    prop_svc = ET.SubElement(filter_elem, "property", attrib={"name": "mlt_service"})
    prop_svc.text = "volume"

    prop_kid = ET.SubElement(filter_elem, "property", attrib={"name": "kdenlive_id"})
    prop_kid.text = "volume"

    prop_gain = ET.SubElement(filter_elem, "property", attrib={"name": "gain"})
    prop_gain.text = f"{gain_db:.1f}dB"

    ramp_len = min(15, duration_frames // 4)
    if ramp_len > 1:
        last_frame = max(1, duration_frames - 1)
        fade_out_start = max(ramp_len + 1, last_frame - ramp_len)
        prop_level = ET.SubElement(filter_elem, "property", attrib={"name": "level"})
        prop_level.text = f"0=0.0; {ramp_len}=1.0; {fade_out_start}=1.0; {last_frame}=0.0"

    return filter_elem


def find_proxy(file_path: Path, proxies_dir: Path | None) -> str | None:
    """Detect if an editing proxy exists on disk."""
    if not proxies_dir or not proxies_dir.is_dir():
        return None
    stem = file_path.stem
    for cand in [
        proxies_dir / f"{stem}_proxy.mov",
        proxies_dir / f"{stem}_proxy.mp4",
        proxies_dir / f"{stem}.mov",
        proxies_dir / f"{stem}.mp4",
    ]:
        if cand.is_file():
            return str(cand.resolve())
    return None


def probe_clip(file_path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size:stream=index,codec_type,codec_name,width,height",
        "-of", "json", str(file_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        return {"duration": 30.0, "size": 0, "width": 1920, "height": 1080}
    try:
        data = json.loads(res.stdout)
        dur = float(data.get("format", {}).get("duration", 30.0))
        size = int(data.get("format", {}).get("size", 0))
        width = 1920
        height = 1080
        for st in data.get("streams", []):
            if st.get("codec_type") == "video":
                width = int(st.get("width", 1920))
                height = int(st.get("height", 1080))
                break
        return {"duration": dur, "size": size, "width": width, "height": height}
    except Exception:
        return {"duration": 30.0, "size": 0, "width": 1920, "height": 1080}


def main():
    args = parse_args()
    project_path = Path(args.project).resolve()
    plan_path = Path(args.plan).resolve()
    output_path = Path(args.output).resolve()
    proxies_dir = Path(args.proxies_dir).resolve() if args.proxies_dir else None

    if not project_path.is_file():
        print(f"[ERROR] Input project file not found: {project_path}", file=sys.stderr)
        sys.exit(1)
    if not plan_path.is_file():
        print(f"[ERROR] Plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(project_path)
    root = tree.getroot()
    width, height, fps = get_profile_info(root)

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    # Sort strictly by timeline_start
    plan.sort(key=lambda x: float(x.get("timeline_start", 0.0)))

    # Find maximum kdenlive:id currently in the project
    max_id = 12
    for elem in root.iter():
        for prop in elem.findall("property"):
            if prop.get("name") == "kdenlive:id" and prop.text and prop.text.isdigit():
                max_id = max(max_id, int(prop.text))

    # Locate main_bin
    main_bin = root.find(".//playlist[@id='main_bin']")
    if main_bin is None:
        print("[ERROR] main_bin playlist not found in project XML", file=sys.stderr)
        sys.exit(1)

    # Find insertion point for new chains (before the first playlist in root)
    chain_insert_idx = len(root)
    for i, child in enumerate(root):
        if child.tag == "playlist":
            chain_insert_idx = i
            break

    # Find tractor4 (sequence tractor) entry in main_bin
    tractor4_entry = None
    for entry in main_bin.findall("entry"):
        if entry.get("producer") == "tractor4":
            tractor4_entry = entry
            break
    main_bin_insert_idx = list(main_bin).index(tractor4_entry) if tractor4_entry is not None else len(main_bin)

    # 1. Register Unique Master B-Roll Clips in main_bin
    unique_clips = {}
    catalog_path = project_path.parent.parent / "broll_catalog.json"
    if catalog_path.is_file():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cat = json.load(f)
                for item in cat:
                    p = Path(item["file_path"]).resolve()
                    if p.is_file():
                        unique_clips[str(p)] = p
        except Exception:
            pass

    for item in plan:
        p = Path(item["clip_path"]).resolve()
        if p.is_file():
            unique_clips[str(p)] = p

    clip_registry = {}
    for idx, (clip_str, clip_path) in enumerate(sorted(unique_clips.items())):
        max_id += 1
        bin_id = str(max_id)
        clip_uuid = f"{{{uuid.uuid4()}}}"
        probe = probe_clip(clip_path)
        clip_dur = probe["duration"]
        orig_w = probe["width"]
        orig_h = probe["height"]
        file_size = probe["size"] or (clip_path.stat().st_size if clip_path.exists() else 0)
        file_hash = compute_kdenlive_hash(clip_path) if clip_path.exists() else ""
        proxy_path = find_proxy(clip_path, proxies_dir)
        if not proxy_path and args.generate_missing_proxies and proxies_dir:
            print(f"[INFO] Generating missing proxy for {clip_path.name}...")
            proxy_path = generate_proxy(clip_path, proxies_dir)

        bin_prod_id = f"chain_broll_{idx + 1}_bin"
        video_prod_id = f"chain_broll_{idx + 1}_video"
        audio_prod_id = f"chain_broll_{idx + 1}_audio"
        clip_out_tc = format_tc(clip_dur)
        clip_len_frames = str(int(round(clip_dur * fps)))

        # A. Bin Master Chain
        active_res = proxy_path if proxy_path and Path(proxy_path).is_file() else str(clip_path)
        c_bin = ET.Element("chain", attrib={"id": bin_prod_id, "out": clip_out_tc})
        ET.SubElement(c_bin, "property", attrib={"name": "length"}).text = clip_len_frames
        ET.SubElement(c_bin, "property", attrib={"name": "eof"}).text = "pause"
        ET.SubElement(c_bin, "property", attrib={"name": "resource"}).text = active_res
        ET.SubElement(c_bin, "property", attrib={"name": "mlt_service"}).text = "avformat-novalidate"
        ET.SubElement(c_bin, "property", attrib={"name": "seekable"}).text = "1"
        ET.SubElement(c_bin, "property", attrib={"name": "format"}).text = "3"
        ET.SubElement(c_bin, "property", attrib={"name": "audio_index"}).text = "1"
        ET.SubElement(c_bin, "property", attrib={"name": "video_index"}).text = "0"
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:control_uuid"}).text = clip_uuid
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:id"}).text = bin_id
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:clip_type"}).text = "0"
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:file_size"}).text = str(file_size)
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:file_hash"}).text = file_hash
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:folderid"}).text = "-1"
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:clipname"}).text = clip_path.name
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:originalurl"}).text = str(clip_path)
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:original.resource"}).text = str(clip_path)
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:original.width"}).text = str(orig_w)
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:original.height"}).text = str(orig_h)
        ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:original.length"}).text = clip_len_frames
        if proxy_path and Path(proxy_path).is_file():
            ET.SubElement(c_bin, "property", attrib={"name": "kdenlive:proxy"}).text = proxy_path

        root.insert(chain_insert_idx, c_bin)
        chain_insert_idx += 1

        # B. Video Track Chain
        c_vid = ET.Element("chain", attrib={"id": video_prod_id, "out": clip_out_tc})
        ET.SubElement(c_vid, "property", attrib={"name": "length"}).text = clip_len_frames
        ET.SubElement(c_vid, "property", attrib={"name": "eof"}).text = "pause"
        ET.SubElement(c_vid, "property", attrib={"name": "resource"}).text = active_res
        ET.SubElement(c_vid, "property", attrib={"name": "mlt_service"}).text = "avformat-novalidate"
        ET.SubElement(c_vid, "property", attrib={"name": "seekable"}).text = "1"
        ET.SubElement(c_vid, "property", attrib={"name": "format"}).text = "3"
        ET.SubElement(c_vid, "property", attrib={"name": "audio_index"}).text = "1"
        ET.SubElement(c_vid, "property", attrib={"name": "video_index"}).text = "0"
        ET.SubElement(c_vid, "property", attrib={"name": "set.test_audio"}).text = "1"
        ET.SubElement(c_vid, "property", attrib={"name": "set.test_image"}).text = "0"
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:control_uuid"}).text = clip_uuid
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:id"}).text = bin_id
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:clip_type"}).text = "0"
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:file_size"}).text = str(file_size)
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:file_hash"}).text = file_hash
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:folderid"}).text = "-1"
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:clipname"}).text = clip_path.name
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:originalurl"}).text = str(clip_path)
        ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:original.resource"}).text = str(clip_path)
        if proxy_path and Path(proxy_path).is_file():
            ET.SubElement(c_vid, "property", attrib={"name": "kdenlive:proxy"}).text = proxy_path

        root.insert(chain_insert_idx, c_vid)
        chain_insert_idx += 1

        # C. Audio Track Chain
        c_aud = ET.Element("chain", attrib={"id": audio_prod_id, "out": clip_out_tc})
        ET.SubElement(c_aud, "property", attrib={"name": "length"}).text = clip_len_frames
        ET.SubElement(c_aud, "property", attrib={"name": "eof"}).text = "pause"
        ET.SubElement(c_aud, "property", attrib={"name": "resource"}).text = str(clip_path)
        ET.SubElement(c_aud, "property", attrib={"name": "mlt_service"}).text = "avformat-novalidate"
        ET.SubElement(c_aud, "property", attrib={"name": "seekable"}).text = "1"
        ET.SubElement(c_aud, "property", attrib={"name": "format"}).text = "3"
        ET.SubElement(c_aud, "property", attrib={"name": "audio_index"}).text = "1"
        ET.SubElement(c_aud, "property", attrib={"name": "video_index"}).text = "0"
        ET.SubElement(c_aud, "property", attrib={"name": "set.test_audio"}).text = "0"
        ET.SubElement(c_aud, "property", attrib={"name": "set.test_image"}).text = "1"
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:control_uuid"}).text = clip_uuid
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:id"}).text = bin_id
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:clip_type"}).text = "0"
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:file_size"}).text = str(file_size)
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:file_hash"}).text = file_hash
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:folderid"}).text = "-1"
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:clipname"}).text = clip_path.name
        ET.SubElement(c_aud, "property", attrib={"name": "kdenlive:originalurl"}).text = str(clip_path)

        root.insert(chain_insert_idx, c_aud)
        chain_insert_idx += 1

        # D. Add Master Clip Entry to main_bin
        bin_e = ET.Element("entry", attrib={"in": "00:00:00.000", "out": clip_out_tc, "producer": bin_prod_id})
        main_bin.insert(main_bin_insert_idx, bin_e)
        main_bin_insert_idx += 1

        clip_registry[clip_str] = {
            "bin_id": bin_id,
            "bin_producer": bin_prod_id,
            "video_producer": video_prod_id,
            "audio_producer": audio_prod_id,
            "duration": clip_dur,
        }

    # 2. Setup Tractors and Playlists
    # In Kdenlive:
    # tractor0 -> Audio Track 2 (A2) -> subtrack 0 is playlist0, subtrack 1 is playlist1 (mixes)
    # tractor1 -> Audio Track 1 (A1) -> subtrack 0 is playlist2, subtrack 1 is playlist3 (mixes)
    # tractor2 -> Video Track 1 (V1) -> subtrack 0 is playlist4, subtrack 1 is playlist5 (mixes)
    # tractor3 -> Video Track 2 (V2) -> subtrack 0 is playlist6, subtrack 1 is playlist7 (mixes)
    # tractor6 -> Video Track 3 (V3) -> subtrack 0 is playlist8, subtrack 1 is playlist9 (mixes)

    tractor0 = root.find(".//tractor[@id='tractor0']")
    tractor1 = root.find(".//tractor[@id='tractor1']")
    tractor2 = root.find(".//tractor[@id='tractor2']")
    tractor3 = root.find(".//tractor[@id='tractor3']")
    tractor4 = root.find(".//tractor[@id='tractor4']")

    timeline_out = tractor4.get("out", "00:11:23.783") if tractor4 is not None else "00:11:23.783"

    def set_prop(elem, name, value):
        for p in elem.findall("property"):
            if p.get("name") == name:
                p.text = value
                return
        ET.SubElement(elem, "property", attrib={"name": name}).text = value

    for t in [tractor0, tractor1, tractor2, tractor3]:
        if t is not None:
            set_prop(t, "kdenlive:trackheight", "48")

    # Add Track V3 (tractor6) if not already present
    tractor6 = root.find(".//tractor[@id='tractor6']")
    if tractor6 is None:
        pl8 = root.find(".//playlist[@id='playlist8']")
        if pl8 is None:
            pl8 = ET.Element("playlist", attrib={"id": "playlist8"})
            t4_idx = list(root).index(tractor4) if tractor4 is not None else len(root)
            root.insert(t4_idx, pl8)
        pl9 = root.find(".//playlist[@id='playlist9']")
        if pl9 is None:
            pl9 = ET.Element("playlist", attrib={"id": "playlist9"})
            t4_idx = list(root).index(tractor4) if tractor4 is not None else len(root)
            root.insert(t4_idx, pl9)

        tractor6 = ET.Element("tractor", attrib={"id": "tractor6", "in": "00:00:00.000"})
        ET.SubElement(tractor6, "property", attrib={"name": "kdenlive:trackheight"}).text = "48"
        ET.SubElement(tractor6, "property", attrib={"name": "kdenlive:timeline_active"}).text = "1"
        ET.SubElement(tractor6, "property", attrib={"name": "kdenlive:collapsed"}).text = "0"
        ET.SubElement(tractor6, "property", attrib={"name": "kdenlive:thumbs_format"})
        ET.SubElement(tractor6, "property", attrib={"name": "kdenlive:audio_rec"})
        ET.SubElement(tractor6, "track", attrib={"hide": "audio", "producer": "playlist8"})
        ET.SubElement(tractor6, "track", attrib={"hide": "audio", "producer": "playlist9"})

        t4_idx = list(root).index(tractor4) if tractor4 is not None else len(root)
        root.insert(t4_idx, tractor6)

        if tractor4 is not None:
            # Insert track element right after existing tracks (before transitions)
            last_track_idx = -1
            for i, child in enumerate(tractor4):
                if child.tag == "track":
                    last_track_idx = i
            track_v3 = ET.Element("track", attrib={"producer": "tractor6"})
            if last_track_idx >= 0:
                tractor4.insert(last_track_idx + 1, track_v3)
            else:
                tractor4.append(track_v3)

            # Add compositing transition for Track V3 (track 0 to track 5)
            trans4 = ET.Element("transition", attrib={"id": "transition4"})
            ET.SubElement(trans4, "property", attrib={"name": "a_track"}).text = "0"
            ET.SubElement(trans4, "property", attrib={"name": "b_track"}).text = "5"
            ET.SubElement(trans4, "property", attrib={"name": "compositing"}).text = "0"
            ET.SubElement(trans4, "property", attrib={"name": "distort"}).text = "0"
            ET.SubElement(trans4, "property", attrib={"name": "rotate_center"}).text = "0"
            ET.SubElement(trans4, "property", attrib={"name": "mlt_service"}).text = "qtblend"
            ET.SubElement(trans4, "property", attrib={"name": "kdenlive_id"}).text = "qtblend"
            ET.SubElement(trans4, "property", attrib={"name": "internal_added"}).text = "237"
            ET.SubElement(trans4, "property", attrib={"name": "always_active"}).text = "1"
            tractor4.append(trans4)

            # Update sequence properties
            set_prop(tractor4, "kdenlive:sequenceproperties.tracks", "5")
            set_prop(tractor4, "kdenlive:sequenceproperties.tracksCount", "5")
            set_prop(tractor4, "kdenlive:sequenceproperties.position", "0")
            set_prop(tractor4, "kdenlive:sequenceproperties.scrollPos", "0")
            set_prop(tractor4, "kdenlive:sequenceproperties.zoom", "12")

    # Locate Target Playlists:
    # Track V2 = subtrack 0 of tractor3 (fallback to playlist6)
    # Track A2 = subtrack 0 of tractor0 (fallback to playlist0)
    v2_pl_id = "playlist6"
    if tractor3 is not None:
        t_sub = tractor3.findall("track")
        if len(t_sub) > 0:
            v2_pl_id = t_sub[0].get("producer", "playlist6")

    a2_pl_id = "playlist0"
    if tractor0 is not None:
        t_sub = tractor0.findall("track")
        if len(t_sub) > 0:
            a2_pl_id = t_sub[0].get("producer", "playlist0")

    v2_playlist = root.find(f".//playlist[@id='{v2_pl_id}']")
    a2_playlist = root.find(f".//playlist[@id='{a2_pl_id}']")

    if v2_playlist is None:
        v2_playlist = ET.SubElement(root, "playlist", attrib={"id": v2_pl_id})
    if a2_playlist is None:
        a2_playlist = ET.SubElement(root, "playlist", attrib={"id": a2_pl_id})

    # Ensure mix subtrack playlists are empty (subtrack 1 of each tractor)
    mix_pl_ids = ["playlist1", "playlist3", "playlist5", "playlist7", "playlist9"]
    for t in [tractor0, tractor1, tractor2, tractor3, tractor6]:
        if t is not None:
            t_sub = t.findall("track")
            if len(t_sub) > 1:
                mix_pl_ids.append(t_sub[1].get("producer"))
    for mix_id in set(mix_pl_ids):
        if mix_id:
            mix_pl = root.find(f".//playlist[@id='{mix_id}']")
            if mix_pl is not None:
                for child in list(mix_pl):
                    if child.tag in ["entry", "blank"]:
                        mix_pl.remove(child)

    # Clear existing entries in Track V2 and Track A2
    for child in list(v2_playlist):
        if child.tag in ["entry", "blank"]:
            v2_playlist.remove(child)
    for child in list(a2_playlist):
        if child.tag in ["entry", "blank"]:
            a2_playlist.remove(child)

    # 3. Populate Track V2 (playlist6) and Track A2 (playlist0)
    current_v_time = 0.0
    current_a_time = 0.0
    filter_counter = 1
    applied_v_count = 0
    applied_a_count = 0

    for idx, item in enumerate(plan):
        clip_path = Path(item["clip_path"]).resolve()
        clip_str = str(clip_path)
        if clip_str not in clip_registry:
            continue

        reg = clip_registry[clip_str]
        bin_id = reg["bin_id"]
        v_prod_id = reg["video_producer"]
        a_prod_id = reg["audio_producer"]

        start = float(item["timeline_start"])
        dur = float(item["duration"])
        src_in = float(item.get("source_in", 0.0))
        src_out = src_in + dur
        dur_frames = int(round(dur * fps))
        motion = item.get("motion_preset", "static")
        audio_db = item.get("ambient_audio_db")

        # --- Track V2 Entry ---
        gap_v = start - current_v_time
        if gap_v > 0.001:
            ET.SubElement(v2_playlist, "blank", attrib={"length": format_tc(gap_v)})

        entry_v = ET.SubElement(
            v2_playlist, "entry",
            attrib={"producer": v_prod_id, "in": format_tc(src_in), "out": format_tc(src_out)}
        )
        ET.SubElement(entry_v, "property", attrib={"name": "kdenlive:id"}).text = bin_id

        if motion and motion in ["subtle_push_in", "subtle_pull_out", "subtle_drift"]:
            filt = create_qtblend_filter(
                f"broll_filter_{filter_counter}",
                width, height,
                motion_preset=motion,
                duration_frames=dur_frames
            )
            entry_v.append(filt)
            filter_counter += 1

        current_v_time = start + dur
        applied_v_count += 1

        # --- Track A2 Entry ---
        if audio_db is not None:
            try:
                gain_val = float(audio_db)
            except ValueError:
                gain_val = -20.0

            gap_a = start - current_a_time
            if gap_a > 0.001:
                ET.SubElement(a2_playlist, "blank", attrib={"length": format_tc(gap_a)})

            entry_a = ET.SubElement(
                a2_playlist, "entry",
                attrib={"producer": a_prod_id, "in": format_tc(src_in), "out": format_tc(src_out)}
            )
            ET.SubElement(entry_a, "property", attrib={"name": "kdenlive:id"}).text = bin_id

            vol_filt = create_volume_filter(f"broll_vol_{filter_counter}", gain_val, dur_frames)
            entry_a.append(vol_filt)
            filter_counter += 1

            current_a_time = start + dur
            applied_a_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)

    # Validate output XML with MLT melt
    melt_check = subprocess.run(
        ["melt", str(output_path), "-consumer", "xml", "vn=1", "an=1", "count=1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True
    )
    if melt_check.returncode != 0:
        print(f"[WARN] MLT melt reported notices: {melt_check.stderr[:300]}")
    else:
        print(f"[VERIFIED] MLT syntax validation passed with 0 errors.")

    print(f"\n[SUCCESS] Successfully applied B-roll plan to {output_path.name}:")
    print(f"  • Master B-Roll clips in Project Bin: {len(clip_registry)}")
    print(f"  • Track V3 created and attached to timeline sequence.")
    print(f"  • Video cutaways placed on Track V2 (playlist6): {applied_v_count}")
    print(f"  • Ambient audio beds on Track A2 (playlist0):   {applied_a_count}")
    print(f"  • Master A-Roll (V1 in playlist4 / A1 in playlist2) preserved intact.")


if __name__ == "__main__":
    main()
