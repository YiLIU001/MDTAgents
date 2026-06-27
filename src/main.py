#!/usr/bin/env python3
"""
MDT-Orchestrator entry point.

Usage:
    python -m src.main cases/demo_case
    python -m src.main cases/demo_case --disease pa
    python -m src.main cases/demo_case --disease oncology
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MDT-Orchestrator")
    parser.add_argument("case_folder", help="Path to the case folder")
    parser.add_argument(
        "--disease",
        default=None,
        choices=["oncology", "pa"],
        help="Disease context: overrides config/system.yaml disease setting",
    )
    return parser.parse_args(argv[1:])


def main() -> None:
    args = _parse_args(sys.argv)

    case_dir = Path(args.case_folder).resolve()
    if not case_dir.exists():
        raise FileNotFoundError(f"病例文件夹不存在: {case_dir}")

    # Determine project root (parent of src/)
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config" / "system.yaml"
    prompts_dir = project_root / "prompts"

    # Lazy imports so the module is importable without all deps installed
    from src.file_bus import FileBus
    from src.scanner import Scanner
    from src.coordinator import Coordinator
    from src.specialist_pool import SpecialistPool
    from src.context_extractor import ContextExtractor

    # ── Round 0: Initialise workspace & scan ──────────────────────────
    bus = FileBus(case_dir)
    bus.init_workspace()

    print(f"[Main] Scanning case folder: {case_dir}")
    scanner = Scanner()
    manifest = scanner.scan(case_dir)
    bus.save_manifest(manifest)
    print(f"[Main] Found {manifest.total_files} file(s). Manifest saved.")

    # ── Context extraction (deterministic, before any AI) ─────────────
    file_paths = [case_dir / fe.path for fe in manifest.files]
    extractor = ContextExtractor(bus.context_dir)
    print("[Main] Extracting file contexts…")
    extractor.extract_all(file_paths, progress_cb=lambda msg: print(f"  {msg}"))
    print("[Main] Context extraction complete.")

    # ── Rounds 1–2: Coordinator index + dispatch (single LLM call) ────
    coordinator = Coordinator(
        bus, config_path=config_path, prompts_dir=prompts_dir,
        disease=args.disease,
    )
    print(f"[Main] Disease context: {coordinator.disease}")
    index, dispatch = coordinator.run_index_and_dispatch(manifest)

    # ── Build per-agent workspaces (deterministic, after dispatch) ─────
    print("[Main] Building agent workspaces…")
    workspaces = bus.build_agent_workspaces(dispatch)
    for name, ws in workspaces.items():
        print(f"  {name}: {ws}")

    # ── Round 3: Parallel specialist consultation ──────────────────────
    pool = SpecialistPool(bus, config_path=config_path, prompts_dir=coordinator.prompts_dir)
    opinions = pool.run_parallel(dispatch)
    print(f"[Main] Received {len(opinions)} specialist opinion(s).")

    # ── Round 4: Synthesis ─────────────────────────────────────────────
    coordinator.run_synthesis(index, opinions)

    print()
    print("✅ MDT 完成。")
    print(f"   报告：{bus.report_path}")
    print(f"   工作区：{bus.workspace_dir}")


if __name__ == "__main__":
    main()
