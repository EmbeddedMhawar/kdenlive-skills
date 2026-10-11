#!/usr/bin/env -S uv run --python 3.12 --with "faster-whisper" --with "av<14" python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["faster-whisper", "av<14"]
# ///
"""
Verify a cuts.json by transcribing the audio of every cut exactly as it will play.

Whisper on the full file often collapses repeated phrases and misplaces timestamps,
so the agent MUST read this output and fix any cut whose text contains a repeated
phrase, a clipped first word, or a leading/trailing fragment of another take.

Output per cut:  [idx] start-end  "text"  (+ WARN flags)
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def repeated_phrase(words):
    toks = [norm(w) for w in words if norm(w)]
    n = len(toks)
    # 1. Back-to-back repeats (stutters: e.g. 'the the', 'have the have the')
    for k in range(min(6, n // 2), 0, -1):
        for i in range(n - 2 * k + 1):
            if toks[i:i + k] == toks[i + k:i + 2 * k]:
                return f"STUTTER:'{' '.join(toks[i:i + k])}'"
    # 2. Non-adjacent repeated clauses (self-correction loops: e.g. 'and I knew that I wanted ... and I knew that I wanted')
    for k in range(min(8, n // 2), 2, -1):
        for i in range(n - k):
            gram = toks[i:i + k]
            rest = toks[i + k:]
            for j in range(len(rest) - k + 1):
                if rest[j:j + k] == gram:
                    return f"CLAUSE:'{' '.join(gram)}'"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--cuts", required=True)
    ap.add_argument("--model", default="base")
    ap.add_argument("--words", action="store_true", help="Print absolute word timestamps (to pick exact restart points)")
    ap.add_argument("--padding", type=float, default=0.0, help="Same padding the assembler will apply")
    a = ap.parse_args()

    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    cuts = json.loads(Path(a.cuts).read_text())
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        for i, c in enumerate(cuts):
            s = max(0.0, c["start"] - a.padding)
            e = c["end"] + a.padding
            wav = Path(td) / f"{i}.wav"
            subprocess.run(["ffmpeg", "-y", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", a.media,
                            "-vn", "-ar", "16000", "-ac", "1", str(wav)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            segs, _ = model.transcribe(str(wav), word_timestamps=True, vad_filter=False,
                                       condition_on_previous_text=False, temperature=0.0)
            words = [w for sg in segs for w in sg.words]
            text = "".join(w.word for w in words).strip()
            flags = []
            rep = repeated_phrase([w.word for w in words])
            if rep:
                flags.append(f"REPEAT:{rep}")
            if words and words[0].start > 0.6:
                flags.append(f"LEADING-GAP {words[0].start:.2f}s")
            
            # Check 1: Word duration anomalies (Whisper smooths over stumbles/pauses by stretching a word)
            stretched = [f"{w.word.strip()}({w.end - w.start:.2f}s)" for w in words if (w.end - w.start) > 0.85]
            if stretched:
                flags.append(f"STRETCHED-WORD:{','.join(stretched)}")

            # Check 2: Word-to-word timestamp gaps
            gaps = [words[j + 1].start - words[j].end for j in range(len(words) - 1)]
            if gaps and max(gaps) > 0.8:
                flags.append(f"GAP-BETWEEN-WORDS {max(gaps):.2f}s")

            # Check 3: True acoustic dead air inside the audio slice (catches silence swallowed by Whisper)
            sil_cmd = ["ffmpeg", "-i", str(wav), "-af", "silencedetect=noise=-30dB:d=0.5", "-f", "null", "-"]
            sil_res = subprocess.run(sil_cmd, stderr=subprocess.PIPE, text=True)
            sil_durs = [float(m) for m in re.findall(r"silence_duration:\s*([0-9.]+)", sil_res.stderr)]
            if sil_durs and max(sil_durs) > 0.6:
                flags.append(f"ACOUSTIC-DEAD-AIR {max(sil_durs):.2f}s")

            # Check 4: Syllable Clipping at onset (checks if cut starts mid-speech rather than clean silence)
            try:
                import struct, math
                raw_head = subprocess.check_output(["ffmpeg", "-y", "-i", str(wav), "-t", "0.03", "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], stderr=subprocess.DEVNULL)
                if len(raw_head) >= 320:
                    samples = struct.unpack(f"<{len(raw_head)//2}h", raw_head)
                    onset_rms = math.sqrt(sum(x*x for x in samples) / len(samples))
                    if onset_rms > 1200:
                        flags.append(f"CLIPPED-ONSET(rms={onset_rms:.0f})")
            except Exception:
                pass

            if flags:
                bad += 1
            print(f"[{i}] {c['start']:.2f}-{c['end']:.2f}  \"{text}\"  {' '.join('WARN:' + f for f in flags)}")
            if a.words:
                print("     " + " ".join(f"{w.word.strip()}@{s + w.start:.2f}" for w in words))
    print(f"\n{bad} cut(s) flagged out of {len(cuts)}")


if __name__ == "__main__":
    main()
