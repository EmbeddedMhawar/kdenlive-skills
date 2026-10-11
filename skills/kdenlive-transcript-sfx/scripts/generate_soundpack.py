#!/usr/bin/env python3
"""
generate_soundpack.py

Synthesizes high-fidelity 48kHz 16-bit mono WAV sound effects
for kdenlive-transcript-sfx:
- Minecraft pack: orb pickup, level up, pop, click, anvil, villager huh, chest open/close
- Accents pack: hotel bell ding, subtle chime, clean UI pop, lightbulb spark
- Foley pack: cash register, camera shutter, notification ping, keyboard tap, clock tick
- Impacts pack: heavy sub-drop, tight sub-boom, cinematic hit
- Comedic pack: vinyl record scratch, spin down, cartoon boing, sad trombone wah
- Transitions pack: fast whoosh, deep cinematic whoosh, tension riser
"""

import math
import os
import random
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 48000


def write_wav(file_path: Path, samples: list[float]):
    """Write normalized float samples (-1.0 to 1.0) to 16-bit mono WAV."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Peak normalize to -1.0 dB (~0.89) to prevent digital clipping
    max_val = max((abs(s) for s in samples), default=1.0)
    if max_val > 0.001:
        gain = 0.89 / max_val
    else:
        gain = 1.0

    int_samples = []
    for s in samples:
        v = int(max(-32767, min(32767, s * gain * 32767)))
        int_samples.append(v)

    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        raw_data = struct.pack(f"<{len(int_samples)}h", *int_samples)
        wf.writeframes(raw_data)
    print(f"Generated: {file_path.name} ({len(samples)/SAMPLE_RATE:.2f}s)")


# ---------------------------------------------------------
# MINECRAFT SOUND PACK
# ---------------------------------------------------------

def gen_minecraft_orb(path: Path):
    """Iconic rising dual-tone XP orb pickup ping."""
    duration = 0.28
    num_samples = int(duration * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        # Rising frequency
        freq = 1150.0 + 350.0 * (t / duration) ** 0.8
        # Exponential decay envelope
        env = math.exp(-12.0 * t)
        # Dual harmonic with slight FM shimmer
        s = math.sin(2 * math.pi * freq * t) * 0.7
        s += math.sin(2 * math.pi * (freq * 2.01) * t) * 0.3
        samples.append(s * env)
    write_wav(path, samples)


def gen_minecraft_level_up(path: Path):
    """5-note triumphant arpeggio chime (C5, E5, G5, B5, C6)."""
    notes = [523.25, 659.25, 783.99, 987.77, 1046.50]
    note_duration = 0.16
    tail = 0.6
    total_duration = len(notes) * note_duration + tail
    num_samples = int(total_duration * SAMPLE_RATE)
    samples = [0.0] * num_samples

    for idx, f in enumerate(notes):
        start_t = idx * note_duration
        start_sample = int(start_t * SAMPLE_RATE)
        for i in range(int((total_duration - start_t) * SAMPLE_RATE)):
            cur_idx = start_sample + i
            if cur_idx >= num_samples:
                break
            t = i / SAMPLE_RATE
            env = math.exp(-5.5 * t)
            # Bell-like harmonics
            s = math.sin(2 * math.pi * f * t) * 0.6
            s += math.sin(2 * math.pi * f * 2.0 * t) * 0.25
            s += math.sin(2 * math.pi * f * 3.01 * t) * 0.15
            samples[cur_idx] += s * env * 0.8

    write_wav(path, samples)


def gen_minecraft_pop(path: Path):
    """Classic item drop pop / bubble click."""
    duration = 0.08
    num_samples = int(duration * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        # Pitch chirp: high to low quickly
        freq = 650.0 - 380.0 * (t / duration)
        env = math.sin(math.pi * (t / duration)) ** 1.5
        s = math.sin(2 * math.pi * freq * t)
        samples.append(s * env)
    write_wav(path, samples)


def gen_minecraft_click(path: Path):
    """Wooden button UI click."""
    duration = 0.05
    num_samples = int(duration * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-80.0 * t)
        freq = 1200.0 - 500.0 * (t / duration)
        s = math.sin(2 * math.pi * freq * t) * 0.7 + (random.random() * 2 - 1) * 0.3
        samples.append(s * env)
    write_wav(path, samples)


def gen_minecraft_anvil(path: Path):
    """Heavy metallic clang with resonant ring."""
    duration = 0.75
    num_samples = int(duration * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-6.0 * t)
        # Metallic harmonics (inharmonic frequencies)
        s = math.sin(2 * math.pi * 880 * t) * 0.4
        s += math.sin(2 * math.pi * 1420 * t) * 0.3
        s += math.sin(2 * math.pi * 2150 * t) * 0.2
        # Low thud impact
        low_env = math.exp(-35.0 * t)
        s += math.sin(2 * math.pi * 110 * t) * 0.8 * low_env
        samples.append(s * env)
    write_wav(path, samples)


def gen_minecraft_villager_huh(path: Path):
    """Puzzled nasal villager 'huh' acoustic vocalization."""
    duration = 0.35
    num_samples = int(duration * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        # Inflected pitch contour
        if t < 0.15:
            pitch = 280.0 + 70.0 * (t / 0.15)
        else:
            pitch = 350.0 - 60.0 * ((t - 0.15) / 0.20)
        # Vocal formant envelope
        env = math.sin(math.pi * (t / duration)) ** 1.2
        s = math.sin(2 * math.pi * pitch * t) * 0.5
        s += math.sin(2 * math.pi * (pitch * 2) * t) * 0.3
        s += math.sin(2 * math.pi * (pitch * 3) * t) * 0.15
        s += math.sin(2 * math.pi * (pitch * 5) * t) * 0.05
        samples.append(s * env)
    write_wav(path, samples)


def gen_minecraft_chest(path_open: Path, path_close: Path):
    """Wooden chest creak open and latch close."""
    # Open: creaky hinge
    num_samples = int(0.45 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * (t / 0.45)) ** 0.8
        freq = 240.0 + 160.0 * (t / 0.45) + 30.0 * math.sin(40.0 * 2 * math.pi * t)
        s = math.sin(2 * math.pi * freq * t) * 0.7
        samples.append(s * env)
    write_wav(path_open, samples)

    # Close: wooden thud
    num_samples = int(0.22 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-25.0 * t)
        s = math.sin(2 * math.pi * 140 * t) * 0.8 + math.sin(2 * math.pi * 320 * t) * 0.3
        samples.append(s * env)
    write_wav(path_close, samples)


# ---------------------------------------------------------
# ACCENTS PACK
# ---------------------------------------------------------

def gen_accents(accents_dir: Path):
    # 1. ding_bell.wav (desk bell / elevator ding)
    num_samples = int(1.1 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-4.2 * t)
        s = math.sin(2 * math.pi * 2380 * t) * 0.6
        s += math.sin(2 * math.pi * 4760 * t) * 0.25
        s += math.sin(2 * math.pi * 7140 * t) * 0.15
        samples.append(s * env)
    write_wav(accents_dir / "ding_bell.wav", samples)

    # 2. chime_subtle.wav (gentle sparkling realization chime)
    num_samples = int(0.9 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-4.8 * t)
        tremolo = 1.0 + 0.15 * math.sin(2 * math.pi * 12.0 * t)
        s = math.sin(2 * math.pi * 1760 * t) * 0.5 * tremolo
        s += math.sin(2 * math.pi * 2217 * t) * 0.4 * tremolo
        s += math.sin(2 * math.pi * 3520 * t) * 0.1
        samples.append(s * env)
    write_wav(accents_dir / "chime_subtle.wav", samples)

    # 3. ui_pop_clean.wav (modern UI glass bubble pop)
    num_samples = int(0.09 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * (t / 0.09)) ** 1.8
        freq = 380.0 + 820.0 * math.sin(math.pi * (t / 0.09))
        s = math.sin(2 * math.pi * freq * t)
        samples.append(s * env)
    write_wav(accents_dir / "ui_pop_clean.wav", samples)

    # 4. lightbulb_spark.wav (electric idea spark + ping)
    num_samples = int(0.6 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-6.0 * t)
        # high shimmer + initial click
        click = math.exp(-120.0 * t) * (random.random() * 2 - 1)
        s = click * 0.4 + math.sin(2 * math.pi * 2850 * t) * 0.5 * env
        s += math.sin(2 * math.pi * 3800 * t) * 0.3 * env
        samples.append(s)
    write_wav(accents_dir / "lightbulb_spark.wav", samples)


# ---------------------------------------------------------
# FOLEY PACK
# ---------------------------------------------------------

def gen_foley(foley_dir: Path):
    # 1. cash_register.wav (cha-ching mechanical roll + chime)
    num_samples = int(0.75 * SAMPLE_RATE)
    samples = [0.0] * num_samples
    # Rattle transient (0.0 to 0.12s)
    for i in range(int(0.12 * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        samples[i] += (random.random() * 2 - 1) * math.exp(-20.0 * t) * 0.4
    # Bright bell hit at 0.10s
    bell_start = int(0.10 * SAMPLE_RATE)
    for i in range(num_samples - bell_start):
        t = i / SAMPLE_RATE
        env = math.exp(-5.0 * t)
        s = math.sin(2 * math.pi * 2637 * t) * 0.6 + math.sin(2 * math.pi * 5274 * t) * 0.3
        samples[bell_start + i] += s * env
    write_wav(foley_dir / "cash_register.wav", samples)

    # 2. camera_shutter.wav (snappy DSLR shutter)
    num_samples = int(0.22 * SAMPLE_RATE)
    samples = [0.0] * num_samples
    # First curtain hit
    for i in range(int(0.08 * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        samples[i] += (random.random() * 2 - 1) * math.exp(-70.0 * t) * 0.8
    # Second curtain hit at 0.07s
    c2 = int(0.07 * SAMPLE_RATE)
    for i in range(num_samples - c2):
        t = i / SAMPLE_RATE
        samples[c2 + i] += (random.random() * 2 - 1) * math.exp(-80.0 * t) * 0.9
    write_wav(foley_dir / "camera_shutter.wav", samples)

    # 3. notification_ping.wav (clean marimba notification)
    num_samples = int(0.55 * SAMPLE_RATE)
    samples = [0.0] * num_samples
    # Note 1: A5 (880Hz) at 0.0s
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        samples[i] += math.sin(2 * math.pi * 880 * t) * math.exp(-8.0 * t) * 0.5
    # Note 2: E6 (1318Hz) at 0.08s
    n2 = int(0.08 * SAMPLE_RATE)
    for i in range(num_samples - n2):
        t = i / SAMPLE_RATE
        samples[n2 + i] += math.sin(2 * math.pi * 1318.5 * t) * math.exp(-6.5 * t) * 0.6
    write_wav(foley_dir / "notification_ping.wav", samples)

    # 4. keyboard_tap.wav
    num_samples = int(0.08 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-90.0 * t)
        s = math.sin(2 * math.pi * 1400 * t) * 0.6 + (random.random() * 2 - 1) * 0.4
        samples.append(s * env)
    write_wav(foley_dir / "keyboard_tap.wav", samples)

    # 5. clock_tick.wav
    num_samples = int(0.06 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-120.0 * t)
        s = math.sin(2 * math.pi * 2100 * t) * 0.5 + (random.random() * 2 - 1) * 0.5
        samples.append(s * env)
    write_wav(foley_dir / "clock_tick.wav", samples)


# ---------------------------------------------------------
# IMPACTS PACK
# ---------------------------------------------------------

def gen_impacts(impacts_dir: Path):
    # 1. sub_drop_heavy.wav (deep 808 sub-bass drop 90Hz -> 35Hz)
    num_samples = int(1.15 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-2.8 * t)
        freq = 92.0 - 55.0 * (t / 1.15) ** 0.5
        phase = 2 * math.pi * freq * t
        # warm soft saturation
        s = math.tanh(math.sin(phase) * 1.4)
        samples.append(s * env)
    write_wav(impacts_dir / "sub_drop_heavy.wav", samples)

    # 2. sub_boom_tight.wav (punchy sub-hit)
    num_samples = int(0.65 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-5.5 * t)
        freq = 85.0 - 45.0 * (t / 0.65)
        s = math.sin(2 * math.pi * freq * t)
        samples.append(s * env)
    write_wav(impacts_dir / "sub_boom_tight.wav", samples)

    # 3. cinematic_hit.wav (impact with low rumble)
    num_samples = int(1.2 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-3.2 * t)
        low = math.sin(2 * math.pi * (65 - 25 * t) * t) * 0.7
        transient = math.exp(-60.0 * t) * (random.random() * 2 - 1) * 0.5
        samples.append((low + transient) * env)
    write_wav(impacts_dir / "cinematic_hit.wav", samples)


# ---------------------------------------------------------
# COMEDIC PACK
# ---------------------------------------------------------

def gen_comedic(comedic_dir: Path):
    # 1. record_scratch.wav (needle scrape / vinyl friction stop)
    num_samples = int(0.48 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * (t / 0.48)) ** 0.8
        # Descending friction tone with noise modulation
        freq = 1900.0 - 1650.0 * (t / 0.48)
        s = math.sin(2 * math.pi * freq * t) * 0.5
        noise = (random.random() * 2 - 1) * 0.5
        samples.append((s + noise) * env)
    write_wav(comedic_dir / "record_scratch.wav", samples)

    # 2. vinyl_spin_down.wav (motor deceleration stop)
    num_samples = int(0.85 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-2.5 * t)
        freq = 600.0 * (1.0 - t / 0.85) ** 1.8
        s = math.sin(2 * math.pi * freq * t) * 0.7
        samples.append(s * env)
    write_wav(comedic_dir / "vinyl_spin_down.wav", samples)

    # 3. cartoon_boing.wav (spring vibrato bounce)
    num_samples = int(0.65 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-3.5 * t)
        vibrato = math.sin(2 * math.pi * 14.0 * t) * 60.0
        base_freq = 280.0 + 350.0 * (t / 0.65)
        s = math.sin(2 * math.pi * (base_freq + vibrato) * t)
        samples.append(s * env)
    write_wav(comedic_dir / "cartoon_boing.wav", samples)

    # 4. sad_trombone_wah.wav (descending brass wah-wah)
    num_samples = int(1.1 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * (t / 1.1)) ** 0.8
        freq = 380.0 - 130.0 * (t / 1.1)
        wah = (1.0 + 0.3 * math.sin(2 * math.pi * 9.0 * t))
        s = math.sin(2 * math.pi * freq * t) * 0.6 * wah
        s += math.sin(2 * math.pi * freq * 2.0 * t) * 0.3 * wah
        samples.append(s * env)
    write_wav(comedic_dir / "sad_trombone_wah.wav", samples)


# ---------------------------------------------------------
# TRANSITIONS PACK
# ---------------------------------------------------------

def gen_transitions(trans_dir: Path):
    # 1. whoosh_fast.wav (quick whip-pan whoosh)
    num_samples = int(0.38 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * (t / 0.38)) ** 2.2
        # Filtered white noise with center frequency sweep
        center_f = 300.0 + 1800.0 * math.sin(math.pi * (t / 0.38))
        s = math.sin(2 * math.pi * center_f * t) * 0.4 + (random.random() * 2 - 1) * 0.6
        samples.append(s * env)
    write_wav(trans_dir / "whoosh_fast.wav", samples)

    # 2. whoosh_deep.wav (cinematic deep airy whoosh)
    num_samples = int(0.72 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * (t / 0.72)) ** 2.0
        center_f = 120.0 + 450.0 * math.sin(math.pi * (t / 0.72))
        s = math.sin(2 * math.pi * center_f * t) * 0.6 + (random.random() * 2 - 1) * 0.4
        samples.append(s * env)
    write_wav(trans_dir / "whoosh_deep.wav", samples)

    # 3. riser_tension.wav (1.2s pitch and volume build)
    num_samples = int(1.2 * SAMPLE_RATE)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        env = (t / 1.2) ** 2.0
        freq = 150.0 + 850.0 * (t / 1.2) ** 1.5
        s = math.sin(2 * math.pi * freq * t) * 0.6 + (random.random() * 2 - 1) * 0.4
        samples.append(s * env)
    write_wav(trans_dir / "riser_tension.wav", samples)


def main():
    base_dir = Path(__file__).resolve().parent.parent / "resources" / "sfx"
    print(f"Synthesizing high-fidelity 48kHz sound effects into: {base_dir}")

    # Minecraft
    mc_dir = base_dir / "minecraft"
    gen_minecraft_orb(mc_dir / "orb_pickup.wav")
    gen_minecraft_level_up(mc_dir / "level_up.wav")
    gen_minecraft_pop(mc_dir / "pop.wav")
    gen_minecraft_click(mc_dir / "click.wav")
    gen_minecraft_anvil(mc_dir / "anvil_impact.wav")
    gen_minecraft_villager_huh(mc_dir / "villager_huh.wav")
    gen_minecraft_chest(mc_dir / "chest_open.wav", mc_dir / "chest_close.wav")

    # Accents
    gen_accents(base_dir / "accents")

    # Foley
    gen_foley(base_dir / "foley")

    # Impacts
    gen_impacts(base_dir / "impacts")

    # Comedic
    gen_comedic(base_dir / "comedic")

    # Transitions
    gen_transitions(base_dir / "transitions")

    print("Soundpack generation complete! All 26 assets synthesized at 48kHz 16-bit PCM.")


if __name__ == "__main__":
    main()
