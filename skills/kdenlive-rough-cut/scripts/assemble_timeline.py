#!/usr/bin/env -S uv run --python 3.12 --with "opentimelineio" python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "opentimelineio",
# ]
# ///
"""
Assemble native Kdenlive (.kdenlive) and OpenTimelineIO (.otio) project files
with multi-clip support, timeline track structure, proxy integration, and Kdenlive hash calculation.
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


def probe_media(media_path: Path) -> dict:
    """Use ffprobe to get media resolution, framerate, and duration."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,sample_aspect_ratio,duration",
        "-show_entries",
        "format=duration,size",
        "-of",
        "json",
        str(media_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {media_path}: {res.stderr}")

    data = json.loads(res.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError(f"No video stream found in {media_path}")

    v = streams[0]
    width = int(v.get("width", 1920))
    height = int(v.get("height", 1080))

    r_fps = v.get("r_frame_rate", "60/1")
    if "/" in r_fps:
        num, den = map(int, r_fps.split("/"))
    else:
        num = int(float(r_fps) * 1000)
        den = 1000

    fmt = data.get("format", {})
    duration = float(v.get("duration") or fmt.get("duration") or 0.0)
    size = int(fmt.get("size") or media_path.stat().st_size)

    return {
        "width": width,
        "height": height,
        "fps_num": num,
        "fps_den": den,
        "fps": num / den,
        "duration": duration,
        "size": size,
    }


def format_tc(seconds: float) -> str:
    secs = int(seconds)
    mins = secs // 60
    hours = mins // 60
    mins = mins % 60
    secs = secs % 60
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{ms:03d}"


def tc_to_frame(tc: str, fps: float) -> int:
    h, m, rest = tc.split(":")
    s, ms = rest.split(".")
    sec = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    return int(round(sec * fps))


def sanitize_cuts(raw_cuts: list[dict], total_duration: float, padding: float) -> list[tuple[float, float, str]]:
    """Sort, apply padding, merge overlapping cuts, and clamp to total duration."""
    processed = []
    for item in raw_cuts:
        # Head is NEVER padded backwards: that bleeds into the previous (discarded) take.
        s = max(0.0, float(item["start"]))
        e = min(total_duration, float(item["end"]) + padding)
        label = item.get("label", "") or item.get("text", "") or "Cut"
        if e > s + 0.05:
            processed.append((s, e, label))

    processed.sort(key=lambda x: x[0])
    if not processed:
        return []

    merged = [processed[0]]
    for current in processed[1:]:
        prev_s, prev_e, prev_label = merged[-1]
        curr_s, curr_e, curr_label = current
        if curr_s <= prev_e:
            merged[-1] = (prev_s, max(prev_e, curr_e), f"{prev_label} + {curr_label}")
        else:
            merged.append(current)

    return merged


def set_or_add_prop(elem, name: str, value: str):
    for p in elem.findall("property"):
        if p.attrib.get("name") == name:
            p.text = str(value)
            return
    sub = ET.SubElement(elem, "property")
    sub.attrib["name"] = name
    sub.text = str(value)


def remove_prop(elem, name: str):
    for p in list(elem.findall("property")):
        if p.attrib.get("name") == name:
            elem.remove(p)


def get_template_path() -> Path:
    # 1. Look in skill resources
    res_path = Path(__file__).resolve().parent.parent / "resources" / "kdenlive_base_template.xml"
    if res_path.exists():
        return res_path
    # 2. Look in user videos
    user_path = Path.home() / "Videos" / "save.kdenlive"
    if user_path.exists():
        return user_path
    raise FileNotFoundError("Could not find kdenlive_base_template.xml")


def write_native_kdenlive(
    clip_data_list: list[tuple[Path, list[tuple[float, float, str]], dict, Path | None]],
    out_path: Path,
    title: str = "Rough Cut",
) -> None:
    template_path = get_template_path()
    tree = ET.parse(template_path)
    root = tree.getroot()

    root.attrib["root"] = str(out_path.parent.resolve())
    root.attrib["title"] = title

    first_meta = clip_data_list[0][2]
    profile = root.find("profile")
    profile.attrib["width"] = str(first_meta["width"])
    profile.attrib["height"] = str(first_meta["height"])
    profile.attrib["frame_rate_num"] = str(first_meta["fps_num"])
    profile.attrib["frame_rate_den"] = str(first_meta["fps_den"])
    profile.attrib["description"] = f"{first_meta['width']}x{first_meta['height']} {first_meta['fps']:.0f} fps"

    tmpl_chain_bin = root.find('.//chain[@id="chain2"]')
    tmpl_chain_audio = root.find('.//chain[@id="chain0"]')
    tmpl_chain_video = root.find('.//chain[@id="chain1"]')

    for ch in list(root):
        if ch.tag == "chain":
            root.remove(ch)

    pl_audio = root.find('.//playlist[@id="playlist2"]')
    pl_video = root.find('.//playlist[@id="playlist4"]')
    main_bin = root.find('.//playlist[@id="main_bin"]')

    set_or_add_prop(main_bin, "kdenlive:docproperties.enableproxy", "1")
    set_or_add_prop(main_bin, "kdenlive:docproperties.generateproxy", "0")
    set_or_add_prop(main_bin, "kdenlive:docproperties.enableexternalproxy", "0")

    for pl in [pl_audio, pl_video]:
        for child in list(pl):
            if child.tag in ["entry", "blank"]:
                pl.remove(child)

    tractor4_entry = None
    for child in list(main_bin):
        if child.tag == "entry":
            if child.attrib.get("producer") == "tractor4":
                tractor4_entry = child
            main_bin.remove(child)

    producer0_idx = 0
    for idx, child in enumerate(root):
        if child.attrib.get("id") == "producer0":
            producer0_idx = idx
            break

    total_sequence_seconds = 0.0
    cur_timeline_frame = 0
    av_groups = []
    fps = first_meta["fps"]
    clip_kdenlive_id = 2
    cache_proxy_dir = Path.home() / ".cache" / "kdenlive" / "proxy"
    cache_proxy_dir.mkdir(parents=True, exist_ok=True)

    for idx, (media_path, cuts, meta, proxy_path) in enumerate(clip_data_list):
        dur = meta["duration"]
        out_tc = format_tc(dur)
        length_frames = str(int(round(dur * meta["fps"])))
        file_hash = compute_kdenlive_hash(media_path)
        file_size = str(meta["size"])

        has_proxy = proxy_path is not None and proxy_path.exists() and proxy_path.stat().st_size > 1000

        if has_proxy:
            cache_link = cache_proxy_dir / f"{file_hash}.mov"
            if not cache_link.exists() or cache_link.is_symlink():
                try:
                    if cache_link.is_symlink() or cache_link.exists():
                        cache_link.unlink()
                    cache_link.symlink_to(proxy_path.resolve())
                except Exception:
                    pass

        cid_bin = f"chain_{idx}_bin"
        cid_audio = f"chain_{idx}_audio"
        cid_video = f"chain_{idx}_video"
        clip_uuid = f"{{{uuid.uuid4()}}}"

        # 1. Bin chain
        c_bin = copy.deepcopy(tmpl_chain_bin)
        c_bin.attrib["id"] = cid_bin
        c_bin.attrib["out"] = out_tc
        set_or_add_prop(c_bin, "resource", str(proxy_path.resolve()) if has_proxy else str(media_path.resolve()))
        set_or_add_prop(c_bin, "length", length_frames)
        set_or_add_prop(c_bin, "kdenlive:id", str(clip_kdenlive_id))
        set_or_add_prop(c_bin, "kdenlive:control_uuid", clip_uuid)
        set_or_add_prop(c_bin, "kdenlive:clipname", media_path.name)
        set_or_add_prop(c_bin, "kdenlive:file_size", file_size)
        set_or_add_prop(c_bin, "kdenlive:file_hash", file_hash)
        set_or_add_prop(c_bin, "kdenlive:clip_type", "0")
        set_or_add_prop(c_bin, "kdenlive:folderid", "-1")
        remove_prop(c_bin, "kdenlive:zone_in")
        remove_prop(c_bin, "kdenlive:zone_out")

        if has_proxy:
            set_or_add_prop(c_bin, "kdenlive:proxy", str(proxy_path.resolve()))
            set_or_add_prop(c_bin, "kdenlive:originalurl", str(media_path.resolve()))
            set_or_add_prop(c_bin, "kdenlive:original.resource", str(media_path.resolve()))
            set_or_add_prop(c_bin, "meta.media.width", "960")
            set_or_add_prop(c_bin, "meta.media.height", "540")
            set_or_add_prop(c_bin, "meta.media.0.codec.width", "960")
            set_or_add_prop(c_bin, "meta.media.0.codec.height", "540")

        root.insert(producer0_idx, c_bin)
        producer0_idx += 1

        # 2. Video chain
        c_vid = copy.deepcopy(tmpl_chain_video)
        c_vid.attrib["id"] = cid_video
        c_vid.attrib["out"] = out_tc
        set_or_add_prop(c_vid, "resource", str(proxy_path.resolve()) if has_proxy else str(media_path.resolve()))
        set_or_add_prop(c_vid, "length", length_frames)
        set_or_add_prop(c_vid, "kdenlive:id", str(clip_kdenlive_id))
        set_or_add_prop(c_vid, "kdenlive:control_uuid", clip_uuid)
        set_or_add_prop(c_vid, "kdenlive:clipname", media_path.name)
        set_or_add_prop(c_vid, "kdenlive:file_size", file_size)
        set_or_add_prop(c_vid, "kdenlive:file_hash", file_hash)
        set_or_add_prop(c_vid, "kdenlive:clip_type", "0")
        set_or_add_prop(c_vid, "kdenlive:folderid", "-1")
        remove_prop(c_vid, "kdenlive:zone_in")
        remove_prop(c_vid, "kdenlive:zone_out")

        if has_proxy:
            set_or_add_prop(c_vid, "kdenlive:proxy", str(proxy_path.resolve()))
            set_or_add_prop(c_vid, "kdenlive:originalurl", str(media_path.resolve()))
            set_or_add_prop(c_vid, "kdenlive:original.resource", str(media_path.resolve()))
            set_or_add_prop(c_vid, "meta.media.width", "960")
            set_or_add_prop(c_vid, "meta.media.height", "540")
            set_or_add_prop(c_vid, "meta.media.0.codec.width", "960")
            set_or_add_prop(c_vid, "meta.media.0.codec.height", "540")

        root.insert(producer0_idx, c_vid)
        producer0_idx += 1

        # 3. Audio chain
        c_aud = copy.deepcopy(tmpl_chain_audio)
        c_aud.attrib["id"] = cid_audio
        c_aud.attrib["out"] = out_tc
        set_or_add_prop(c_aud, "resource", str(media_path.resolve()))
        set_or_add_prop(c_aud, "length", length_frames)
        set_or_add_prop(c_aud, "kdenlive:id", str(clip_kdenlive_id))
        set_or_add_prop(c_aud, "kdenlive:control_uuid", clip_uuid)
        set_or_add_prop(c_aud, "kdenlive:clipname", media_path.name)
        set_or_add_prop(c_aud, "kdenlive:file_size", file_size)
        set_or_add_prop(c_aud, "kdenlive:file_hash", file_hash)
        set_or_add_prop(c_aud, "kdenlive:clip_type", "0")
        set_or_add_prop(c_aud, "kdenlive:folderid", "-1")
        remove_prop(c_aud, "kdenlive:zone_in")
        remove_prop(c_aud, "kdenlive:zone_out")

        root.insert(producer0_idx, c_aud)
        producer0_idx += 1

        # Bin entry
        bin_entry = ET.SubElement(main_bin, "entry")
        bin_entry.attrib["producer"] = cid_bin
        bin_entry.attrib["in"] = "00:00:00.000"
        bin_entry.attrib["out"] = out_tc

        # Timeline cuts
        for s, e, _ in cuts:
            in_tc = format_tc(s)
            out_tc_cut = format_tc(e)

            entry_v = ET.SubElement(pl_video, "entry")
            entry_v.attrib["producer"] = cid_video
            entry_v.attrib["in"] = in_tc
            entry_v.attrib["out"] = out_tc_cut
            prop_v = ET.SubElement(entry_v, "property")
            prop_v.attrib["name"] = "kdenlive:id"
            prop_v.text = str(clip_kdenlive_id)

            entry_a = ET.SubElement(pl_audio, "entry")
            entry_a.attrib["producer"] = cid_audio
            entry_a.attrib["in"] = in_tc
            entry_a.attrib["out"] = out_tc_cut
            prop_a = ET.SubElement(entry_a, "property")
            prop_a.attrib["name"] = "kdenlive:id"
            prop_a.text = str(clip_kdenlive_id)

            inf = tc_to_frame(in_tc, fps)
            outf = tc_to_frame(out_tc_cut, fps)
            dur_f = max(1, outf - inf + 1)

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

            cur_timeline_frame += dur_f
            total_sequence_seconds += (e - s)

        clip_kdenlive_id += 1

    total_seq_tc = format_tc(total_sequence_seconds)
    total_seq_frames = str(int(round(total_sequence_seconds * first_meta["fps"])))

    if tractor4_entry is not None:
        tractor4_entry.attrib["out"] = total_seq_tc
        main_bin.append(tractor4_entry)

    producer0 = root.find('.//producer[@id="producer0"]')
    if producer0 is not None:
        producer0.attrib["out"] = total_seq_tc

    tractor1 = root.find('.//tractor[@id="tractor1"]')
    if tractor1 is not None:
        tractor1.attrib["out"] = total_seq_tc

    tractor2 = root.find('.//tractor[@id="tractor2"]')
    if tractor2 is not None:
        tractor2.attrib["out"] = total_seq_tc

    tractor4 = root.find('.//tractor[@id="tractor4"]')
    if tractor4 is not None:
        tractor4.attrib["out"] = total_seq_tc
        set_or_add_prop(tractor4, "kdenlive:duration", total_seq_tc)
        set_or_add_prop(tractor4, "kdenlive:maxduration", total_seq_frames)
        set_or_add_prop(tractor4, "kdenlive:id", "1")
        set_or_add_prop(tractor4, "kdenlive:clipname", "Sequence 1")
        set_or_add_prop(tractor4, "kdenlive:folderid", "2")
        set_or_add_prop(tractor4, "kdenlive:sequenceproperties.groups", json.dumps(av_groups, indent=4))
        set_or_add_prop(tractor4, "kdenlive:sequenceproperties.position", "0")
        set_or_add_prop(tractor4, "kdenlive:sequenceproperties.scrollPos", "0")
        set_or_add_prop(tractor4, "kdenlive:sequenceproperties.zonein", "0")
        set_or_add_prop(tractor4, "kdenlive:sequenceproperties.zoneout", total_seq_frames)

    tractor5 = root.find('.//tractor[@id="tractor5"]')
    if tractor5 is not None:
        tractor5.attrib["out"] = total_seq_tc
        track_tr4 = tractor5.find('.//track[@producer="tractor4"]')
        if track_tr4 is not None:
            track_tr4.attrib["out"] = total_seq_tc
        root.attrib["producer"] = "tractor5"

    tree.write(out_path, encoding="utf-8", xml_declaration=True)


def write_otio(
    clip_data_list: list[tuple[Path, list[tuple[float, float, str]], dict, Path | None]],
    out_path: Path,
) -> None:
    """Generate OpenTimelineIO (.otio) project file."""
    import opentimelineio as otio

    first_meta = clip_data_list[0][2]
    fps = first_meta["fps"]
    timeline = otio.schema.Timeline(name=out_path.stem)
    track = otio.schema.Track(name="Video 1", kind=otio.schema.TrackKind.Video)
    timeline.tracks.append(track)

    for media_path, cuts, meta, _ in clip_data_list:
        media_ref = otio.schema.ExternalReference(target_url=str(media_path.resolve()))
        for idx, (s, e, label) in enumerate(cuts):
            start_frame = max(0, int(round(s * fps)))
            duration_frames = max(1, int(round((e - s) * fps)))

            clip = otio.schema.Clip(
                name=f"{media_path.stem}_{idx + 1:03d}_{label[:25]}",
                media_reference=media_ref,
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(start_frame, fps),
                    duration=otio.opentime.RationalTime(duration_frames, fps),
                ),
            )
            track.append(clip)

    otio.adapters.write_to_file(timeline, str(out_path))


def main():
    parser = argparse.ArgumentParser(description="Assemble native Kdenlive and OTIO timelines from cuts")
    parser.add_argument("--media", "-m", required=True, nargs="+", help="Path to original raw media file(s)")
    parser.add_argument("--cuts", "-c", required=True, help="Path to cuts JSON file (or directory of cuts)")
    parser.add_argument("--output", "-o", required=True, help="Output project path (.kdenlive or .otio)")
    parser.add_argument("--proxy", "-p", default=None, help="Optional proxy file or directory containing proxies")
    parser.add_argument("--padding", type=float, default=0.08, help="TAIL padding in seconds (default: 0.08). Heads are never padded.")

    args = parser.parse_args()

    media_paths = [Path(m).resolve() for m in args.media]
    out_base = Path(args.output).resolve()
    out_kdenlive = out_base.with_suffix(".kdenlive")
    out_otio = out_base.with_suffix(".otio")

    cuts_arg = Path(args.cuts).resolve()
    clip_data_list = []

    for m in media_paths:
        if not m.exists():
            print(f"Warning: media file not found: {m}")
            continue

        meta = probe_media(m)

        # Locate cuts JSON
        if cuts_arg.is_dir():
            clean_stem = m.stem.replace("-005", "")
            stem_digits = "".join(filter(str.isdigit, clean_stem))
            cand_names = [
                f"cuts_{stem_digits}.json" if stem_digits else "",
                f"cuts_{clean_stem}.json",
                f"cuts_{m.stem}.json",
            ]
            cuts_file = None
            for cname in cand_names:
                if cname and (cuts_arg / cname).exists():
                    cuts_file = cuts_arg / cname
                    break
            if cuts_file is None:
                cuts_file = cuts_arg / f"cuts_{m.stem}.json"
        else:
            cuts_file = cuts_arg

        if not cuts_file.exists():
            print(f"Warning: cuts file not found for {m.name}: {cuts_file}")
            continue

        raw_cuts = json.loads(cuts_file.read_text(encoding="utf-8"))
        cuts = sanitize_cuts(raw_cuts, meta["duration"], args.padding)
        if not cuts:
            continue

        # Locate proxy
        proxy_path = None
        if args.proxy:
            p_arg = Path(args.proxy).resolve()
            if p_arg.is_dir():
                stem = m.stem.replace("-005", "")
                cand = p_arg / f"{stem}_proxy.mov"
                if cand.exists():
                    proxy_path = cand
            elif p_arg.is_file():
                proxy_path = p_arg
        else:
            # Check nearby proxies directory
            cand = m.parent / "proxies" / f"{m.stem.replace('-005', '')}_proxy.mov"
            if cand.exists():
                proxy_path = cand

        clip_data_list.append((m, cuts, meta, proxy_path))

    if not clip_data_list:
        sys.exit("Error: No valid clips with cuts to assemble.")

    # Write Kdenlive and OTIO
    write_native_kdenlive(clip_data_list, out_kdenlive, title=out_kdenlive.stem)
    print(f"✔ Generated Kdenlive project: {out_kdenlive}")

    try:
        write_otio(clip_data_list, out_otio)
        print(f"✔ Generated OpenTimelineIO project: {out_otio}")
    except Exception as e:
        print(f"Notice: OpenTimelineIO generation skipped ({e})")

    # Summary
    total_orig = sum(item[2]["duration"] for item in clip_data_list)
    total_cut = sum(sum(e - s for s, e, _ in item[1]) for item in clip_data_list)
    saved = total_orig - total_cut
    pct = (saved / total_orig * 100) if total_orig > 0 else 0

    total_segments = sum(len(item[1]) for item in clip_data_list)
    print(f"\n--- Cut Summary ---")
    print(f"Total clips: {len(clip_data_list)}")
    print(f"Total keeper segments: {total_segments}")
    print(f"Original duration: {total_orig:.1f}s ({total_orig/60:.1f}m)")
    print(f"Rough cut duration: {total_cut:.1f}s ({total_cut/60:.1f}m)")
    print(f"Cut out: {saved:.1f}s ({saved/60:.1f}m, -{pct:.1f}%)")


if __name__ == "__main__":
    main()
