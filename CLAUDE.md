# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (in project root)
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt

# Run against a case
python -m src.main cases/demo_case
python -m src.main cases/lrr_case

# Web UI
streamlit run app.py

# Tests
python -m pytest tests/ -v
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v

# Lint (syntax check on all source files)
python -m py_compile src/scanner.py src/file_bus.py src/cli_client.py src/coordinator.py src/specialist_pool.py src/main.py
```

## Architecture: File Bus Pattern

The central design pattern: **agents communicate exclusively through files in `.mdt_workspace/`**. No agent talks directly to another agent, and Python code never interprets medical content. This makes the pipeline debuggable (every intermediate artifact is on disk), restartable (cached artifacts skip LLM calls), and extensible (new agents only need to read/write the conventions).

**Artifact flow:**
```
00_manifest.json → 01_index.json → 02_dispatch.json → 03_opinions/{name}.md → 05_mdt_report.html
```

Each artifact is produced once and read by downstream stages. If the artifact file already exists, the stage may skip its LLM call (idempotency — see `coordinator.py:271-276` and `specialist_pool.py` opinion checking).

## Pipeline: Three-Round Coordinator + Parallel Specialists

**Round 0** (Python, deterministic): `scanner.py` walks the case folder and produces `00_manifest.json` (file metadata, text previews, MD5 checksums). `context_extractor.py` extracts full text and page images from PDF/DOCX/XLSX into `.mdt_workspace/context/`.

**Rounds 1+2** (AI, combined): `coordinator.run_index_and_dispatch()` sends the manifest + file texts + available specialists list to the LLM in one call. The LLM returns a combined JSON with both file classifications and specialist assignments. Saved as two separate files for downstream compatibility.

**Round 3** (AI, parallel): `specialist_pool.py` runs all dispatched specialists concurrently via `ThreadPoolExecutor`. Each specialist gets its own workspace with only assigned files. System prompt = `prompts/specialists/base.md` + `prompts/specialists/{name}.md`. The `--cwd` is set to a per-specialist workspace under `.mdt_workspace/{name}_workspace/`. Opinions are cached — if `03_opinions/{name}.md` exists, the LLM call is skipped.

**Round 4** (AI): `coordinator.run_synthesis()` sends index + all specialist opinions to the LLM. The output is Markdown converted to styled HTML via `file_bus._md_to_html()` (Mermaid diagrams rendered server-side via Kroki.io API). This step uses `max_steps=1` — it's pure generation with no tool calls.

## Agent Backend

`cli_client.py` provides two backends behind a uniform `.run()` interface:

- **`OpenCodeClient`**: wraps `opencode run` CLI, creates temp agent files in `.opencode/agents/` with permission frontmatter, parses JSONL event stream.
- **`MiniAgentClient`**: wraps the vendored `codelet` CLI (in `mini-coding-agent-CLI/`) in one-shot mode. Extracts responses from `<final>...</final>` tags. The command name is configured via `MINI_AGENT_CMD` in `.env` (currently `codelet`).

Backend selection priority: `config/system.yaml` → `.env` (`AGENT_BACKEND`) → default `"opencode"`.

## Code Conventions

**scanner.py must contain zero medical keywords.** All file-type classification is deferred to the LLM. The scanner only extracts text/metadata — it never labels anything "影像" or "病理".

**Language support is bilingual (zh/en).** Prompts are loaded from `prompts/en/` subdirectories when `lang="en"`. Specialist prompt files are filtered: Chinese names contain non-ASCII characters; English names are ASCII-only. Selection is driven by `config/system.yaml` → `ui.language`.

**JSON parsing from LLM output is defensive.** `coordinator._extract_json()` strips markdown code fences, then scans line-by-line for the first `{` or `[` at a line boundary. Beware of mini-agent ASCII-art banners that contain stray braces.

**Codelet compaction tuning.** The `.mini-coding-agent/config.yaml` at the project root sets `target_chars: 60000`. This is needed because the synthesis prompt + index + 5 specialist opinions can reach 20-30K chars, exceeding codelet's default 12K threshold which triggers a `HardHaltError` during compaction. The project root config is auto-discovered because the coordinator runs synthesis without a `workspace_dir`, so codelet's `--cwd` is the project root.

**Resilience patterns:**
- `_run_with_retry()` in `coordinator.py` retries failed agent calls up to `coordinator_retries` times (default 3) with a 5s delay
- Specialist pool continues if individual specialists fail; errors go to `errors/{name}.log`
- Specialist timeout is 30 min with an automatic text-only fallback retry (10 min, no file reading)
- `start_new_session=True` on all subprocesses to isolate signal propagation

## Configuration Files

| File | What It Controls |
|------|-----------------|
| `config/system.yaml` | Specialist registry, timeouts, max_workers, UI language, debate toggle |
| `.env` | LLM provider/key/URL, agent backend, mini-agent parameters |
| `.mini-coding-agent/config.yaml` | Codelet harness: compaction target, max steps, token limits |
| `prompts/coordinator_*.md` | AI prompt templates for each coordinator round |
| `prompts/specialists/{name}.md` | Per-specialty analysis instructions |
