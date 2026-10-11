#!/usr/bin/env -S uv run --python 3.12 python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
apply_redundancy_pruning.py - Ripple-delete approved redundant sentences/cuts from a Kdenlive project timeline.

Supports:
- Dual-mode: Works seamlessly on rough-cut timelines (V1/A1) and full multi-track projects (V1-V3, A1-A4).
- Ripple excision: Slices clips at exact deletion boundaries, removes the target segment, and ripple-shifts all downstream clips and blanks across all tracks.
- Native AVSplit sync: Rebuilds and synchronizes kdenlive:sequenceproperties.groups so audio/video ripple editing and scrubbing remain in lockstep.
- Safe backup: Automatically generates a timestamped .bak backup of the original project file.
"""

import argparse
import copy
import json
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def tc_to_frames(tc_str: str, fps: float) -> int:
    """Parse timecode string (HH:MM:SS.mmm or integer frames or float seconds) to integer frames."""
    tc_str = str(tc_str).strip()
    if ":" in tc_str:
        parts = tc_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return round((int(h) * 3600 + int(m) * 60 + float(s)) * fps)
        elif len(parts) == 2:
            m, s = parts
            return round((int(m) * 60 + float(s)) * fps)
    try:
        return round(float(tc_str) * fps)
    except ValueError:
        return 0


def frames_to_tc(frames: int, fps: float) -> str:
    """Format integer frames into Kdenlive-compatible HH:MM:SS.mmm format."""
    seconds = max(0.0, frames / fps)
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


def get_element_duration_frames(elem: ET.Element, fps: float) -> int:
    """Get frame-accurate duration of an entry or blank element."""
    if elem.tag == "entry":
        in_f = tc_to_frames(elem.attrib.get("in", "0"), fps)
        out_f = tc_to_frames(elem.attrib.get("out", "0"), fps)
        return max(0, out_f - in_f + 1)
    elif elem.tag == "blank":
        return max(0, tc_to_frames(elem.attrib.get("length", "0"), fps))
    return 0


def slice_playlist(playlist: ET.Element, del_start_frame: int, del_end_frame: int, fps: float) -> None:
    """
    Excise [del_start_frame, del_end_frame] from a playlist of entries and blanks.
    Downstream elements naturally shift earlier by (del_end_frame - del_start_frame) frames.
    Attributes of playlist are preserved strictly.
    """
    elements = list(playlist)
    non_clip_children = [ch for ch in elements if ch.tag not in ("entry", "blank")]
    clip_elements = [ch for ch in elements if ch.tag in ("entry", "blank")]

    new_clip_elements = []
    cur_f = 0

    for elem in clip_elements:
        dur_f = get_element_duration_frames(elem, fps)
        if dur_f <= 0:
            continue

        item_start_f = cur_f
        item_end_f = cur_f + dur_f
        cur_f = item_end_f

        # Case 1: Item ends at or before deletion start
        if item_end_f <= del_start_frame:
            new_clip_elements.append(elem)
            continue

        # Case 2: Item starts at or after deletion end
        if item_start_f >= del_end_frame:
            new_clip_elements.append(elem)
            continue

        # Case 3: Item is completely enveloped by deletion
        if item_start_f >= del_start_frame and item_end_f <= del_end_frame:
            continue

        # Case 4: Deletion falls strictly inside the item -> split into two
        if item_start_f < del_start_frame and item_end_f > del_end_frame:
            # Piece 1: item_start_f to del_start_frame
            p1 = copy.deepcopy(elem)
            dur1_f = del_start_frame - item_start_f
            if p1.tag == "entry":
                orig_in_f = tc_to_frames(p1.attrib.get("in", "0"), fps)
                p1.attrib["out"] = frames_to_tc(orig_in_f + dur1_f - 1, fps)
            elif p1.tag == "blank":
                p1.attrib["length"] = frames_to_tc(dur1_f, fps)
            new_clip_elements.append(p1)

            # Piece 2: del_end_frame to item_end_f
            p2 = copy.deepcopy(elem)
            dur2_f = item_end_f - del_end_frame
            if p2.tag == "entry":
                orig_in_f = tc_to_frames(p2.attrib.get("in", "0"), fps)
                orig_out_f = tc_to_frames(p2.attrib.get("out", "0"), fps)
                cut_offset_f = del_end_frame - item_start_f
                p2.attrib["in"] = frames_to_tc(orig_in_f + cut_offset_f, fps)
                p2.attrib["out"] = frames_to_tc(orig_out_f, fps)
            elif p2.tag == "blank":
                p2.attrib["length"] = frames_to_tc(dur2_f, fps)
            new_clip_elements.append(p2)
            continue

        # Case 5: Deletion overlaps the tail of the item -> trim tail
        if item_start_f < del_start_frame and item_end_f <= del_end_frame:
            p = copy.deepcopy(elem)
            dur_trimmed_f = del_start_frame - item_start_f
            if p.tag == "entry":
                orig_in_f = tc_to_frames(p.attrib.get("in", "0"), fps)
                p.attrib["out"] = frames_to_tc(orig_in_f + dur_trimmed_f - 1, fps)
            elif p.tag == "blank":
                p.attrib["length"] = frames_to_tc(dur_trimmed_f, fps)
            new_clip_elements.append(p)
            continue

        # Case 6: Deletion overlaps the head of the item -> trim head
        if item_start_f >= del_start_frame and item_end_f > del_end_frame:
            p = copy.deepcopy(elem)
            cut_offset_f = del_end_frame - item_start_f
            if p.tag == "entry":
                orig_in_f = tc_to_frames(p.attrib.get("in", "0"), fps)
                p.attrib["in"] = frames_to_tc(orig_in_f + cut_offset_f, fps)
            elif p.tag == "blank":
                dur_remaining_f = item_end_f - del_end_frame
                p.attrib["length"] = frames_to_tc(dur_remaining_f, fps)
            new_clip_elements.append(p)
            continue

    # Clear only child elements, keeping playlist attributes & text intact
    for ch in list(playlist):
        playlist.remove(ch)
    for prop in non_clip_children:
        playlist.append(prop)
    for clip in new_clip_elements:
        playlist.append(clip)


def shift_sequence_groups(root: ET.Element, del_start_frame: int, del_end_frame: int) -> None:
    """Shift existing groups in kdenlive:sequenceproperties.groups when ripple excising."""
    cut_frames = del_end_frame - del_start_frame
    for tr in root.findall(".//tractor"):
        for prop in tr.findall("property"):
            if prop.attrib.get("name") == "kdenlive:sequenceproperties.groups":
                try:
                    groups = json.loads(prop.text)
                except Exception:
                    continue
                new_groups = []
                for g in groups:
                    valid_group = True
                    new_children = []
                    for ch in g.get("children", []):
                        data = ch.get("data", "")
                        parts = data.split(":")
                        if len(parts) >= 2:
                            track_idx = parts[0]
                            f_idx = int(parts[1])
                            rest = parts[2:]
                            if del_start_frame <= f_idx < del_end_frame:
                                valid_group = False
                                break
                            elif f_idx >= del_end_frame:
                                f_idx -= cut_frames
                            new_data = f"{track_idx}:{f_idx}:" + ":".join(rest)
                            ch_copy = dict(ch)
                            ch_copy["data"] = new_data
                            new_children.append(ch_copy)
                        else:
                            new_children.append(ch)
                    if valid_group:
                        g_copy = dict(g)
                        g_copy["children"] = new_children
                        new_groups.append(g_copy)
                prop.text = json.dumps(new_groups, indent=4)


def rebuild_avsplit_groups(root: ET.Element, fps: float) -> None:
    """
    Rebuild kdenlive:sequenceproperties.groups for playlist2 (Audio Track 1)
    and playlist4 (Video Track 2) ensuring frame-accurate lockstep pairing.
    """
    pl_audio = root.find('.//playlist[@id="playlist2"]')
    pl_video = root.find('.//playlist[@id="playlist4"]')
    if pl_audio is None or pl_video is None:
        return

    audio_entries = [ch for ch in list(pl_audio) if ch.tag == "entry"]
    video_entries = [ch for ch in list(pl_video) if ch.tag == "entry"]

    if len(audio_entries) != len(video_entries):
        return

    av_groups = []
    cur_frame = 0

    for ve in video_entries:
        dur = get_element_duration(ve)
        dur_f = max(1, int(round(dur * fps)))

        av_groups.append({
            "children": [
                {
                    "data": f"1:{cur_frame}:-1",
                    "leaf": "clip",
                    "type": "Leaf",
                },
                {
                    "data": f"2:{cur_frame}:-1",
                    "leaf": "clip",
                    "type": "Leaf",
                },
            ],
            "type": "AVSplit",
        })
        cur_frame += dur_f

    # Find sequence tractor and update property
    for tr in root.findall(".//tractor"):
        for prop in tr.findall("property"):
            if prop.attrib.get("name") == "kdenlive:sequenceproperties.groups":
                prop.text = json.dumps(av_groups, indent=4)
                return


def apply_deletions(project_path: Path, deletions: list[dict], output_path: Path, backup: bool = True) -> float:
    """Execute ripple deletions on a Kdenlive MLT XML project."""
    if backup:
        bak_path = project_path.with_suffix(f"{project_path.suffix}.bak")
        shutil.copy2(project_path, bak_path)
        print(f"📦 Backup created: {bak_path}")

    tree = ET.parse(project_path)
    root = tree.getroot()

    # 1. Profile information
    profile = root.find("profile")
    if profile is None:
        raise ValueError("<profile> tag not found in Kdenlive project.")

    fps_num = int(profile.attrib.get("frame_rate_num", 60))
    fps_den = int(profile.attrib.get("frame_rate_den", 1))
    fps = fps_num / fps_den

    # 2. Identify track playlists
    track_playlists = []
    for pl in root.findall(".//playlist"):
        pl_id = pl.attrib.get("id", "")
        if pl_id.startswith("playlist") and pl_id not in ("playlist_bin", "main_bin"):
            track_playlists.append(pl)

    # 3. Find sequence tractor
    seq_tractor = None
    for tr in root.findall(".//tractor"):
        for prop in tr.findall("property"):
            if prop.attrib.get("name") in ("kdenlive:projectTractor", "kdenlive:sequenceproperties.documentuuid", "kdenlive:sequenceproperties.tracksCount"):
                seq_tractor = tr
                break
        if seq_tractor is not None:
            break

    if seq_tractor is None:
        tractors = root.findall(".//tractor")
        if tractors:
            seq_tractor = max(tractors, key=lambda t: len(t.findall("track")))

    # 4. Filter and sort deletions in DESCENDING order (so earlier timestamps stay intact)
    valid_deletions = []
    for d in deletions:
        s = float(d["start"])
        e = float(d["end"])
        if e > s + 0.02:
            valid_deletions.append((s, e, d.get("label", ""), d.get("reason", "")))

    valid_deletions.sort(key=lambda x: x[0], reverse=True)

    if not valid_deletions:
        print("No valid deletions to apply.")
        return 0.0

    print(f"Applying {len(valid_deletions)} ripple deletions in reverse chronological order...")

    total_excised_seconds = 0.0

    for s, e, label, reason in valid_deletions:
        s_f = int(round(s * fps))
        e_f = int(round(e * fps))
        dur_f = e_f - s_f
        dur_s = dur_f / fps
        total_excised_seconds += dur_s
        print(f"  ✂️ Deleting [{frames_to_tc(s_f, fps)} -> {frames_to_tc(e_f, fps)}] ({dur_s:.2f}s): {label} ({reason})")

        # Slice all track playlists across all tracks
        for pl in track_playlists:
            slice_playlist(pl, s_f, e_f, fps)

        # Shift sequence groups
        shift_sequence_groups(root, s_f, e_f)

    # 5. Synchronize AVSplit groups after all deletions
    rebuild_avsplit_groups(root, fps)

    # 6. Measure new total timeline duration
    new_tl_frames = 0
    ref_pl = root.find('.//playlist[@id="playlist4"]')
    if ref_pl is None:
        ref_pl = root.find('.//playlist[@id="playlist2"]')
    if ref_pl is not None:
        for ch in ref_pl:
            new_tl_frames += get_element_duration_frames(ch, fps)

    new_tl_duration = new_tl_frames / fps
    new_tc_str = frames_to_tc(new_tl_frames, fps)

    # 7. Update sequence duration properties and tractors
    if seq_tractor is not None:
        seq_tractor.attrib["out"] = new_tc_str
        for prop in seq_tractor.findall("property"):
            p_name = prop.attrib.get("name", "")
            if p_name == "kdenlive:duration":
                prop.text = new_tc_str
            elif p_name in ("kdenlive:maxduration", "kdenlive:sequenceproperties.zoneout"):
                prop.text = str(new_tl_frames)

    # Update track tractors out timecode
    for tr in root.findall(".//tractor"):
        if tr != seq_tractor:
            tr.attrib["out"] = new_tc_str

    # Update black_track if present
    for prod in root.findall(".//producer"):
        if prod.attrib.get("id") == "black_track":
            prod.attrib["out"] = new_tc_str
            for prop in prod.findall("property"):
                if prop.attrib.get("name") == "length":
                    prop.text = str(new_tl_frames)

    # Update project tractor or root producer
    proj_tr_id = root.attrib.get("producer")
    if proj_tr_id:
        proj_tr = root.find(f'.//tractor[@id="{proj_tr_id}"]')
        if proj_tr is not None:
            proj_tr.attrib["out"] = new_tc_str
            for tr_track in proj_tr.findall("track"):
                tr_track.attrib["out"] = new_tc_str

    # Update entry in main_bin for sequence tractor
    if seq_tractor is not None:
        seq_id = seq_tractor.attrib.get("id")
        for ent in root.findall(f'.//entry[@producer="{seq_id}"]'):
            ent.attrib["out"] = new_tc_str

    # 8. Write to output
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    orig_tc = frames_to_tc(new_tl_frames + int(round(total_excised_seconds * fps)), fps)
    print(f"✅ Successfully wrote pruned project: {output_path}")
    print(f"   Original -> New Duration: {orig_tc} -> {new_tc_str} (-{total_excised_seconds:.2f}s, -{int(round(total_excised_seconds * fps))} frames)")

    return total_excised_seconds


def main():
    parser = argparse.ArgumentParser(description="Ripple-delete redundant cuts from Kdenlive project")
    parser.add_argument("--project", "-p", required=True, type=Path, help="Input .kdenlive project file")
    parser.add_argument("--deletions", "-d", required=True, type=Path, help="Path to deletions JSON file")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output .kdenlive project file")
    parser.add_argument("--no-backup", action="store_true", help="Disable automatic backup creation")
    args = parser.parse_args()

    project_path = args.project.resolve()
    if not project_path.exists():
        sys.exit(f"Error: Project file not found: {project_path}")

    deletions_path = args.deletions.resolve()
    if not deletions_path.exists():
        sys.exit(f"Error: Deletions file not found: {deletions_path}")

    out_path = args.output
    if out_path is None:
        out_path = project_path.parent / f"{project_path.stem}_deduped.kdenlive"
    out_path = out_path.resolve()

    with open(deletions_path, "r", encoding="utf-8") as f:
        deletions_data = json.load(f)

    if not isinstance(deletions_data, list):
        sys.exit("Error: deletions JSON must be a list of deletion entries.")

    apply_deletions(
        project_path=project_path,
        deletions=deletions_data,
        output_path=out_path,
        backup=not args.no_backup,
    )


if __name__ == "__main__":
    main()
