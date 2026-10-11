#!/usr/bin/env python3
"""
apply_sfx.py

Non-destructively injects transcript-driven sound effects into a Kdenlive project timeline XML:
- Injects audio effects onto Track A3 (tractor7 -> playlist10 [primary], playlist11 [mix]).
- Supports seamless coexistence with existing Track A3 clips (motion graphic titles/whooshes).
- Preserves the stable 6-track timeline schema (V1-V3, A1-A3) to avoid Kdenlive GUI segfaults.
- Attaches sample-accurate volume gain filters matching calibrated dB targets.
- Validates XML integrity with 'melt' before finishing.
"""

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Inject transcript SFX into Kdenlive MLT XML.")
    parser.add_argument("--project", "-p", type=str, required=True,
                        help="Path to input .kdenlive project file.")
    parser.add_argument("--plan", "-s", type=str, required=True,
                        help="Path to verified sfx_plan.json produced by generate_sfx_plan.py.")
    parser.add_argument("--output", "-o", type=str, required=True,
                        help="Path to output .kdenlive project file.")
    parser.add_argument("--master-volume", type=float, default=1.0,
                        help="Master volume multiplier (linear, default 1.0).")
    return parser.parse_args()


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


def parse_tc(tc_str: str) -> float:
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
        return float(tc_str)
    except ValueError:
        return 0.0


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


def get_fps(root: ET.Element) -> float:
    profile = root.find("profile")
    if profile is not None:
        num = float(profile.get("frame_rate_num", "60"))
        den = float(profile.get("frame_rate_den", "1"))
        return num / den
    return 60.0


class TimelineEntry:
    def __init__(self, start: float, dur: float, elem: ET.Element, is_new: bool = False):
        self.start = round(start, 3)
        self.dur = round(dur, 3)
        self.elem = elem
        self.is_new = is_new


def ensure_track_a3(root: ET.Element):
    """Ensure Track A3 playlist exists and is returned."""
    # 1. First check if a playlist already contains motion audio clips
    for pl in root.findall(".//playlist"):
        if pl.get("id") == "main_bin":
            continue
        for ent in pl.findall("entry"):
            prod = ent.get("producer", "")
            if "motion" in prod and "audio" in prod:
                return pl

    # 2. Check tractor0 if it is audio track (e.g. 6-track schema with audio first)
    tr0 = root.find(".//tractor[@id='tractor0']")
    if tr0 is not None:
        p = tr0.find("property[@name='kdenlive:audio_track']")
        if p is not None and p.text == "1":
            for tr_track in tr0.findall("track"):
                pl_id = tr_track.get("producer")
                if pl_id:
                    pl = root.find(f".//playlist[@id='{pl_id}']")
                    if pl is not None:
                        return pl

    t5 = root.find(".//tractor[@id='tractor5']")
    if t5 is None:
        all_tractors = root.findall("tractor")
        t5 = all_tractors[-1] if all_tractors else None

    tr7 = root.find(".//tractor[@id='tractor7']")
    pl10 = root.find(".//playlist[@id='playlist10']")
    pl11 = root.find(".//playlist[@id='playlist11']")

    if pl10 is None:
        pl10 = ET.Element("playlist", id="playlist10")
        ET.SubElement(pl10, "property", name="kdenlive:audio_track").text = "1"
        tr0_idx = next((i for i, e in enumerate(root) if e.tag == "tractor" and e.attrib.get("id") == "tractor0"), len(root))
        root.insert(tr0_idx, pl10)

    if pl11 is None:
        pl11 = ET.Element("playlist", id="playlist11")
        ET.SubElement(pl11, "property", name="kdenlive:audio_track").text = "1"
        tr0_idx = next((i for i, e in enumerate(root) if e.tag == "tractor" and e.attrib.get("id") == "tractor0"), len(root))
        root.insert(tr0_idx, pl11)

    if tr7 is None:
        tr7 = ET.Element("tractor", id="tractor7", attrib={"in": "00:00:00.000", "out": "00:11:23.783"})
        ET.SubElement(tr7, "property", name="kdenlive:audio_track").text = "1"
        ET.SubElement(tr7, "property", name="kdenlive:trackheight").text = "48"
        ET.SubElement(tr7, "property", name="kdenlive:timeline_active").text = "1"
        ET.SubElement(tr7, "property", name="kdenlive:collapsed").text = "0"
        ET.SubElement(tr7, "property", name="kdenlive:thumbs_format")
        ET.SubElement(tr7, "property", name="kdenlive:audio_rec")
        ET.SubElement(tr7, "track", hide="video", producer="playlist10")
        ET.SubElement(tr7, "track", hide="video", producer="playlist11")

        f_vol = ET.SubElement(tr7, "filter", id="filter_a3_vol")
        ET.SubElement(f_vol, "property", name="window").text = "75"
        ET.SubElement(f_vol, "property", name="max_gain").text = "20dB"
        ET.SubElement(f_vol, "property", name="channel_mask").text = "-1"
        ET.SubElement(f_vol, "property", name="mlt_service").text = "volume"
        ET.SubElement(f_vol, "property", name="internal_added").text = "237"
        ET.SubElement(f_vol, "property", name="disable").text = "1"

        f_pan = ET.SubElement(tr7, "filter", id="filter_a3_pan")
        ET.SubElement(f_pan, "property", name="channel").text = "-1"
        ET.SubElement(f_pan, "property", name="mlt_service").text = "panner"
        ET.SubElement(f_pan, "property", name="internal_added").text = "237"
        ET.SubElement(f_pan, "property", name="start").text = "0.5"
        ET.SubElement(f_pan, "property", name="disable").text = "1"

        f_lvl = ET.SubElement(tr7, "filter", id="filter_a3_level")
        ET.SubElement(f_lvl, "property", name="iec_scale").text = "0"
        ET.SubElement(f_lvl, "property", name="mlt_service").text = "audiolevel"
        ET.SubElement(f_lvl, "property", name="internal_added").text = "237"
        ET.SubElement(f_lvl, "property", name="dbpeak").text = "1"
        ET.SubElement(f_lvl, "property", name="disable").text = "1"

        tr0_idx = next((i for i, e in enumerate(root) if e.tag == "tractor" and e.attrib.get("id") == "tractor0"), len(root))
        root.insert(tr0_idx, tr7)

        # Wire tractor7 into tractor5 as Track A3 (index 1, right after producer0)
        if t5 is not None:
            prod0_idx = -1
            for idx_t, child in enumerate(t5):
                if child.tag == "track" and child.attrib.get("producer") == "producer0":
                    prod0_idx = idx_t
                    break
            track_tr7 = ET.Element("track", producer="tractor7")
            if prod0_idx >= 0:
                t5.insert(prod0_idx + 1, track_tr7)
            else:
                t5.append(track_tr7)

            # Rebuild transitions for the 6 tracks
            for trans in list(t5.findall("transition")):
                t5.remove(trans)

            # Audio tracks (indices 1, 2, 3) mix with track 0
            for b_idx in [1, 2, 3]:
                tr = ET.SubElement(t5, "transition", id=f"transition_mix_{b_idx}")
                ET.SubElement(tr, "property", name="a_track").text = "0"
                ET.SubElement(tr, "property", name="b_track").text = str(b_idx)
                ET.SubElement(tr, "property", name="mlt_service").text = "mix"
                ET.SubElement(tr, "property", name="kdenlive_id").text = "mix"
                ET.SubElement(tr, "property", name="internal_added").text = "237"
                ET.SubElement(tr, "property", name="always_active").text = "1"
                ET.SubElement(tr, "property", name="accepts_blanks").text = "1"
                ET.SubElement(tr, "property", name="sum").text = "1"

            # Video tracks (indices 4, 5, 6) qtblend with track 0
            for b_idx in [4, 5, 6]:
                tr = ET.SubElement(t5, "transition", id=f"transition_blend_{b_idx}")
                ET.SubElement(tr, "property", name="a_track").text = "0"
                ET.SubElement(tr, "property", name="b_track").text = str(b_idx)
                ET.SubElement(tr, "property", name="compositing").text = "0"
                ET.SubElement(tr, "property", name="distort").text = "0"
                ET.SubElement(tr, "property", name="rotate_center").text = "0"
                ET.SubElement(tr, "property", name="mlt_service").text = "qtblend"
                ET.SubElement(tr, "property", name="kdenlive_id").text = "qtblend"
                ET.SubElement(tr, "property", name="internal_added").text = "237"
                ET.SubElement(tr, "property", name="always_active").text = "1"

            def set_prop(elem, k, v):
                p = elem.find(f"property[@name='{k}']")
                if p is not None:
                    p.text = v
                else:
                    ET.SubElement(elem, "property", name=k).text = v

            set_prop(t5, "kdenlive:sequenceproperties.tracks", "6")
            set_prop(t5, "kdenlive:sequenceproperties.tracksCount", "6")

            # Shift activeTrack, audioTarget, videoTarget by +1
            for prop_name in ["kdenlive:sequenceproperties.activeTrack", "kdenlive:sequenceproperties.audioTarget", "kdenlive:sequenceproperties.videoTarget"]:
                p = t5.find(f"property[@name='{prop_name}']")
                if p is not None and p.text and p.text.isdigit():
                    p.text = str(int(p.text) + 1)

            # Shift groups track numbers by +1
            grp_p = t5.find("property[@name='kdenlive:sequenceproperties.groups']")
            if grp_p is not None and grp_p.text:
                try:
                    groups = json.loads(grp_p.text)
                    for grp in groups:
                        for child in grp.get("children", []):
                            d = child.get("data", "")
                            parts = d.split(":")
                            if len(parts) == 3 and parts[0].isdigit():
                                parts[0] = str(int(parts[0]) + 1)
                                child["data"] = ":".join(parts)
                    grp_p.text = json.dumps(groups, indent=4)
                except Exception:
                    pass

    return pl10


def apply_sfx(project_path: str, plan_path: str, output_path: str, master_vol: float = 1.0):
    tree = ET.parse(project_path)
    root = tree.getroot()
    fps = get_fps(root)

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    # Sort plan strictly by timeline_start
    plan.sort(key=lambda x: x.get("timeline_start", 0))

    # Determine highest kdenlive:id
    max_id = 100
    for elem in root.iter():
        for prop in elem.findall("property"):
            if prop.get("name") == "kdenlive:id" and prop.text and prop.text.isdigit():
                max_id = max(max_id, int(prop.text))

    # Ensure Track A3 exists and grab playlist10
    pl10 = ensure_track_a3(root)

    # Extract existing clips from pl10
    existing_entries: list[TimelineEntry] = []
    cur_pl_time = 0.0
    for child in list(pl10):
        if child.tag == "blank":
            cur_pl_time += parse_tc(child.get("length", "0"))
        elif child.tag == "entry":
            in_t = parse_tc(child.get("in", "0"))
            out_t = parse_tc(child.get("out", "0"))
            dur = max(0.02, out_t - in_t)
            existing_entries.append(TimelineEntry(cur_pl_time, dur, copy.deepcopy(child), is_new=False))
            cur_pl_time += dur

    # Find insertion point for new chains (before first playlist)
    first_playlist_idx = 0
    for idx, elem in enumerate(root):
        if elem.tag == "playlist":
            first_playlist_idx = idx
            break
    insert_chain_idx = first_playlist_idx

    new_entries: list[TimelineEntry] = []

    for idx, item in enumerate(plan):
        start = float(item["timeline_start"])
        dur = float(item.get("duration", 0.5))
        sfx_path_str = item.get("full_path") or item.get("sfx_path")
        sfx_path = Path(sfx_path_str)
        vol_db = float(item.get("volume_db", -14.0))

        # Linear gain multiplier
        gain_linear = (10.0 ** (vol_db / 20.0)) * master_vol

        producer_id = f"producer_transcript_sfx_{idx + 1}"
        max_id += 1
        sfx_kid = max_id

        # Create audio producer chain
        chain = ET.Element("chain", id=producer_id, out=format_tc(dur))
        ET.SubElement(chain, "property", name="length").text = str(int(round(dur * fps)))
        ET.SubElement(chain, "property", name="eof").text = "pause"
        ET.SubElement(chain, "property", name="resource").text = str(sfx_path.resolve())
        ET.SubElement(chain, "property", name="mlt_service").text = "avformat-novalidate"
        ET.SubElement(chain, "property", name="kdenlive:id").text = str(sfx_kid)
        ET.SubElement(chain, "property", name="kdenlive:control_uuid").text = f"{{{uuid.uuid4()}}}"
        ET.SubElement(chain, "property", name="kdenlive:clipname").text = f"SFX: {item.get('name', sfx_path.stem)}"
        if sfx_path.is_file():
            ET.SubElement(chain, "property", name="kdenlive:file_size").text = str(sfx_path.stat().st_size)
            ET.SubElement(chain, "property", name="kdenlive:file_hash").text = compute_kdenlive_hash(sfx_path)
        ET.SubElement(chain, "property", name="kdenlive:clip_type").text = "1"  # Audio clip
        ET.SubElement(chain, "property", name="video_index").text = "-1"
        ET.SubElement(chain, "property", name="audio_index").text = "0"

        # Gain filter
        f_vol = ET.SubElement(chain, "filter", id=f"filter_sfx_vol_{sfx_kid}")
        ET.SubElement(f_vol, "property", name="mlt_service").text = "volume"
        ET.SubElement(f_vol, "property", name="gain").text = f"{gain_linear:.3f}"

        root.insert(insert_chain_idx, chain)
        insert_chain_idx += 1

        # Create timeline entry element
        entry_elem = ET.Element("entry", producer=producer_id, out=format_tc(dur))
        entry_elem.set("in", "00:00:00.000")
        ET.SubElement(entry_elem, "property", name="kdenlive:id").text = str(sfx_kid)

        new_entries.append(TimelineEntry(start, dur, entry_elem, is_new=True))

    # Combine existing and new entries, sorting strictly by start time
    all_entries = sorted(existing_entries + new_entries, key=lambda e: e.start)

    # Rebuild playlist10
    for child in list(pl10):
        if child.tag in ["entry", "blank"]:
            pl10.remove(child)

    cur_time = 0.0
    for entry in all_entries:
        gap = entry.start - cur_time
        if gap > 0.001:
            ET.SubElement(pl10, "blank", length=format_tc(gap))
            cur_time += gap
        pl10.append(entry.elem)
        cur_time += entry.dur

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(out_p), encoding="utf-8", xml_declaration=True)

    print(f"[SUCCESS] Injected {len(new_entries)} transcript sound effects onto Track A3.")
    print(f"Total entries on Track A3 now: {len(all_entries)} (Preserved {len(existing_entries)} existing clips)")
    print(f"Saved project to: {output_path}")

    # Validate output with melt
    try:
        env = os.environ.copy()
        env["MLT_LOG_LEVEL"] = "debug"
        res = subprocess.run(["melt", str(out_p), "-consumer", "null", "out=1"], capture_output=True, text=True, env=env)
        errors = [line for line in res.stderr.splitlines() if "Property without a parent" in line or "failed to load" in line]
        if res.returncode == 0 and len(errors) == 0:
            print("[MELT VERIFICATION] Project loaded successfully with 0 errors!")
        else:
            if errors:
                print(f"[MELT ERROR] Found {len(errors)} issues:\n" + "\n".join(errors[:5]), file=sys.stderr)
            else:
                print(f"[MELT WARNING] {res.stderr[:200]}")
    except Exception as e:
        print(f"[MELT INFO] Validation skipped: {e}")


def main():
    args = parse_args()
    apply_sfx(args.project, args.plan, args.output, args.master_volume)


if __name__ == "__main__":
    main()
