from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .analysis import analyze_audio, fingerprint_file, save_json
from .config import AnalysisConfig
from .designs import DesignStore
from .export import export_timeline_csv
from .identity import IdentityCache
from .palette import generate_automatic_design
from .recognition import (
    RecognitionError,
    cover_url_for_release,
    download_fpcalc,
    find_fpcalc,
    identify_file,
)
from .storage import AnalysisCache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mvi",
        description="Music Visual Intelligence V1.2",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze an audio file.")
    analyze.add_argument("audio", type=Path)
    analyze.add_argument("--output", type=Path)
    analyze.add_argument("--cache-dir", type=Path, default=Path("cache/analyses"))
    analyze.add_argument("--cover", type=Path)
    analyze.add_argument("--csv", type=Path)

    identify = sub.add_parser(
        "identify",
        help="Recognize a song with AcoustID + MusicBrainz.",
    )
    identify.add_argument("audio", type=Path)
    identify.add_argument("--client", default=os.getenv("MVI_ACOUSTID_CLIENT"))
    identify.add_argument("--fpcalc", type=Path)
    identify.add_argument("--output", type=Path, default=Path("cache/identity"))

    inspect = sub.add_parser("inspect", help="Inspect a stored JSON analysis.")
    inspect.add_argument("analysis", type=Path)

    doctor = sub.add_parser("doctor", help="Check local module availability.")
    doctor.add_argument("--fpcalc", type=Path)

    setup_fp = sub.add_parser(
        "setup-fpcalc",
        help="Download official Windows fpcalc into this project.",
    )
    setup_fp.add_argument("--destination", type=Path)

    designs = sub.add_parser("designs", help="Work with personal designs.")
    design_sub = designs.add_subparsers(dest="design_command", required=True)
    design_list = design_sub.add_parser("list", help="List personal designs.")
    design_list.add_argument("fingerprint", nargs="?")
    design_list.add_argument("--store", type=Path, default=Path("cache/designs"))

    return parser


def print_summary(analysis, cache_hit: bool) -> None:
    print("=" * 78)
    print("MUSIC VISUAL INTELLIGENCE — V1.2")
    print("=" * 78)
    print(f"File:                 {analysis.audio.source_path}")
    print(f"Duration:             {analysis.audio.duration_seconds:.2f} s")
    print(f"Sample rate:          {analysis.audio.sample_rate} Hz")
    print(f"Channels:             {analysis.audio.channels}")
    print(f"Timeline frames:      {len(analysis.timeline)}")
    print(f"Estimated tempo:      {analysis.global_features['tempo_bpm']:.2f} BPM")
    print(f"Beats:                {len(analysis.beats)}")
    print(f"Significant changes:  {len(analysis.events)}")
    print(f"Segments:             {len(analysis.segments)}")
    print(f"Cache hit:            {cache_hit}")
    print()
    print("PERFORMANCE")
    print("-" * 78)
    for key, value in analysis.performance.items():
        print(f"{key:42} {value}")
    print()
    print("FIRST TIMELINE FRAMES")
    print("-" * 78)
    for frame in analysis.timeline[:10]:
        print(
            f"{frame.time:8.2f}s "
            f"B:{frame.bass_db:8.2f} "
            f"M:{frame.mids_db:8.2f} "
            f"H:{frame.highs_db:8.2f} "
            f"E:{frame.rms_db:8.2f} "
            f"Br:{frame.brightness:.3f} "
            f"N:{frame.novelty:.3f} "
            f"R:{frame.rhythm:.3f} "
            f"S:{frame.salience:.3f}"
        )


def command_analyze(args: argparse.Namespace) -> int:
    if not args.audio.exists():
        raise SystemExit(f"mvi: error: audio file not found: {args.audio}")
    if args.cover is not None and not args.cover.exists():
        raise SystemExit(f"mvi: error: cover image not found: {args.cover}")

    config = AnalysisConfig()
    cache = AnalysisCache(args.cache_dir)
    fingerprint = fingerprint_file(args.audio)
    cached = cache.get(fingerprint, config.analysis_version)

    if cached is not None:
        print_summary(cached, cache_hit=True)
        if args.output:
            save_json(cached, args.output)
        if args.csv:
            export_timeline_csv(cached, args.csv)
        return 0

    analysis = analyze_audio(args.audio, config)

    if args.cover:
        analysis.automatic_design = generate_automatic_design(args.cover)
        DesignStore("cache/designs").save_automatic(
            analysis.source_fingerprint,
            analysis.automatic_design,
        )

    cache_path = cache.put(analysis)
    if args.output:
        save_json(analysis, args.output)
    if args.csv:
        export_timeline_csv(analysis, args.csv)

    print_summary(analysis, cache_hit=False)
    print(f"Analysis cache:       {cache_path}")
    return 0


def command_identify(args: argparse.Namespace) -> int:
    if not args.audio.exists():
        raise SystemExit(f"mvi: error: audio file not found: {args.audio}")

    fingerprint = fingerprint_file(args.audio)
    cache = IdentityCache(args.output)
    cached = cache.get(fingerprint)

    if cached is not None:
        print("Identity cache hit.")
        print(json.dumps(cached.to_dict(), indent=2, ensure_ascii=False))
        return 0

    try:
        identity = identify_file(
            args.audio,
            client_key=args.client,
            fpcalc_path=args.fpcalc,
        )
    except RecognitionError as exc:
        raise SystemExit(f"mvi: recognition error: {exc}") from exc

    if identity.release_id:
        identity.cover_url = cover_url_for_release(identity.release_id, 500)

    cache_path = cache.put(fingerprint, identity)
    print(json.dumps(identity.to_dict(), indent=2, ensure_ascii=False))
    print(f"Identity cache: {cache_path}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    print("=" * 78)
    print("MUSIC VISUAL INTELLIGENCE — DOCTOR")
    print("=" * 78)
    print(f"Python:               {sys.version.split()[0]}")
    print(
        "AcoustID client:      "
        + ("configured" if os.getenv("MVI_ACOUSTID_CLIENT") else "missing")
    )

    fpcalc = find_fpcalc(args.fpcalc)
    print(f"fpcalc:               {fpcalc if fpcalc else 'missing'}")

    ready = bool(fpcalc and os.getenv("MVI_ACOUSTID_CLIENT"))
    print(f"Internet recognition: {'ready' if ready else 'not ready'}")

    if not fpcalc:
        print()
        print("Run `mvi setup-fpcalc` to place fpcalc inside this project.")
    if not os.getenv("MVI_ACOUSTID_CLIENT"):
        print("Set MVI_ACOUSTID_CLIENT to enable AcoustID lookup.")

    return 0 if ready else 1


def command_setup_fpcalc(args: argparse.Namespace) -> int:
    try:
        path = download_fpcalc(args.destination)
    except RecognitionError as exc:
        raise SystemExit(f"mvi: error: {exc}") from exc

    print(f"fpcalc installed inside project: {path}")
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    if not args.analysis.exists():
        raise SystemExit(f"mvi: error: analysis file not found: {args.analysis}")
    payload = json.loads(args.analysis.read_text(encoding="utf-8"))
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def command_designs(args: argparse.Namespace) -> int:
    store = DesignStore(args.store)
    results = store.list_personal(args.fingerprint)
    if not results:
        print("No personal designs found.")
        return 0

    for item in results:
        print(
            f"{item['design_id']} | "
            f"{item['name']} | "
            f"{item['base_analysis_fingerprint']}"
        )
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        return command_analyze(args)
    if args.command == "identify":
        return command_identify(args)
    if args.command == "doctor":
        return command_doctor(args)
    if args.command == "setup-fpcalc":
        return command_setup_fpcalc(args)
    if args.command == "inspect":
        return command_inspect(args)
    if args.command == "designs":
        return command_designs(args)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
