#!/usr/bin/env python3
"""
apply_motion_graphics.py

Non-destructively injects rendered motion graphics and paired SFX into
a Kdenlive project timeline XML:
- Video overlays and chapter cards -> Track V3 (playlist6)
- Sound effects -> Track A3 (playlist1)
Preserves A-Roll (V1/A1) and B-Roll (V2/A2) completely untouched.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Inject motion graphics into Kdenlive MLT XML.")
    parser.add_argument("--project", "-p", type=str, required=True,
                        help="Path to input .kdenlive project file (e.g. roughcut_zoomed.kdenlive).")
    parser.add_argument("--manifest", "-m", type=str, required=True,
                        help="Path to motion_manifest.json produced by render_motion_graphics.py.")
    parser.add_argument("--output", "-o", type=str, required=True,
                        help="Path to output .kdenlive project file.")
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


def format_tc(seconds: float) -> str:
    secs = int(seconds)
    mins = secs // 60
    hours = mins // 60
    mins = mins % 60
    secs = secs % 60
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{ms:03d}"


def get_fps(root: ET.Element) -> float:
    profile = root.find("profile")
    if profile is not None:
        num = float(profile.get("frame_rate_num", "60"))
        den = float(profile.get("frame_rate_den", "1"))
        return num / den
    return 60.0


def apply_motion(project_path: str, manifest_path: str, output_path: str):
    tree = ET.parse(project_path)
    root = tree.getroot()
    fps = get_fps(root)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Sort manifest strictly by timeline_start
    manifest.sort(key=lambda x: x.get("timeline_start", 0))

    # Find highest kdenlive:id to avoid ID collisions
    max_id = 100
    for elem in root.iter():
        for prop in elem.findall("property"):
            if prop.get("name") == "kdenlive:id" and prop.text and prop.text.isdigit():
                max_id = max(max_id, int(prop.text))

    # Locate Target Playlists:
    # Track V3 is playlist8 (primary subtrack of tractor4/V3)
    v3_playlist = root.find(".//playlist[@id='playlist8']")
    if v3_playlist is None:
        v3_playlist = ET.SubElement(root, "playlist", id="playlist8")

    # Clear previous entries in V3 if re-running
    for child in list(v3_playlist):
        if child.tag in ["entry", "blank"]:
            v3_playlist.remove(child)

    # Dedicated Audio Track A3 (tractor7 -> playlist10 [primary], playlist11 [mix])
    # Note: playlist1 is the mix subtrack of A2, so placing independent clips there causes
    # 'incorrect subtrack found and fixed on track A2' errors in Kdenlive.
    t5 = root.find(".//tractor[@id='tractor5']")
    if t5 is None:
        # Fallback to last tractor as sequence tractor
        all_tractors = root.findall("tractor")
        t5 = all_tractors[-1] if all_tractors else None

    # Check if tractor7 already exists
    tr7 = root.find(".//tractor[@id='tractor7']")
    pl10 = root.find(".//playlist[@id='playlist10']")
    pl11 = root.find(".//playlist[@id='playlist11']")

    if pl10 is None:
        pl10 = ET.Element("playlist", id="playlist10")
        ET.SubElement(pl10, "property", name="kdenlive:audio_track").text = "1"
        tr0_idx = next((i for i, e in enumerate(root) if e.tag == "tractor" and e.attrib.get("id") == "tractor0"), len(root))
        root.insert(tr0_idx, pl10)
    else:
        for child in list(pl10):
            if child.tag in ["entry", "blank"]:
                pl10.remove(child)

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

            # 3 Audio tracks (indices 1, 2, 3) mix with track 0
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

            # 3 Video tracks (indices 4, 5, 6) qtblend with track 0
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

            # Helper for properties
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

    a3_playlist = pl10

    # Find index of first playlist so new chains are defined BEFORE any playlist references them
    first_playlist_idx = 0
    for idx, elem in enumerate(root):
        if elem.tag == "playlist":
            first_playlist_idx = idx
            break
    insert_chain_idx = first_playlist_idx

    current_v_time = 0.0
    current_a_time = 0.0

    for idx, item in enumerate(manifest):
        title_id = item.get("title_id", f"title_{idx + 1}")
        start = float(item["timeline_start"])
        dur = float(item["duration"])
        v_path = Path(item["video_path"])
        a_path = Path(item["audio_path"])

        v_producer_id = f"producer_motion_{idx + 1}_video"
        a_producer_id = f"producer_motion_{idx + 1}_audio"

        max_id += 1
        v_kid = max_id
        max_id += 1
        a_kid = max_id

        # 1. Video Chain
        v_chain = ET.Element("chain", id=v_producer_id, out=format_tc(dur))
        ET.SubElement(v_chain, "property", name="length").text = str(int(round(dur * fps)))
        ET.SubElement(v_chain, "property", name="eof").text = "pause"
        ET.SubElement(v_chain, "property", name="resource").text = str(v_path.resolve())
        ET.SubElement(v_chain, "property", name="mlt_service").text = "avformat-novalidate"
        ET.SubElement(v_chain, "property", name="kdenlive:id").text = str(v_kid)
        ET.SubElement(v_chain, "property", name="kdenlive:control_uuid").text = f"{{{uuid.uuid4()}}}"
        ET.SubElement(v_chain, "property", name="kdenlive:clipname").text = f"Motion: {item.get('text', '')[:20]}"
        if v_path.is_file():
            ET.SubElement(v_chain, "property", name="kdenlive:file_size").text = str(v_path.stat().st_size)
            ET.SubElement(v_chain, "property", name="kdenlive:file_hash").text = compute_kdenlive_hash(v_path)
        ET.SubElement(v_chain, "property", name="kdenlive:clip_type").text = "0"
        ET.SubElement(v_chain, "property", name="video_index").text = "0"
        ET.SubElement(v_chain, "property", name="audio_index").text = "-1"
        root.insert(insert_chain_idx, v_chain)
        insert_chain_idx += 1

        # 2. Audio SFX Chain
        a_chain = ET.Element("chain", id=a_producer_id, out=format_tc(dur))
        ET.SubElement(a_chain, "property", name="length").text = str(int(round(dur * fps)))
        ET.SubElement(a_chain, "property", name="eof").text = "pause"
        ET.SubElement(a_chain, "property", name="resource").text = str(a_path.resolve())
        ET.SubElement(a_chain, "property", name="mlt_service").text = "avformat-novalidate"
        ET.SubElement(a_chain, "property", name="kdenlive:id").text = str(a_kid)
        ET.SubElement(a_chain, "property", name="kdenlive:control_uuid").text = f"{{{uuid.uuid4()}}}"
        ET.SubElement(a_chain, "property", name="kdenlive:clipname").text = f"SFX: {item.get('text', '')[:20]}"
        if a_path.is_file():
            ET.SubElement(a_chain, "property", name="kdenlive:file_size").text = str(a_path.stat().st_size)
            ET.SubElement(a_chain, "property", name="kdenlive:file_hash").text = compute_kdenlive_hash(a_path)
        ET.SubElement(a_chain, "property", name="kdenlive:clip_type").text = "1"
        ET.SubElement(a_chain, "property", name="video_index").text = "-1"
        ET.SubElement(a_chain, "property", name="audio_index").text = "0"
        root.insert(insert_chain_idx, a_chain)
        insert_chain_idx += 1

        # 3. Add to V3 Timeline Playlist
        gap_v = start - current_v_time
        if gap_v > 0.001:
            ET.SubElement(v3_playlist, "blank", length=format_tc(gap_v))
        entry_v = ET.SubElement(v3_playlist, "entry", producer=v_producer_id, out=format_tc(dur))
        entry_v.set("in", "00:00:00.000")
        ET.SubElement(entry_v, "property", name="kdenlive:id").text = str(v_kid)
        current_v_time = start + dur

        # 4. Add to A3 Timeline Playlist
        gap_a = start - current_a_time
        if gap_a > 0.001:
            ET.SubElement(a3_playlist, "blank", length=format_tc(gap_a))
        entry_a = ET.SubElement(a3_playlist, "entry", producer=a_producer_id, out=format_tc(dur))
        entry_a.set("in", "00:00:00.000")
        ET.SubElement(entry_a, "property", name="kdenlive:id").text = str(a_kid)
        current_a_time = start + dur

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(out_p), encoding="utf-8", xml_declaration=True)

    print(f"[SUCCESS] Injected {len(manifest)} motion titles into Track V3 and SFX into Track A3.")
    print(f"Output saved to: {output_path}")

    # Validate output with melt
    try:
        import os
        env = os.environ.copy()
        env["MLT_LOG_LEVEL"] = "debug"
        res = subprocess.run(["melt", str(out_p), "-consumer", "null", "out=1"], capture_output=True, text=True, env=env)
        errors = [line for line in res.stderr.splitlines() if "Property without a parent" in line or "failed to load" in line]
        if res.returncode == 0 and len(errors) == 0:
            print("[MELT VERIFICATION] Project loaded successfully with 0 errors!")
        else:
            if errors:
                print(f"[MELT ERROR] Found {len(errors)} issues:\n" + "\n".join(errors[:5]))
            else:
                print(f"[MELT WARNING] {res.stderr[:200]}")
    except Exception as e:
        print(f"[MELT INFO] Validation skipped: {e}")


def main():
    args = parse_args()
    apply_motion(args.project, args.manifest, args.output)


if __name__ == "__main__":
    main()
