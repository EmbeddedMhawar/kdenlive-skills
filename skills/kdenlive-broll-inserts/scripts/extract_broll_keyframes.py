#!/usr/bin/env -S uv run --python 3.12 python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
extract_broll_keyframes.py - Extract visual keyframe thumbnails and technical metadata
from B-roll video footage for automated cataloging and semantic placement.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {".mov", ".mp4", ".mkv", ".m4v", ".webm", ".avi"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract keyframe thumbnails and metadata from B-roll video footage."
    )
    parser.add_argument(
        "--input-dir", "-i", type=str, required=True,
        help="Directory containing B-roll footage files (searched non-recursively by default, or recursively)."
    )
    parser.add_argument(
        "--output-dir", "-o", type=str, required=True,
        help="Directory to save extracted keyframe images and inventory JSON."
    )
    parser.add_argument(
        "--proxies-dir", "-p", type=str, default=None,
        help="Optional directory containing editing proxies to associate with source clips."
    )
    parser.add_argument(
        "--generate-proxies", action="store_true",
        help="Automatically transcode 540p editing proxies for clips missing them in --proxies-dir."
    )
    parser.add_argument(
        "--num-keyframes", "-n", type=int, default=3,
        help="Number of representative keyframes to extract per clip (default: 3)."
    )
    parser.add_argument(
        "--recursive", "-r", action="store_true",
        help="Scan input directory recursively for video files."
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


def probe_file(file_path: Path) -> dict:
    """Probe video file for streams, duration, resolution, and fps."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate",
        "-of", "json",
        str(file_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        return {}

    data = json.loads(res.stdout)
    duration = float(data.get("format", {}).get("duration", 0.0))

    video_stream = None
    has_audio = False
    for st in data.get("streams", []):
        if st.get("codec_type") == "video" and video_stream is None:
            video_stream = st
        elif st.get("codec_type") == "audio":
            has_audio = True

    if not video_stream:
        return {}

    w = int(video_stream.get("width", 0))
    h = int(video_stream.get("height", 0))

    fps_str = video_stream.get("avg_frame_rate", "60/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) > 0 else 60.0
    else:
        fps = float(fps_str) if fps_str else 60.0

    return {
        "duration": duration,
        "width": w,
        "height": h,
        "fps": round(fps, 3),
        "video_codec": video_stream.get("codec_name", "unknown"),
        "has_audio": has_audio,
    }


def find_proxy(file_path: Path, proxies_dir: Path | None) -> str | None:
    """Check if an editing proxy file exists for the given clip."""
    if not proxies_dir or not proxies_dir.is_dir():
        return None

    stem = file_path.stem
    candidates = [
        proxies_dir / f"{stem}_proxy.mov",
        proxies_dir / f"{stem}_proxy.mp4",
        proxies_dir / f"{stem}.mov",
        proxies_dir / f"{stem}.mp4",
    ]
    for cand in candidates:
        if cand.is_file():
            return str(cand.resolve())
    return None


def extract_thumbnails(video_path: Path, out_dir: Path, duration: float, n_frames: int) -> list[dict]:
    """Extract representative keyframe thumbnails at evenly spaced timestamps."""
    if duration <= 0:
        return []

    # Calculate timestamps (e.g. 15%, 50%, 85% for n=3)
    timestamps = []
    if n_frames == 1:
        timestamps = [duration * 0.5]
    else:
        step = duration / (n_frames + 1)
        timestamps = [step * (i + 1) for i in range(n_frames)]

    thumbs = []
    stem = video_path.stem

    for idx, ts in enumerate(timestamps):
        thumb_name = f"{stem}_thumb_{idx + 1:02d}.jpg"
        thumb_path = out_dir / thumb_name

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", f"{ts:.3f}",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "3",
            "-vf", "scale=960:-2",
            str(thumb_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and thumb_path.is_file():
            thumbs.append({
                "index": idx + 1,
                "timestamp_sec": round(ts, 2),
                "path": str(thumb_path.resolve()),
            })

    return thumbs


def main():
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    proxies_dir = Path(args.proxies_dir).resolve() if args.proxies_dir else None

    if not input_dir.is_dir():
        print(f"[ERROR] Input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect video files
    if args.recursive:
        video_files = [p for p in input_dir.rglob("*") if p.suffix.lower() in VIDEO_EXTENSIONS and p.is_file()]
    else:
        video_files = [p for p in input_dir.glob("*") if p.suffix.lower() in VIDEO_EXTENSIONS and p.is_file()]

    video_files.sort(key=lambda p: p.name)

    if not video_files:
        print(f"[WARN] No video files found in: {input_dir}")
        sys.exit(0)

    print(f"[INFO] Scanning {len(video_files)} video clips in {input_dir}...")
    inventory = []

    for vf in video_files:
        meta = probe_file(vf)
        if not meta or meta["duration"] <= 0.2:
            continue

        proxy_path = find_proxy(vf, proxies_dir)
        if not proxy_path and args.generate_proxies and proxies_dir:
            print(f"  ⚡ Transcoding proxy for {vf.name}...")
            proxy_path = generate_proxy(vf, proxies_dir)

        thumbs = extract_thumbnails(vf, output_dir, meta["duration"], args.num_keyframes)

        item = {
            "file_name": vf.name,
            "file_path": str(vf.resolve()),
            "proxy_path": proxy_path,
            "duration": round(meta["duration"], 2),
            "width": meta["width"],
            "height": meta["height"],
            "fps": meta["fps"],
            "has_audio": meta["has_audio"],
            "keyframes": thumbs,
        }
        inventory.append(item)
        print(f"  ✓ {vf.name} ({meta['duration']:.1f}s, {meta['width']}x{meta['height']}) -> {len(thumbs)} keyframes")

    inventory_path = output_dir / "broll_inventory.json"
    with open(inventory_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)

    print(f"\n[SUCCESS] Indexed {len(inventory)} clips.")
    print(f"Keyframe thumbnails saved to: {output_dir}")
    print(f"Inventory saved to: {inventory_path}")


if __name__ == "__main__":
    main()
