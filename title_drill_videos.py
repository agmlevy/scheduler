"""
Transcribe drill videos and suggest titles from audio + on-screen text (OCR).

Usage:
  .venv\\Scripts\\python title_drill_videos.py --limit 10
  .venv\\Scripts\\python title_drill_videos.py
  .venv\\Scripts\\python title_drill_videos.py --merge
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent
VIDEOS_ROOT = ROOT / "videos"
LIBRARY_PATH = ROOT / "drill_library.json"
OUTPUT_PATH = ROOT / "drill_titles.json"
THUMBNAILS_DIR = ROOT / "video_analysis" / "thumbnails"

SOCCER_KEYWORDS = re.compile(
    r"\b(drill|passing|dribbl|finish|shoot|agility|cone|rondo|goalkeeper|keeper|"
    r"defend|press|sprint|warm[\s-]?up|exercise|training|possession|cross|"
    r"header|volley|1v1|2v1|3v2|overlap|finishing|endurance|fitness)\b",
    re.I,
)

NOISE_PATTERNS = re.compile(
    r"(ebury|petrocub|suntem|subscribe|instagram|tiktok|youtube|@\w+|www\.|"
    r"follow for more|daily training content|like and follow|link in bio)",
    re.I,
)

SOCIAL_CTA = re.compile(r"(follow for more|daily training|subscribe|link in bio)", re.I)
COUNTING_TRANSCRIPT = re.compile(r"^(\d+[!.\s]+){3,}")


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("ffmpeg not found on PATH and imageio-ffmpeg unavailable") from exc


def find_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def has_audio_stream(video_path: Path) -> bool:
    ffprobe = find_ffprobe()
    if not ffprobe:
        return True
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def extract_audio(ffmpeg: str, video_path: Path, wav_path: Path) -> bool:
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 1000


def extract_frame(cap: cv2.VideoCapture, ratio: float) -> tuple[bool, any]:
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total <= 0:
        return False, None
    cap.set(cv2.CAP_PROP_POS_FRAMES, min(max(int(total * ratio), 0), total - 1))
    return cap.read()


def run_ocr(reader, frame) -> list[str]:
    try:
        results = reader.readtext(frame, detail=0, paragraph=True)
    except Exception:
        return []
    lines: list[str] = []
    for item in results:
        text = str(item).strip()
        if len(text) >= 3:
            lines.append(text)
    return lines


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" -|•:")
    return text


def score_title_candidate(text: str) -> float:
    text = normalize_text(text)
    if not text or len(text) < 8 or len(text) > 100:
        return 0.0
    if SOCIAL_CTA.search(text):
        return 0.0
    if NOISE_PATTERNS.search(text) and not SOCCER_KEYWORDS.search(text):
        return 0.0
    if re.fullmatch(r"[\d\W]+", text):
        return 0.0
    if COUNTING_TRANSCRIPT.match(text):
        return 0.0

    score = 0.0
    if SOCCER_KEYWORDS.search(text):
        score += 3.0
    if re.search(r"\b(drill|combo|variation|exercise|movement|jump|sprint)\b", text, re.I):
        score += 2.0
    if text[0].isupper():
        score += 0.5
    if 25 <= len(text) <= 80:
        score += 1.5
    elif 15 <= len(text) < 25:
        score += 0.5
    if text.endswith(":"):
        score -= 0.5
    if text.isupper() and len(text) > 40 and "DRILL" not in text:
        score -= 0.5
    return score


def pick_from_transcript(transcript: str) -> str | None:
    if not transcript.strip() or COUNTING_TRANSCRIPT.match(transcript.strip()):
        return None
    sentences = re.split(r"[.!?\n]+", transcript)
    best = ""
    best_score = 0.0
    for sentence in sentences:
        sentence = normalize_text(sentence)
        if len(sentence) < 12:
            continue
        score = score_title_candidate(sentence)
        if score > best_score:
            best_score = score
            best = sentence
    return best if best_score >= 2.5 else None


def pick_from_ocr(ocr_lines: list[str]) -> str | None:
    best = ""
    best_score = 0.0
    for line in ocr_lines:
        line = normalize_text(line)
        score = score_title_candidate(line)
        if score > best_score:
            best_score = score
            best = line
    return best if best_score >= 2.5 else None


def infer_visual_context(category: str, ocr_lines: list[str], transcript: str) -> str:
    combined = " ".join(ocr_lines + [transcript, category]).lower()
    tags: list[str] = []
    mapping = {
        "strength": ["squat", "strength", "gym", "power"],
        "agility": ["agility", "ladder", "cone", "footwork"],
        "passing": ["pass", "rondo", "possession", "one touch", "one-touch"],
        "dribbling": ["dribbl", "ball mastery"],
        "finishing": ["finish", "shoot", "goal", "striker"],
        "defending": ["defend", "press", "tackle", "block"],
        "goalkeeping": ["keeper", "goalkeeper", "save"],
        "endurance": ["sprint", "interval", "fitness", "endurance"],
    }
    for label, words in mapping.items():
        if any(word in combined for word in words):
            tags.append(label)
    if not tags:
        tags.append(category.replace(" Drills", "").lower())
    return ", ".join(dict.fromkeys(tags))


def suggest_title(
    category: str,
    transcript: str,
    ocr_lines: list[str],
) -> tuple[str, str, float]:
    ocr_pick = pick_from_ocr(ocr_lines)
    transcript_pick = pick_from_transcript(transcript)

    if ocr_pick and transcript_pick:
        if ocr_pick.lower() in transcript_pick.lower() or transcript_pick.lower() in ocr_pick.lower():
            return normalize_text(ocr_pick), "ocr+transcript", 0.9
        return normalize_text(ocr_pick), "ocr", 0.75

    if ocr_pick:
        return normalize_text(ocr_pick), "ocr", 0.7

    if transcript_pick:
        return normalize_text(transcript_pick), "transcript", 0.65

    short_transcript = normalize_text(transcript)
    if short_transcript and not COUNTING_TRANSCRIPT.match(short_transcript):
        words = short_transcript.split()
        snippet = " ".join(words[:12])
        if len(snippet) > 12 and score_title_candidate(snippet) > 0:
            return snippet[:80], "transcript_snippet", 0.45

    if ocr_lines:
        fallback = normalize_text(max(ocr_lines, key=len))
        if len(fallback) > 12 and not SOCIAL_CTA.search(fallback):
            return fallback[:80], "ocr_fallback", 0.35

    clean_category = category.replace(" Drills", "").strip()
    return f"{clean_category} Drill", "category_fallback", 0.25


class Pipeline:
    def __init__(self, model_size: str = "small", languages: list[str] | None = None):
        from faster_whisper import WhisperModel
        import easyocr

        self.ffmpeg = find_ffmpeg()
        self.whisper = WhisperModel(model_size, device="cpu", compute_type="int8")
        langs = languages or ["en", "pt", "es", "ro"]
        self.ocr = easyocr.Reader(langs, gpu=False, verbose=False)

    def process_video(self, video_path: Path, entry: dict, save_thumbnail: bool) -> dict:
        cap = cv2.VideoCapture(str(video_path))
        duration_sec = 0.0
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            if fps:
                duration_sec = round(frames / fps, 1)

        transcript = ""
        audio_present = has_audio_stream(video_path)
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "audio.wav"
            if audio_present and extract_audio(self.ffmpeg, video_path, wav_path):
                segments, _info = self.whisper.transcribe(
                    str(wav_path),
                    beam_size=5,
                    vad_filter=True,
                )
                transcript = normalize_text(" ".join(segment.text for segment in segments))

        ocr_lines: list[str] = []
        thumbnail_path = None
        if cap.isOpened():
            for ratio in (0.15, 0.5, 0.85):
                ok, frame = extract_frame(cap, ratio)
                if ok and frame is not None:
                    ocr_lines.extend(run_ocr(self.ocr, frame))
                    if save_thumbnail and ratio == 0.5 and thumbnail_path is None:
                        THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
                        thumbnail_path = THUMBNAILS_DIR / f"{entry['id']}.jpg"
                        cv2.imwrite(str(thumbnail_path), frame)
        cap.release()

        ocr_lines = list(dict.fromkeys(normalize_text(line) for line in ocr_lines if line.strip()))
        suggested_title, title_source, confidence = suggest_title(
            entry["category"],
            transcript,
            ocr_lines,
        )
        visual_context = infer_visual_context(entry["category"], ocr_lines, transcript)

        return {
            "id": entry["id"],
            "relativePath": entry["relativePath"],
            "category": entry["category"],
            "durationSec": duration_sec,
            "audioPresent": audio_present,
            "transcript": transcript,
            "ocrText": ocr_lines,
            "visualContext": visual_context,
            "suggestedTitle": suggested_title,
            "titleSource": title_source,
            "titleConfidence": confidence,
            "thumbnailPath": thumbnail_path.relative_to(ROOT).as_posix() if thumbnail_path else None,
            "processedAt": datetime.now(timezone.utc).isoformat(),
        }


def load_library() -> dict:
    return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))


def load_existing_results() -> dict:
    if OUTPUT_PATH.exists():
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    return {"videos": {}}


def save_results(data: dict) -> None:
    OUTPUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def merge_into_library() -> None:
    if not OUTPUT_PATH.exists():
        print("No drill_titles.json found. Run transcription first.")
        return
    library = load_library()
    titles = load_existing_results()
    by_id = titles.get("videos", {})
    merged = 0
    for video in library.get("videos", []):
        result = by_id.get(video["id"])
        if not result:
            continue
        video["suggestedTitle"] = result.get("suggestedTitle")
        video["transcript"] = result.get("transcript")
        video["ocrText"] = result.get("ocrText")
        video["visualContext"] = result.get("visualContext")
        video["titleSource"] = result.get("titleSource")
        video["titleConfidence"] = result.get("titleConfidence")
        video["durationSec"] = result.get("durationSec")
        video["thumbnailPath"] = result.get("thumbnailPath")
        merged += 1
    library["titleEnrichment"] = {
        "mergedAt": datetime.now(timezone.utc).isoformat(),
        "mergedCount": merged,
        "sourceFile": OUTPUT_PATH.name,
    }
    LIBRARY_PATH.write_text(json.dumps(library, indent=2), encoding="utf-8")
    print(f"Merged {merged} titles into {LIBRARY_PATH}")


def run(args: argparse.Namespace) -> int:
    if args.merge:
        merge_into_library()
        return 0

    library = load_library()
    videos = library.get("videos", [])
    if args.category:
        videos = [v for v in videos if v.get("category") == args.category]
    if args.limit:
        videos = videos[: args.limit]

    results = load_existing_results()
    results.setdefault("meta", {})
    results["meta"].update(
        {
            "model": args.model,
            "startedAt": results["meta"].get("startedAt") or datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    results.setdefault("videos", {})

    pipeline = Pipeline(model_size=args.model)
    processed = 0
    skipped = 0

    for index, entry in enumerate(videos, start=1):
        video_id = entry["id"]
        if not args.force and video_id in results["videos"]:
            skipped += 1
            continue

        video_path = ROOT / entry["relativePath"]
        if not video_path.exists():
            print(f"[{index}/{len(videos)}] missing: {entry['relativePath']}")
            continue

        print(f"[{index}/{len(videos)}] {video_id}")
        try:
            results["videos"][video_id] = pipeline.process_video(
                video_path,
                entry,
                save_thumbnail=args.save_thumbnails,
            )
            processed += 1
            save_results(results)
        except Exception as exc:
            print(f"  error: {exc}")
            results["videos"][video_id] = {
                "id": video_id,
                "relativePath": entry["relativePath"],
                "error": str(exc),
                "processedAt": datetime.now(timezone.utc).isoformat(),
            }
            save_results(results)

    results["meta"]["processedCount"] = len(results["videos"])
    results["meta"]["updatedAt"] = datetime.now(timezone.utc).isoformat()
    save_results(results)
    print(f"Done. processed={processed}, skipped={skipped}, total={len(results['videos'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Title soccer drill videos via audio + vision OCR")
    parser.add_argument("--limit", type=int, help="Process only the first N videos")
    parser.add_argument("--category", help="Process only one category folder name")
    parser.add_argument("--model", default="small", help="faster-whisper model size")
    parser.add_argument("--force", action="store_true", help="Reprocess videos already in drill_titles.json")
    parser.add_argument("--merge", action="store_true", help="Merge drill_titles.json into drill_library.json")
    parser.add_argument("--save-thumbnails", action="store_true", help="Save middle-frame thumbnails")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
