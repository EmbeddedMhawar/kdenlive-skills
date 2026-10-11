#!/usr/bin/env python3
"""
render_motion_graphics.py

High-performance motion graphics and SFX synthesizer for Kdenlive.
Renders:
1. Full-screen animated cards (procedural 3D cyber grid, flowing mesh gradient,
   or AI-thematic concept with 2.5D camera drift).
2. Transparent in-frame overlays (kinetic multi-scale typography with alpha channel).
3. Synchronized audio SFX tracks (cinematic sub-hits, whooshes, pops, typewriter clicks).
"""

import argparse
import json
import math
import os
import random
import re
import struct
import subprocess
import sys
import string
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_SFX_DIR = SKILL_ROOT / "resources" / "sfx"


def parse_args():
    parser = argparse.ArgumentParser(description="Render motion graphics and paired SFX for Kdenlive.")
    parser.add_argument("--plan", "-p", type=str, required=True,
                        help="Path to /tmp/motion_plan.json.")
    parser.add_argument("--output-dir", "-o", type=str, required=True,
                        help="Directory to save rendered video and audio files.")
    parser.add_argument("--width", type=int, default=1920, help="Output width in pixels.")
    parser.add_argument("--height", type=int, default=1080, help="Output height in pixels.")
    parser.add_argument("--fps", type=int, default=60, help="Framerate.")
    parser.add_argument("--sfx-dir", type=str, default=str(DEFAULT_SFX_DIR),
                        help="Path to SFX sound library directory.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Font Resolution
# ---------------------------------------------------------------------------
def resolve_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    # 1. Try fc-match
    try:
        match_path = subprocess.check_output(
            ["fc-match", "-f", "%{file}", font_name],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        if match_path and os.path.isfile(match_path):
            return ImageFont.truetype(match_path, size)
    except Exception:
        pass

    # 2. Check known font paths
    search_dirs = [
        Path.home() / ".local/share/fonts",
        Path.home() / ".fonts",
        Path("/usr/share/fonts"),
    ]
    for d in search_dirs:
        if d.is_dir():
            for f in d.rglob("*.ttf"):
                if font_name.lower() in f.name.lower():
                    return ImageFont.truetype(str(f), size)

    # 3. Fallback
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Audio SFX Synthesizer & Builder
# ---------------------------------------------------------------------------
def load_wav_samples(wav_path: str):
    if not os.path.isfile(wav_path):
        return []
    with wave.open(wav_path, "r") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)
        
        samples = []
        fmt = "<h" if sampwidth == 2 else "<b"
        step = sampwidth * nchannels
        for i in range(0, len(raw), step):
            val = struct.unpack_from(fmt, raw, i)[0]
            samples.append(val / (32767.0 if sampwidth == 2 else 127.0))
        return samples, framerate


def build_sfx_audio(item: dict, out_audio_path: str, sfx_dir: Path, total_duration: float):
    volume = float(item.get("sfx_volume", 0.70))
    sr = 48000
    total_samples = int(total_duration * sr)
    buffer = [0.0] * total_samples

    # Load clean mechanical and thock clicks (no bells, no sub hits)
    mech_dir = sfx_dir / "mechanical"
    thock_dir = sfx_dir / "thock"
    clicks = []
    for d in [mech_dir, thock_dir]:
        if d.is_dir():
            for f in d.glob("click_*.wav"):
                clicks.append(f)
            for f in d.glob("thock_*.wav"):
                clicks.append(f)
    if not clicks:
        # Fallback to pop
        pop_p = sfx_dir / "pop" / "pop_clean.wav"
        if pop_p.is_file():
            clicks.append(pop_p)

    def mix_wav(wav_path: str, t_offset: float, vol_factor: float = 1.0):
        if not os.path.isfile(wav_path):
            return
        s, _ = load_wav_samples(wav_path)
        start_idx = int(t_offset * sr)
        for i, val in enumerate(s):
            if start_idx + i < total_samples:
                buffer[start_idx + i] += val * volume * vol_factor

    sfx_times = item.get("sfx_times", [])
    if sfx_times:
        # Speech-synced tactile clicks on each word/line appearance
        for t_hit in sfx_times:
            if 0.0 <= t_hit < total_duration:
                # Pre-scramble light flicker clicks
                if t_hit >= 0.08 and clicks:
                    c_pre = random.choice(clicks)
                    mix_wav(str(c_pre), t_hit - 0.05, vol_factor=0.35)
                # Primary word resolve click
                if clicks:
                    c_main = random.choice(clicks)
                    mix_wav(str(c_main), t_hit, vol_factor=0.75)
    else:
        # Fallback subtle mechanical clicks
        num_clicks = min(8, int(total_duration * 3))
        for idx in range(num_clicks):
            t_offset = 0.06 + idx * 0.09
            if clicks and t_offset < total_duration:
                c_path = random.choice(clicks)
                mix_wav(str(c_path), t_offset, vol_factor=0.6)

    # Clamp & export WAV
    with wave.open(out_audio_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        raw_out = bytearray()
        for s in buffer:
            clamped = max(-32767, min(32767, int(s * 32767)))
            raw_out.extend(struct.pack("<h", clamped))
        wf.writeframes(raw_out)


# ---------------------------------------------------------------------------
# Background Renderers
# ---------------------------------------------------------------------------
def render_cyber_grid_frame(t: float, width: int, height: int, stars: list) -> Image.Image:
    img = Image.new("RGBA", (width, height), (7, 8, 12, 255))
    draw = ImageDraw.Draw(img)
    cx, cy = width / 2.0, height / 2.0

    # Draw twinkling stars
    for sx, sy, size, b in stars:
        twinkle = 0.75 + 0.25 * math.sin(t * 3.0 + sx)
        val = int(255 * b * twinkle)
        draw.ellipse([sx - size, sy - size, sx + size, sy + size], fill=(val, val, val, val))

    num_v_lines = 14
    num_h_lines = 10
    v_spacing = width / (num_v_lines - 1)
    h_spacing = height / (num_h_lines - 1)

    warp = math.sin(t * 1.6) * 0.04

    # Vertical perspective curved lines
    for i in range(num_v_lines):
        base_x = i * v_spacing
        dx = (base_x - cx) / cx
        pts = []
        for y in range(0, height + 20, 20):
            ny = (y - cy) / cy
            curve = 1.0 + 0.18 * (ny ** 2) + warp * (1.0 - abs(dx))
            curved_x = cx + (base_x - cx) * curve
            pts.append((curved_x, y))
        alpha = int(210 * (1.0 - 0.25 * abs(dx)))
        draw.line(pts, fill=(240, 248, 255, alpha), width=2)

    # Horizontal perspective curved lines with slow forward drift
    grid_offset = (t * 45.0) % h_spacing
    for j in range(-1, num_h_lines + 2):
        base_y = j * h_spacing + grid_offset
        dy = (base_y - cy) / cy
        pts = []
        for x in range(0, width + 20, 20):
            nx = (x - cx) / cx
            curve = 1.0 + 0.14 * (nx ** 2)
            curved_y = cy + (base_y - cy) * curve
            pts.append((x, curved_y))
        alpha = int(210 * (1.0 - 0.25 * abs(dy)))
        draw.line(pts, fill=(240, 248, 255, alpha), width=2)

    return img


def render_mesh_gradient_frame(t: float, width: int, height: int) -> Image.Image:
    # High-aesthetic smooth animated mesh gradient
    # Color stops: deep navy, royal blue, electric cyan
    img = Image.new("RGBA", (width, height), (10, 25, 47, 255))
    draw = ImageDraw.Draw(img)
    
    # Animated glow center
    glow_x = width * (0.65 + 0.1 * math.sin(t * 0.8))
    glow_y = height * (0.35 + 0.08 * math.cos(t * 0.9))
    max_r = int(width * 0.75)
    
    for r in range(max_r, 0, -40):
        factor = 1.0 - (r / max_r)
        alpha = int(90 * factor)
        # Shift from blue to cyan
        cr = int(2 + 25 * factor)
        cg = int(120 + 75 * factor)
        cb = int(210 + 45 * factor)
        draw.ellipse([glow_x - r, glow_y - r, glow_x + r, glow_y + r], fill=(cr, cg, cb, alpha))
        
    return img


# ---------------------------------------------------------------------------
# Visual Layout & Typography Animation (Random Scramble & Kinetic Multi-Scale)
# ---------------------------------------------------------------------------
GLYPHS = string.ascii_uppercase + string.digits + "!@#$%&*"


def scramble_text(target: str, progress: float, frame_idx: int, seed: int = 42) -> str:
    if progress >= 1.0:
        return target
    if progress <= 0.0:
        return ""
    n = len(target)
    rng_order = random.Random(seed)
    threshs = [rng_order.uniform(0.18, 0.88) for _ in range(n)]
    res = []
    for i, ch in enumerate(target):
        if ch in " \n\t":
            res.append(ch)
            continue
        if progress >= threshs[i]:
            res.append(ch)
        else:
            rng_glyph = random.Random(frame_idx * 59 + i * 149 + seed)
            res.append(rng_glyph.choice(GLYPHS))
    return "".join(res)


def draw_stacked_card(img: Image.Image, item: dict, t: float, width: int, height: int, frame_idx: int = 0):
    draw = ImageDraw.Draw(img)
    font_name = item.get("font", "Clarify-Blk")
    tag = item.get("tag", "").upper()
    text = item.get("text", "")
    dur = float(item.get("duration", 4.5))

    # Exit fade during last 0.35s
    alpha_mult = 1.0
    if t > dur - 0.35:
        alpha_mult = max(0.0, (dur - t) / 0.35)

    anim_style = item.get("animation_style", "random_scramble")
    is_scramble = anim_style in ["random_scramble", "scramble_reveal"]

    is_recap = ("\n" in text) or (len(text) > 50)
    tag_size = 36
    text_size = 46 if is_recap else 64

    tag_font = resolve_font(font_name, tag_size)
    text_font = resolve_font(font_name, text_size)

    cx, cy = width / 2.0, height / 2.0

    tag_bbox = draw.textbbox((0, 0), tag, font=tag_font) if tag else (0, 0, 0, 0)
    tag_w = tag_bbox[2] - tag_bbox[0]
    tag_h = tag_bbox[3] - tag_bbox[1]

    if "\n" in text:
        raw_lines = text.split("\n")
    else:
        max_text_w = int(width * 0.78)
        words = text.split()
        raw_lines = []
        curr = []
        for w in words:
            test_line = " ".join(curr + [w])
            tb = draw.textbbox((0, 0), test_line, font=text_font)
            if tb[2] - tb[0] > max_text_w and curr:
                raw_lines.append(" ".join(curr))
                curr = [w]
            else:
                curr.append(w)
        if curr:
            raw_lines.append(" ".join(curr))

    line_h = text_size * 1.35
    total_text_h = len(raw_lines) * line_h
    total_block_h = tag_h + 30 + total_text_h if tag else total_text_h

    start_y = cy - total_block_h / 2.0

    # Eyebrow Tag
    if tag:
        if is_scramble:
            p_tag = max(0.0, min(1.0, (t - 0.05) / 0.28))
            rendered_tag = scramble_text(tag, p_tag, frame_idx, seed=101)
        else:
            rendered_tag = tag if t >= 0.05 else ""

        if rendered_tag:
            tag_x = (cx - tag_w / 2.0) if not is_recap else int(width * 0.15)
            draw.text((tag_x + 3, start_y + 3), rendered_tag, font=tag_font, fill=(0, 0, 0, int(180 * alpha_mult)))
            draw.text((tag_x, start_y), rendered_tag, font=tag_font, fill=(255, 255, 255, int(255 * alpha_mult)))
        start_y += tag_h + 30

    # Text Lines
    for line_idx, line in enumerate(raw_lines):
        if is_scramble:
            t_line_start = 0.15 + line_idx * (0.16 if is_recap else 0.10)
            p_line = max(0.0, min(1.0, (t - t_line_start) / 0.32))
            rendered_line = scramble_text(line, p_line, frame_idx, seed=202 + line_idx * 73)
        else:
            rendered_line = line if t >= 0.2 else ""

        if rendered_line:
            lb = draw.textbbox((0, 0), rendered_line, font=text_font)
            lw = lb[2] - lb[0]
            lx = int(width * 0.15) if is_recap else (cx - lw / 2.0)
            for off in [(2, 2), (3, 3), (4, 4)]:
                draw.text((lx + off[0], start_y + off[1]), rendered_line, font=text_font, fill=(0, 0, 0, int(160 * alpha_mult)))
            draw.text((lx, start_y), rendered_line, font=text_font, fill=(255, 255, 255, int(255 * alpha_mult)))
        start_y += line_h


def draw_kinetic_multiscale(img: Image.Image, item: dict, t: float, width: int, height: int, frame_idx: int = 0):
    draw = ImageDraw.Draw(img)
    font_name = item.get("font", "Clarify-Blk")
    dur = float(item.get("duration", 4.5))

    # Exit fade during last 0.30s
    alpha_mult = 1.0
    if t > dur - 0.30:
        alpha_mult = max(0.0, (dur - t) / 0.30)

    start_x = int(width * item.get("start_x", 0.06))
    start_y = int(height * item.get("start_y", 0.22))

    numeral_size = int(item.get("numeral_size", 130))
    line_size = int(item.get("line_size", 70))
    eyebrow_size = int(item.get("eyebrow_size", 34))

    font_huge = resolve_font(font_name, numeral_size)
    font_large = resolve_font(font_name, line_size)
    font_sub = resolve_font(font_name, eyebrow_size)

    # 1. Numeral + Eyebrow Tag
    numeral = item.get("numeral", "")
    eyebrow = item.get("eyebrow", "")
    t_num = float(item.get("numeral_t", 0.0))

    if numeral and t >= t_num:
        p_num = max(0.0, min(1.0, (t - t_num) / 0.18))
        txt_num = scramble_text(numeral, p_num, frame_idx, seed=11)
        if txt_num:
            draw.text((start_x + 3, start_y + 3), txt_num, font=font_huge, fill=(0, 0, 0, int(180 * alpha_mult)))
            draw.text((start_x, start_y), txt_num, font=font_huge, fill=(255, 255, 255, int(255 * alpha_mult)))

    if eyebrow and t >= t_num:
        p_eye = max(0.0, min(1.0, (t - t_num) / 0.18))
        txt_eye = scramble_text(eyebrow, p_eye, frame_idx, seed=22)
        if txt_eye:
            offset_x = start_x + int(numeral_size * (0.85 if len(numeral) <= 1 else 1.35))
            offset_y = start_y + int(numeral_size * 0.22)
            draw.text((offset_x + 3, offset_y + 3), txt_eye, font=font_sub, fill=(0, 0, 0, int(180 * alpha_mult)))
            draw.text((offset_x, offset_y), txt_eye, font=font_sub, fill=(240, 240, 245, int(255 * alpha_mult)))

    # Vertical line layout
    num_bbox = draw.textbbox((0, 0), numeral if numeral else "00", font=font_huge)
    num_h = num_bbox[3] - num_bbox[1]
    y1 = start_y + num_h + int(line_size * 0.35)
    line_h = int(line_size * 0.80)
    box_w = max(850, int(line_size * 10))
    box_h = int(line_size * 1.6)

    # 2. Line 1
    line1 = item.get("line1", "")
    t_line1 = float(item.get("line1_t", 0.15))

    if line1 and t >= t_line1:
        p1 = max(0.0, min(1.0, (t - t_line1) / 0.22))
        txt_l1 = scramble_text(line1, p1, frame_idx, seed=33)
        if txt_l1:
            if item.get("line1_sheared", False):
                tmp_im = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
                d_tmp = ImageDraw.Draw(tmp_im)
                d_tmp.text((23, 23), txt_l1, font=font_large, fill=(0, 0, 0, int(180 * alpha_mult)))
                d_tmp.text((20, 20), txt_l1, font=font_large, fill=(255, 255, 255, int(255 * alpha_mult)))
                sheared = tmp_im.transform(tmp_im.size, Image.AFFINE, (1, -0.20, 0.20 * (box_h / 2), 0, 1, 0), Image.BICUBIC)
                img.paste(sheared, (start_x - 20, y1 - 20), sheared)
            else:
                draw.text((start_x + 3, y1 + 3), txt_l1, font=font_large, fill=(0, 0, 0, int(180 * alpha_mult)))
                draw.text((start_x, y1), txt_l1, font=font_large, fill=(255, 255, 255, int(255 * alpha_mult)))

    # 3. Line 2
    line2 = item.get("line2", "")
    t_line2 = float(item.get("line2_t", 0.50))
    y2 = y1 + line_h

    if line2 and t >= t_line2:
        p2 = max(0.0, min(1.0, (t - t_line2) / 0.22))
        txt_l2 = scramble_text(line2, p2, frame_idx, seed=44)
        if txt_l2:
            if item.get("line2_sheared", True):
                tmp_im = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
                d_tmp = ImageDraw.Draw(tmp_im)
                d_tmp.text((23, 23), txt_l2, font=font_large, fill=(0, 0, 0, int(180 * alpha_mult)))
                d_tmp.text((20, 20), txt_l2, font=font_large, fill=(255, 255, 255, int(255 * alpha_mult)))
                sheared = tmp_im.transform(tmp_im.size, Image.AFFINE, (1, -0.20, 0.20 * (box_h / 2), 0, 1, 0), Image.BICUBIC)
                img.paste(sheared, (start_x - 20, y2 - 20), sheared)
            else:
                draw.text((start_x + 3, y2 + 3), txt_l2, font=font_large, fill=(0, 0, 0, int(180 * alpha_mult)))
                draw.text((start_x, y2), txt_l2, font=font_large, fill=(255, 255, 255, int(255 * alpha_mult)))

    # 4. Line 3 (Optional)
    line3 = item.get("line3", "")
    t_line3 = float(item.get("line3_t", 3.80))
    y3 = y2 + line_h

    if line3 and t >= t_line3:
        p3 = max(0.0, min(1.0, (t - t_line3) / 0.22))
        txt_l3 = scramble_text(line3, p3, frame_idx, seed=55)
        if txt_l3:
            draw.text((start_x + 3, y3 + 3), txt_l3, font=font_large, fill=(0, 0, 0, int(180 * alpha_mult)))
            draw.text((start_x, y3), txt_l3, font=font_large, fill=(255, 255, 255, int(255 * alpha_mult)))


def draw_rules_list(img: Image.Image, item: dict, t: float, width: int, height: int, frame_idx: int = 0):
    draw = ImageDraw.Draw(img)
    font_name = item.get("font", "Clarify-Blk")
    dur = float(item.get("duration", 8.0))

    # Exit fade during last 0.35s
    alpha_mult = 1.0
    if t > dur - 0.35:
        alpha_mult = max(0.0, (dur - t) / 0.35)

    start_x = int(width * item.get("start_x", 0.045))
    start_y = int(height * item.get("start_y", 0.11))

    hdr_size = int(item.get("header_size", 48))
    num_size = int(item.get("num_size", 39))
    rule_size = int(item.get("rule_size", 39))

    font_hdr = resolve_font(font_name, hdr_size)
    font_num = resolve_font(font_name, num_size)
    font_rule = resolve_font(font_name, rule_size)

    # Header
    header = item.get("header", "THE 5 RULES TO LOCK IN")
    if t >= 0.0:
        p_hdr = max(0.0, min(1.0, t / 0.25))
        txt_hdr = scramble_text(header, p_hdr, frame_idx, seed=10)
        if txt_hdr:
            draw.text((start_x + 2, start_y + 2), txt_hdr, font=font_hdr, fill=(0, 0, 0, int(180 * alpha_mult)))
            draw.text((start_x, start_y), txt_hdr, font=font_hdr, fill=(255, 255, 255, int(255 * alpha_mult)))

    # 5 Rules
    rules = item.get("rules", [
        ("01", "FOCUS ON LESS GOALS"),
        ("02", "SCHEDULE YOUR DAYS"),
        ("03", "START ON LEVEL 1 BOSSES"),
        ("04", "STOP STREAKING YOUR DAYS"),
        ("05", "STOP COMPARING TO OTHERS")
    ])
    rule_times = item.get("rule_times", [0.4, 1.0, 1.6, 2.2, 2.8])

    curr_y = start_y + 72
    for idx, (num, rule_txt) in enumerate(rules):
        t_rule = rule_times[idx] if idx < len(rule_times) else (0.4 + idx * 0.6)
        if t >= t_rule:
            p = max(0.0, min(1.0, (t - t_rule) / 0.22))
            s_num = scramble_text(num, p, frame_idx, seed=20 + idx * 11)
            s_txt = scramble_text(rule_txt, p, frame_idx, seed=30 + idx * 13)

            # Number
            draw.text((start_x + 2, curr_y + 2), s_num, font=font_num, fill=(0, 0, 0, int(180 * alpha_mult)))
            draw.text((start_x, curr_y), s_num, font=font_num, fill=(240, 240, 245, int(255 * alpha_mult)))

            # Rule text
            x_txt = start_x + 68
            draw.text((x_txt + 2, curr_y + 2), s_txt, font=font_rule, fill=(0, 0, 0, int(180 * alpha_mult)))
            draw.text((x_txt, curr_y), s_txt, font=font_rule, fill=(255, 255, 255, int(255 * alpha_mult)))

        curr_y += 62


# ---------------------------------------------------------------------------
# Main Rendering Loop
# ---------------------------------------------------------------------------
def render_item(item: dict, out_dir: Path, width: int, height: int, fps: int, sfx_dir: Path) -> dict:
    item_id = item.get("id", f"title_{random.randint(100, 999)}")
    visual_mode = item.get("visual_mode", "fullscreen_card")
    bg_type = item.get("background", "cyber_grid")
    duration = float(item.get("duration", 3.0))
    total_frames = int(duration * fps)
    
    out_video = out_dir / f"{item_id}.webm" if visual_mode == "inframe_overlay" else out_dir / f"{item_id}.mp4"
    out_audio = out_dir / f"{item_id}_sfx.wav"
    
    print(f"\n[Rendering] {item_id}: mode={visual_mode}, bg={bg_type}, dur={duration}s -> {out_video.name}")
    
    # 1. Synthesize Audio SFX
    build_sfx_audio(item, str(out_audio), sfx_dir, duration)
    
    # 2. Setup FFmpeg video pipe
    if visual_mode == "inframe_overlay":
        # Transparent VP9 WebM
        cmd = [
            "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{width}x{height}", "-pix_fmt", "rgba", "-r", str(fps),
            "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-b:v", "0", "-crf", "22", "-auto-alt-ref", "0",
            "-deadline", "realtime", "-speed", "8", "-cpu-used", "8",
            str(out_video)
        ]
    else:
        # Fullscreen H.264 MP4
        cmd = [
            "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{width}x{height}", "-pix_fmt", "rgba", "-r", str(fps),
            "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "ultrafast", "-crf", "18",
            str(out_video)
        ]
        
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Pre-seed stars for cyber grid
    random.seed(1337)
    stars = [(random.randint(0, width), random.randint(0, height), random.uniform(1.0, 2.5), random.uniform(0.3, 1.0)) for _ in range(130)]
    
    for f in range(total_frames):
        t = f / fps
        
        # Step A: Background layer
        if visual_mode == "inframe_overlay":
            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        elif bg_type == "mesh_gradient":
            img = render_mesh_gradient_frame(t, width, height)
        else: # cyber_grid or fallback
            img = render_cyber_grid_frame(t, width, height, stars)
            
        # Step B: Layout & Typography
        layout = item.get("layout", "stacked_card")
        if layout == "rules_list":
            draw_rules_list(img, item, t, width, height, f)
        elif layout == "kinetic_multiscale":
            draw_kinetic_multiscale(img, item, t, width, height, f)
        else:
            draw_stacked_card(img, item, t, width, height, f)
            
        proc.stdin.write(img.tobytes())
        
    proc.stdin.close()
    proc.wait()
    
    return {
        "title_id": item_id,
        "timeline_start": item.get("timeline_start", 0.0),
        "duration": duration,
        "visual_mode": visual_mode,
        "video_path": str(out_video),
        "audio_path": str(out_audio),
        "text": item.get("text", ""),
        "tag": item.get("tag", "")
    }


def main():
    args = parse_args()
    with open(args.plan, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sfx_dir = Path(args.sfx_dir)
    
    manifest = []
    for item in plan:
        res = render_item(item, out_dir, args.width, args.height, args.fps, sfx_dir)
        manifest.append(res)
        
    manifest_path = out_dir / "motion_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"\n[SUCCESS] Rendered {len(manifest)} motion assets. Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
