# BTO Compass

An AI assistant that helps Singapore home buyers navigate the HDB Build-To-Order (BTO) process. It combines a LangGraph agent (LLM-powered via Groq or AWS Bedrock), a TF-IDF-based retrieval-augmented generation (RAG) layer over HDB policy documents, and the OneMap Singapore API to score and recommend BTO projects against an applicant's income, budget, timeline, and location preferences.

## How it works

`app_graph` (defined in `src/graph.py`) is a 5-node LangGraph pipeline:

1. **`profile_validation`** — placeholder node for future applicant-input validation.
2. **`load_projects`** — loads the BTO project listing (CSV) and application-rate data (JSON) from `data/`, and pulls the latest scraped rates via `get_application_rates_context()`.
3. **`filter_projects`** — hard-filters projects by the applicant's effective budget (base budget + calculated EHG grant) and max waiting time.
4. **`rank_projects`** — scores each eligible project (`engine.score_project`) on a weighted blend of affordability, location/MRT proximity, demand, waiting time, and lifestyle amenities, and keeps the top 3.
5. **`generate_explanation`** — retrieves relevant HDB policy text (RAG) and rate context, and prompts the LLM (strictly grounded to the retrieved data) to produce the final chat response.

## Project structure

```
.
├── app.py                    # Streamlit web application (main UI)
├── main.py                   # CLI entry point / smoke test for the LangGraph pipeline
├── check_key.py               # Validates the Groq API key (syntax + live auth check)
├── test_inference.py          # Ad-hoc script: sends a real inference request to Groq
├── test_bedrock.py            # Ad-hoc script: verifies AWS Bedrock connectivity
├── pyproject.toml             # Project metadata & dependencies (uv-managed)
├── uv.lock                    # Locked dependency versions for uv
├── requirements.txt           # pip-installable dependency list
├── .python-version            # Pins the Python version (3.14)
├── .gitignore
├── .env                       # Local secrets (not committed) — see "Environment variables"
├── data/                      # Not included in this repo/upload — see "Data files" below
│   ├── bto_flat_offerings_feb2026.csv
│   ├── application_rates_feb2026.json
│   ├── application_rates.json
│   ├── rates_url.txt
│   └── policies/*.md
└── src/
    ├── config.py               # Central settings: paths, scoring weights, one LLM factory (`get_llm`)
    ├── state.py                 # `BTOState` — the LangGraph state schema (TypedDict)
    ├── graph.py                  # Builds and compiles `app_graph` (the 5-node pipeline above)
    ├── engine.py                  # Scoring/eligibility logic: `calculate_ehg_grant()`, `score_project()`
    ├── extractors.py               # `extract_income_from_pdf()` — parses payslips to get gross income
    ├── llm.py                      # A second LLM factory + `get_active_provider_info()` (used for the UI status display)
    ├── cost_tracker.py              # `UsageTracker` — computes USD cost from LLM token usage
    ├── rag/
    │   ├── rag_retriever.py          # `retrieve_policy()` — TF-IDF search over `data/policies/*.md`
    │   ├── rates_reader.py            # `get_application_rates_context()` — reads `data/application_rates.json`
    │   └── ingest_rates.py             # Offline utility: scrapes a rates webpage (Firecrawl) into `data/application_rates.json`
    └── tools/
        ├── onemap.py                 # OneMap Singapore API client (geocoding, MRT, themed amenities)
        └── tools.py                   # LangChain @tool-wrapped functions exposed to the agent
```

## File reference

### Root scripts

| File | Purpose |
|---|---|
| `app.py` | Streamlit entry point. Renders the sidebar (LLM provider status, payslip uploader, applicant profile form), runs the chat loop against `app_graph`, and renders a Pydeck map of recommended BTO projects with nearby kindergartens/hawker centres within a 1.5km radius. Also shows the retrieved RAG context and an estimated per-query token cost. |
| `main.py` | Headless CLI entry point. Invokes `app_graph` with a hard-coded sample applicant profile and prints the ranked recommendations and LLM explanation to the terminal — useful for testing the pipeline without the UI. |
| `check_key.py` | Standalone diagnostic. Confirms `GROQ_API_KEY` is present and correctly formatted (`gsk_...` prefix), then calls `client.models.list()` to verify it's actually authorized against Groq's API. |
| `test_inference.py` | Minimal smoke test that sends one live chat completion request to Groq and prints the response. |
| `test_bedrock.py` | Minimal smoke test that initializes the LLM via `src.llm.get_llm()` and sends a prompt — confirms AWS Bedrock connectivity. |

### Configuration files

| File | Purpose |
|---|---|
| `pyproject.toml` | Declares the project as `bto-compass`, pins `requires-python >= 3.14`, lists dependencies (LangChain, LangGraph, Streamlit, scikit-learn, pandas, pydantic, etc.), and defines a console entry point (`bto-compass`) built with `uv_build`. |
| `uv.lock` | Locked, reproducible dependency graph for [uv](https://docs.astral.sh/uv/) — install with `uv sync` to match exactly. |
| `requirements.txt` | pip-compatible dependency list, for environments not using `uv`. |
| `.python-version` | Pins the interpreter to Python 3.14. |
| `.gitignore` | Excludes virtual environments, `__pycache__`, build artifacts, and `.env` secrets from version control. |

### `src/` — core application logic

| File | Purpose |
|---|---|
| `config.py` | Central configuration module. Loads `.env`, resolves `DATA_PATH_CSV`/`DATA_PATH_JSON`, defines the project-scoring `WEIGHTS` (affordability 30%, location 25%, demand 20%, wait 15%, lifestyle 10%), reads `GROQ_API_KEY`/`GROQ_MODEL` (with a Streamlit-secrets fallback), and provides its own `get_llm()` that switches between Groq and Bedrock based on `LLM_PROVIDER` (defaults to `"groq"` here). This is the `get_llm()` actually used by `graph.py` and `extractors.py`. |
| `state.py` | Defines `BTOState`, the `TypedDict` schema LangGraph uses to carry applicant data, loaded projects, filtered/ranked results, RAG context, and chat messages through the pipeline. |
| `graph.py` | Builds the LangGraph `StateGraph` (`app_graph`): wires up the five pipeline nodes described above and compiles them into the runnable graph that `app.py` and `main.py` invoke. |
| `engine.py` | Domain logic for HDB eligibility and scoring. `calculate_ehg_grant()` computes the Enhanced CPF Housing Grant tier from income; `calculate_haversine_distance()` and `count_nearby_amenities()` support location scoring via OneMap; `score_project()` applies hard eligibility filters (income ceiling, singles restricted to 2-Room Flexi, budget vs. effective budget) then computes the weighted composite score used to rank projects. |
| `extractors.py` | Defines the `PayslipData` Pydantic model (`gross_income`, `cpf_deduction`, `employment_status`) and `extract_income_from_pdf()`, which extracts text from an uploaded payslip PDF (via `pypdf`) and uses an LLM + `PydanticOutputParser` to parse it into structured fields for auto-filling the income field in the UI. |
| `llm.py` | A second LLM factory. `get_active_provider_info()` reports which provider/model is "active" (defaults to `"bedrock"` here — note this differs from `config.py`'s default) and is what `app.py`'s sidebar displays. `get_llm()` here is used by `test_bedrock.py`. |
| `cost_tracker.py` | `UsageTracker.calculate_cost(usage, model_id)` converts LLM token usage into an estimated USD cost using a small hard-coded `PRICING` table (Bedrock Claude Haiku 4.5, Groq Llama-3.3-70B, and a `"default"` fallback rate). |

### `src/rag/` — retrieval-augmented generation

| File | Purpose |
|---|---|
| `rag_retriever.py` | `retrieve_policy(query, top_k=2)` loads every `*.md` file under `data/policies/`, TF-IDF-vectorizes them plus the query (`scikit-learn`), and returns the top-k most cosine-similar policy documents as grounding context for the LLM. Falls back to a small hard-coded EHG/income-ceiling summary if no policy files are found (e.g. on a fresh deployment). |
| `rates_reader.py` | `get_application_rates_context()` reads `data/application_rates.json` (walking up from its own location to find the project root, i.e. the folder containing `app.py`) and returns its `full_page_content`/`markdown`/`content` field as a context string for the LLM. Returns `"Data unavailable in live feed."` if the file is missing. |
| `ingest_rates.py` | Standalone data-refresh script (not called at runtime). Reads a target URL from `data/rates_url.txt`, scrapes it via the [Firecrawl](https://firecrawl.dev) API (`FIRECRAWL_API_KEY`), and writes the scraped markdown into `data/application_rates.json` — i.e. this is how the "live" application-rates knowledge base gets updated. Run it manually / on a schedule to refresh the data `rates_reader.py` later serves. |

### `src/tools/` — external integrations & agent tools

| File | Purpose |
|---|---|
| `onemap.py` | Thin client for Singapore's [OneMap](https://www.onemap.gov.sg/) government API: `geocode_address()` (address → lat/lng), `get_nearest_mrt_stops()`, `check_theme_status()`, and `get_theme_data()` / `find_nearby_amenities()` (pulls themed datasets such as kindergartens and hawker centres). Used directly by `engine.py`'s scoring logic and by `app.py`'s map rendering. |
| `tools.py` | Wraps RAG/OneMap logic as LangChain `@tool`-decorated functions for agent use: `search_hdb_policies()` (delegates to `rag_retriever.retrieve_policy`) and `get_project_amenities()` (delegates to `onemap.py`). |

## Data files (`data/`) — excluded from this upload

The app expects a `data/` directory at the project root with the following files. None were included in this upload, so recreate or supply them before running:

| File | Format | Purpose |
|---|---|---|
| `bto_flat_offerings_feb2026.csv` | CSV | The BTO project listing itself — one row per project/flat-type, with columns the code reads including `project_name`, `town`, `flat_type`, `price_min_sgd`, `price_max_sgd`, `waiting_time_months`, and `classification`. Loaded by `graph.py`'s `load_projects` node and is the base dataset that `filter_projects`/`rank_projects` operate on. |
| `application_rates_feb2026.json` | JSON | Structured per-project application/demand rate figures, keyed by project name (fuzzy-matched in `graph.py`'s `get_matching_rate`). Path is set by `config.py`'s `DATA_PATH_JSON` and loaded into `state["application_rates"]`, used both for demand scoring and shown to the LLM. |
| `application_rates.json` | JSON | Output of `ingest_rates.py` — the raw scraped webpage content (markdown) for the latest HDB application rates, read by `rates_reader.get_application_rates_context()` and injected into the LLM prompt as "live" context. **Note:** this is a different file from `application_rates_feb2026.json` above (see "Known inconsistencies"). |
| `rates_url.txt` | Plain text | A single URL (the page to scrape for current HDB application rates) consumed by `ingest_rates.py`. |
| `policies/*.md` | Markdown | The RAG knowledge base — official HDB eligibility rules and housing-policy documents in Markdown, one file per policy/topic. Indexed and searched by `rag_retriever.py` via TF-IDF + cosine similarity to ground the assistant's policy answers. |

## Environment variables

Create a `.env` file in the project root:

```dotenv
# --- LLM provider selection ---
LLM_PROVIDER=bedorck   # "groq" or "bedrock" — see "Known inconsistencies" re: default mismatch

# Groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-20b

# AWS Bedrock (only needed if LLM_PROVIDER=bedrock)
BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_SESSION_TOKEN=your_session_token   # only if using temporary credentials
AWS_DEFAULT_REGION=us-east-1

# OneMap (geocoding & amenities) — set both, different modules read different names
ONEMAP_API_TOKEN=your_onemap_token
ONEMAP_TOKEN=your_onemap_token

# Firecrawl — only needed to run src/rag/ingest_rates.py to refresh application-rates data
FIRECRAWL_API_KEY=your_firecrawl_key
```

## Prerequisites

- Python 3.14 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) (recommended, matches `pyproject.toml`/`uv.lock`) or `pip`
- A [Groq API key](https://console.groq.com/), and/or AWS credentials with Bedrock access
- A [OneMap API](https://www.onemap.gov.sg/apidocs/) token
- The `data/` files described above
- (Optional) a [Firecrawl](https://firecrawl.dev) API key, only if you intend to run `ingest_rates.py`

## Setup

**Option A — uv (recommended):**
```bash
uv sync
```

**Option B — pip:**
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

1. **Validate your Groq key:**
   ```bash
   python check_key.py
   ```
2. **(Optional) refresh the application-rates data:**
   ```bash
   python src/rag/ingest_rates.py
   ```
3. **Smoke-test the LLM connection:**
   ```bash
   python test_inference.py   # Groq
   python test_bedrock.py     # AWS Bedrock
   ```
4. **Run the CLI pipeline** (no UI, uses a hard-coded sample applicant):
   ```bash
   python main.py
   ```
5. **Run the web app:**
   ```bash
   streamlit run app.py
   ```
   Then open the URL Streamlit prints (default `http://localhost:8501`).

## Known inconsistencies

Worth being aware of before relying on this as-is:

- **Two independent LLM factories.** `src/config.py::get_llm()` (used by `graph.py` and `extractors.py` — i.e. the actual chat pipeline) defaults `LLM_PROVIDER` to `"groq"`. `src/llm.py::get_llm()`/`get_active_provider_info()` (used by `test_bedrock.py`, and what `app.py`'s sidebar displays) defaults to `"bedrock"`. If `LLM_PROVIDER` isn't set explicitly in `.env`, the sidebar can show a different provider than the one actually generating answers.
- **Token cost is likely mis-priced.** `app.py` calls `tracker.calculate_cost(usage)` without a `model_id`, so `UsageTracker` always falls back to the `"default"` pricing tier rather than the actual Groq/Bedrock rate.
- **Two different "application rates" files.** `config.py` points `DATA_PATH_JSON` at `data/application_rates_feb2026.json` (loaded into graph state for demand scoring), while `rates_reader.py` reads `data/application_rates.json` (the output of `ingest_rates.py`, injected as prompt context). Keep both populated and in sync, or verify which one your deployment actually needs.
- **Two OneMap token env vars.** `src/tools/onemap.py` reads `ONEMAP_API_TOKEN`; `app.py` reads `ONEMAP_TOKEN`. Set both to the same value.

## Notes

- `pyproject.toml` lists `pytest` as a dependency, implying a test suite exists; no test files beyond the manual `test_*.py` scripts above were included in this upload.
- `pyproject.toml` also defines a `bto-compass` console script pointing at `bto_compass:main` — once installed (`uv sync` / `pip install -e .`), the CLI may also be runnable as `bto-compass` directly, in addition to `python main.py`.
