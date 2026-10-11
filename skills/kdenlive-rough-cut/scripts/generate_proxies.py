#!/usr/bin/env python3
"""
Hardware-accelerated proxy generator for Kdenlive video editing.
Optimized for Intel QuickSync (VAAPI) with automatic ultrafast CPU fallback.
Produces intra-friendly (g=60, bf=0) lightweight proxy files for zero-lag timeline scrubbing.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def is_vaapi_available() -> bool:
    """Check if /dev/dri/renderD128 exists and ffmpeg supports vaapi."""
    dev = Path("/dev/dri/renderD128")
    if not dev.exists() or not os.access(dev, os.R_OK | os.W_OK):
        return False
    cmd = ["ffmpeg", "-init_hw_device", "vaapi=vaapi0:/dev/dri/renderD128", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1", "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-f", "null", "-"]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0


def generate_proxy(input_path: Path, output_path: Path, width: int = 960, use_vaapi: bool = True) -> bool:
    """Generate proxy file using VAAPI hardware acceleration if available, else ultrafast CPU."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_path.with_suffix(".tmp.mov")

    if use_vaapi:
        # Full GPU pipeline: HW decode -> HW scale -> HW h264_vaapi encode
        cmd = [
            "ffmpeg", "-y",
            "-init_hw_device", "vaapi=vaapi0:/dev/dri/renderD128",
            "-hwaccel", "vaapi",
            "-hwaccel_output_format", "vaapi",
            "-hwaccel_device", "vaapi0",
            "-i", str(input_path.resolve()),
            "-vf", f"scale_vaapi=w={width}:h=-2:format=nv12",
            "-c:v", "h264_vaapi",
            "-g", "60",
            "-bf", "0",
            "-qp", "26",
            "-c:a", "copy",
            str(tmp_out),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            tmp_out.replace(output_path)
            return True
        print(f"VAAPI encoding failed for {input_path.name}, falling back to CPU x264...")

    # CPU Fallback: x264 ultrafast, fastdecode
    cmd_cpu = [
        "ffmpeg", "-y",
        "-i", str(input_path.resolve()),
        "-vf", f"scale={width}:-2",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "fastdecode",
        "-crf", "23",
        "-g", "60",
        "-bf", "0",
        "-c:a", "copy",
        str(tmp_out),
    ]
    res_cpu = subprocess.run(cmd_cpu, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_cpu.returncode == 0:
        tmp_out.replace(output_path)
        return True

    print(f"Error generating proxy for {input_path.name}: {res_cpu.stderr}")
    if tmp_out.exists():
        tmp_out.unlink()
    return False


def main():
    parser = argparse.ArgumentParser(description="Generate fast editing proxies for video files")
    parser.add_argument("--input", "-i", required=True, nargs="+", help="Input video file(s) or directory")
    parser.add_argument("--output-dir", "-o", required=True, help="Directory to store proxy files")
    parser.add_argument("--width", "-w", type=int, default=960, help="Proxy width (default: 960)")
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing proxies")
    args = parser.parse_args()

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    input_files = []
    for inp in args.input:
        p = Path(inp).resolve()
        if p.is_dir():
            for ext in [".mov", ".mp4", ".mkv", ".MOV", ".MP4", ".MKV"]:
                input_files.extend(list(p.glob(f"*{ext}")))
        elif p.is_file():
            input_files.append(p)

    # Filter out symlinks pointing to other files in list, duplicates
    seen = set()
    unique_files = []
    for f in sorted(input_files):
        real_target = f.resolve()
        if real_target not in seen:
            seen.add(real_target)
            unique_files.append(f)

    if not unique_files:
        sys.exit("No video files found to process.")

    vaapi_ok = is_vaapi_available()
    mode = "Intel VAAPI Hardware Acceleration" if vaapi_ok else "CPU Ultrafast x264"
    print(f"Proxy Generator initialized: {len(unique_files)} files to process.")
    print(f"Mode: {mode} (Resolution: {args.width}xAuto, GOP=60, B-frames=0)\n")

    t_start = time.time()
    for idx, f in enumerate(unique_files, 1):
        stem = f.stem.replace("-005", "")
        proxy_path = out_dir / f"{stem}_proxy.mov"

        if proxy_path.exists() and not args.force and proxy_path.stat().st_size > 1000:
            print(f"[{idx}/{len(unique_files)}] Skipping {f.name} (proxy already exists: {proxy_path.name})")
            continue

        print(f"[{idx}/{len(unique_files)}] Encoding proxy for {f.name}...")
        t0 = time.time()
        success = generate_proxy(f, proxy_path, width=args.width, use_vaapi=vaapi_ok)
        dt = time.time() - t0
        if success:
            mb = proxy_path.stat().st_size / (1024 * 1024)
            print(f"  ✔ Done in {dt:.1f}s -> {proxy_path.name} ({mb:.1f} MB)")
        else:
            print(f"  ✖ Failed for {f.name}")

    total_time = time.time() - t_start
    print(f"\nAll proxies completed in {total_time:.1f}s ({total_time/60:.1f}m). Proxies saved in: {out_dir}")


if __name__ == "__main__":
    main()
