# MDT-Orchestrator

An AI-powered multi-agent clinical consultation simulation platform. Give it a folder of patient files and it autonomously identifies data types, assembles a virtual specialist team, runs parallel consultations, and outputs a structured clinical report.

> **Current diseases**: Oncology MDT (tumor board) | Primary Aldosteronism (PA) AI diagnostic pathway.  
> **Core principle**: Python only acts as the "dispatcher" and "file courier" — all medical judgment, file classification, and specialist assignment is delegated to the AI Agent.

---

## Project Structure

```
MDTAgents/
├── README.md
├── Makefile                         # Common operations
├── app.py                           # Streamlit Web UI entry point
├── requirements.txt                 # Core dependencies
├── requirements-dev.txt             # Test dependencies (pytest)
├── requirements-ui.txt              # Web UI dependencies (streamlit)
├── .env                             # LLM provider, API key, agent backend config
├── config/
│   └── system.yaml                  # Disease context, specialists, timeouts, concurrency
├── prompts/
│   ├── oncology/                    # Oncology MDT prompts (zh)
│   │   ├── coordinator_*.md         # Index, dispatch, combined, synthesis
│   │   └── specialists/             # 5 oncology specialist prompts
│   ├── pa/                          # Primary Aldosteronism prompts (zh)
│   │   ├── coordinator_*.md         # Index, dispatch, combined, synthesis
│   │   └── specialists/             # 4 PA analysis module prompts
│   └── en/
│       ├── oncology/                # English oncology mirror
│       └── pa/                      # English PA mirror
├── src/
│   ├── main.py                      # CLI entry point
│   ├── scanner.py                   # Pure file scanning (zero medical keywords)
│   ├── context_extractor.py         # PDF/DOCX/XLSX text + image extraction
│   ├── file_bus.py                  # Filesystem message bus + HTML rendering
│   ├── coordinator.py               # Three-round coordinator engine
│   ├── specialist_pool.py           # Parallel specialist agent pool
│   ├── cli_client.py                # Agent CLI wrappers (opencode + mini_agent)
│   └── env_config.py                # .env loader + LLM config resolver
├── mini-coding-agent-CLI/           # Vendored codelet agent (mini_agent backend)
├── tests/
│   ├── unit/                        # Unit tests
│   └── integration/                 # Integration tests
└── cases/
    ├── demo_case/                   # Lung cancer demo (4 Markdown files)
    └── lrr_case/                    # Breast cancer case (9 PDFs)
```

---

## Architecture: File Bus Pattern

All inter-agent communication goes through files in `.mdt_workspace/`. No agent talks directly to another agent — Python code never interprets medical content.

```
cases/{case_id}/
├── [raw patient files...]
└── .mdt_workspace/
    ├── 00_manifest.json             # Scanner output: file metadata + previews
    ├── 01_index.json                # Coordinator: file classifications
    ├── 02_dispatch.json             # Coordinator: specialist assignments
    ├── 03_opinions/
    │   └── {name}.md                # Per-specialist consultation opinions
    ├── 05_mdt_report.html           # Final clinical report (styled HTML)
    ├── context/                     # Extracted text + page images from PDFs/DOCX/XLSX
    ├── errors/
    │   └── {agent_name}.log         # Per-agent error logs
    ├── logs/                        # Full audit traces per LLM call
    └── {name}_workspace/            # Per-specialist working directories
```

---

## Pipeline

```
Round 0  [Python]  scan files + extract text/images
         ↓ 00_manifest.json
Rounds 1+2  [AI]  classify files + dispatch specialists (single LLM call)
         ↓ 01_index.json + 02_dispatch.json
Round 3  [AI]  parallel specialist consultation (ThreadPoolExecutor)
         ↓ 03_opinions/{name}.md
Round 4  [AI]  coordinator synthesis → structured report
         ↓ 05_mdt_report.html
```

---

## Installation

### Prerequisites

- Python 3.10+
- For `mini_agent` backend: the vendored [codelet](mini-coding-agent-CLI/) CLI (installed automatically via `requirements.txt`)
- For `opencode` backend: [OpenCode CLI](https://opencode.ai/)

### Quick setup

```bash
# Create virtual environment and install
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Optionally install the codelet agent in editable mode
uv pip install -e mini-coding-agent-CLI/
```

### Configure .env

Copy and edit the example:

```bash
cp example.env .env
```

Key settings:

```bash
AGENT_BACKEND=mini_agent            # opencode | mini_agent
MINI_AGENT_CMD=codelet              # CLI command for mini_agent backend
LLM_PROVIDER=custom                 # kimi | zhipu | siliconflow | openai | custom
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-chat
```

The system auto-loads `.env` from the project root and supports multiple LLM providers (Kimi/Moonshot, Zhipu/GLM, SiliconFlow, OpenAI, DeepSeek, or any OpenAI-compatible endpoint).

---

## Quick Start

### CLI

```bash
# Oncology MDT (default)
python -m src.main cases/demo_case --disease oncology

# Primary Aldosteronism diagnostic pathway
python -m src.main cases/demo_case --disease pa

# Uses config/system.yaml disease setting when --disease is omitted
python -m src.main cases/lrr_case
```

### Make shortcuts

```bash
make install        # Install core dependencies
make install-dev    # Install core + test dependencies
make install-ui     # Install core + UI dependencies
make run            # Run MDT on cases/demo_case
make run CASE=cases/my_case
make ui             # Launch Streamlit Web UI
make test           # Run all tests
make test-unit      # Unit tests only
make test-int       # Integration tests only
make lint           # Python syntax check
```

### Web UI (Streamlit)

```bash
streamlit run app.py   # or: make ui
```

Three tabs: **🏥 Run MDT** (step-by-step pipeline with live progress), **🔍 Debug** (browse workspace artifacts), **⚙️ Admin** (edit config, manage specialists).

---

## Disease Switching

Set the disease context in `config/system.yaml` or via CLI:

```bash
# Via CLI (overrides config)
python -m src.main cases/demo_case --disease pa
python -m src.main cases/demo_case --disease oncology
```

```yaml
# Via config/system.yaml
disease: pa          # "oncology" or "pa"
```

Each disease has its own prompt directory (`prompts/{disease}/`), specialist registry, and file categories in `config/system.yaml`. Priority: **CLI arg > config > default "oncology"**.

### Available disease contexts

| Disease | Focus | Specialists | Output |
|---------|-------|-------------|--------|
| `oncology` | Tumor MDT — treatment decision | 5 clinical specialties (Radiology, Pathology, Oncology, Surgery, Internal Med) | 11-section MDT Consultation Report |
| `pa` | Primary Aldosteronism — diagnosis confirmation | 4 analysis modules (Hormone, Functional Test, Mass Spec, Adrenal Imaging) | 10-section PA Diagnostic Assessment |

---

## Configuration

Edit `config/system.yaml`:

```yaml
disease: pa                         # Disease context (oncology | pa)
ui:
  language: zh                      # zh = Chinese | en = English

opencode:
  backend: mini_agent               # opencode | mini_agent
  max_workers: 2                    # Parallel specialist concurrency
  coordinator_timeout: 300          # Seconds for index/dispatch rounds
  synthesis_timeout: 1800           # Seconds for synthesis round
  coordinator_retries: 3            # Retry attempts on failure
  specialist_timeout: 1800          # Per-specialist timeout (30 min)
  fallback_timeout: 600            # Text-only fallback (10 min)

specialists:
  oncology:                         # Registry keyed by disease
    - name: 影像科
      file_categories: [影像]
    # ... 5 specialists total
  pa:
    - name: 激素分析模块
      file_categories: [激素检测, 病历]
    # ... 4 modules total
```

---

## Agent Backends

Two backends behind a uniform `.run()` interface:

| Backend | Config value | What it wraps |
|---------|-------------|---------------|
| **OpenCodeClient** | `opencode` | `opencode run` CLI with agent MD files + JSON event stream |
| **MiniAgentClient** | `mini_agent` | Vendored `codelet` CLI in one-shot mode, any OpenAI-compatible API |

Selection priority: `config/system.yaml` → `.env` (`AGENT_BACKEND`) → default `"opencode"`.

---

## Extending

### Adding a new disease

1. Create `prompts/{disease}/` and `prompts/en/{disease}/` with coordinator + specialist prompts
2. Add `specialists.{disease}` in `config/system.yaml`
3. Set `disease: {disease}` in config

### Adding a new specialist (within a disease)

1. Create a new prompt file in `prompts/{disease}/specialists/`
2. Register it in `config/system.yaml` under `specialists.{disease}`
3. The Coordinator auto-discovers and dispatches it

### Supporting new file formats

Add a new extension and extraction function to `_SUFFIX_EXTRACTORS` in `src/scanner.py`. No prompt changes needed.

---

## Error Handling

- Each agent call failure is logged to `.mdt_workspace/errors/{agent_name}.log`
- A failed specialist does not block other specialists
- Coordinator failures raise `AgentError` and stop the pipeline
- Per-call audit traces (request + response + timing) are written to `logs/`

---

## Supported File Formats

| Extension | Handling |
|-----------|----------|
| `.md`, `.txt`, `.json`, `.csv` | Read directly |
| `.pdf` | pdfplumber text extraction + page screenshots |
| `.docx` | python-docx paragraph extraction |
| `.xlsx` | openpyxl to text table |
