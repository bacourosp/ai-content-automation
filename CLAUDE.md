# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A low-resource, local-first automation that runs as short-lived processes (no long-running orchestrator). Each tick: pull AI-related posts from X.com → score and write a per-platform content plan with an LLM → render a vertical video via the Higgsfield MCP server → enqueue per-platform publish jobs in SQLite → optionally publish to TikTok/Instagram/Facebook. State lives entirely in SQLite; the runtime is meant to be driven by a scheduler (launchd / systemd timers), not a daemon.

The README is in Spanish; code, identifiers, and most log messages are English (a few user-facing strings are Spanish).

## Commands

```bash
# Setup (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .

# Tests (pytest config in pyproject.toml; testpaths=tests, -q)
pytest                              # full suite
pytest tests/test_e2e_pipeline.py  # one file
pytest tests/test_preflight.py::test_preflight_no_network  # one test
pytest --cov=xai_automation        # with coverage (pytest-cov installed)

# The CLI (entrypoint: xai_automation.cli:main, installed as `xai-automation`)
xai-automation init-db                 # create/migrate SQLite schema (idempotent)
xai-automation init-system [--write-env]# print callback URLs + per-platform setup checklist
xai-automation run-once                # one ingest→score→render→enqueue cycle
xai-automation preflight [--no-network]# validate env + connectivity (exit 2 on failure)
xai-automation process-queue --limit N # publish queued items
xai-automation approve-job --job-id X  # move a job's items from awaiting_approval→queued
xai-automation serve-assets [--port N] # asset server + OAuth callbacks (+ optional Cloudflare tunnel)
xai-automation costs|errors|error|print-config
```

There is no linter/formatter configured; match existing style. Every module uses `from __future__ import annotations` and modern type hints (`str | None`, `list[str]`).

## Architecture

Layered, with a strict dependency direction. Higher layers import lower ones, never the reverse:

```
cli.py                     # arg parsing only; each subcommand loads settings, opens DB, delegates
  └─ workflows/            # orchestration: pipeline, publish_queue, preflight, assets_server
       ├─ connectors/      # external write APIs: x_api, publish_{tiktok,instagram,facebook}
       ├─ mcp/             # Higgsfield via JSON-RPC MCP over HTTP (http_client + higgsfield wrapper)
       ├─ services/        # shared primitives: http, errors, retry, deepseek, gemini, logging, tunnel_manager
       ├─ storage/         # db (sqlite), schema (DDL), repo (all SQL lives here)
       └─ config/          # settings (frozen dataclass), env_loader
```

### The pipeline as a state machine (`workflows/pipeline.py`)

`run_once` → `_ingest_and_process` collects posts from sources, then `_process_job` advances each job through SQLite `jobs.state`. Knowing these states is the fastest way to debug a stuck job (query `jobs` and `api_errors`):

`detected` → `classified` → `scored` → (`dropped` if spam or score<50) → `video_planned` → (`blocked_higgsfield_budget` if over free tier) → `video_rendered` | `video_missing` | `failed_higgsfield` → `queued`. Dead ends: `failed_deepseek`.

Once `queued`, three rows (tiktok/instagram/facebook) are written to `publish_queue` with status `awaiting_approval` (if `REQUIRE_APPROVAL=true`, the default) or `queued`. Publish-queue statuses: `awaiting_approval` → `queued` → `published` | `failed`. When approval is off, `run_once` calls `process_queue` itself at the end.

### Conventions that span the codebase

- **Settings are the only config surface.** `config/settings.py` reads *everything* from env into one frozen `Settings` dataclass via `load_settings()`. Add new config by adding a field there with an `env(...)` default and a typed coercion helper (`_as_int/_as_float/_as_bool/_as_csv`). `env_loader` searches `.env` in CWD, parent, `/etc/xai-automation/xai.env`, `~/.config/...`, or `XAI_ENV_FILE`; **dotenv loading is skipped under pytest** so tests are hermetic.
- **LLM provider is duck-typed.** `DeepSeekClient` (NVIDIA-hosted, OpenAI-style `chat/completions`) and `GeminiClient` expose the same `ping()` / `score_post(prompt=, post_payload=)` returning a dict. `pipeline` picks one by `settings.llm_provider` (**"gemini" default**, model `gemini-2.5-flash`; or "nvidia" with `deepseek-ai/deepseek-v3.1-terminus`) and treats it as `Any`. Gemini forces `responseMimeType=application/json`. The output schema is strictly validated in `services/deepseek.py` (`parse_strict_json` / `_validate_score_schema`: enforces the `category` enum, storyboard, carousel slide shape `{title,bullets[],footer}`, and `seconds` bounds) — Gemini reuses those validators. If you change the expected model JSON, update both the validator and `prompts/deepseek_score_v1.txt`. Note `MAX_MODEL_OUTPUT_TOKENS` defaults to 4000 because the full 3-platform `content_plan` is large.
- **OAuth is turnkey.** `serve-assets` runs a custom handler (`workflows/assets_server.py`) that serves `/assets/...`, exposes `/oauth/{tiktok,meta}/start` (302 to the provider) and `/callback/{tiktok,meta}` (exchanges the code via `connectors/oauth_{tiktok,meta}.py` and writes tokens to `.env` via `config/env_writer.py`). With an ephemeral Cloudflare tunnel, `serve-assets` discovers the public URL and writes it to `.env` as `PUBLIC_BASE_URL` so the short-lived `process-queue` reads the current URL. `workflows/setup_report.py` builds the shared setup/checklist text used by `serve-assets` and `init-system`.
- **All HTTP goes through `services/http.py::HttpClient`,** which raises `ApiCallError` (in `services/errors.py`) on any failure, carrying provider/method/url/status/request/response. Pass a `provider=` string on every call — it drives quota detection (`is_quota` for 402/403/429 and known phrases) and SSE handling (Higgsfield responses may be `text/event-stream`, parsed by `_parse_sse_json`). `ApiCallError` is persisted via `repo.log_api_error`, and `request`/`response` are scrubbed by `redact_secrets` before storage. Never log raw payloads — use `dumps_redacted`.
- **All SQL lives in `storage/repo.py`.** Workflows never write SQL inline; they call `Repo` methods. Schema is a single DDL string in `storage/schema.py`, applied idempotently by `db.init()` (every command calls it, so it doubles as migration). The `kv` table stores X `since_id` cursors per source.
- **Retries** are explicit: wrap a thunk in `services/retry.py::retry(fn, max_attempts=, backoff_seconds=)` (linear backoff `backoff*attempt`). Used around every external call in `pipeline` and `publish_queue`.
- **Higgsfield is an MCP server, not a REST API.** `mcp/http_client.py` speaks JSON-RPC 2.0 (`initialize` → `tools/list` → `tools/call`). `mcp/higgsfield.py` resolves the render tool by name or heuristics, builds the `tools/call` arguments from the tool's `inputSchema` (falling back to `HIGGSFIELD_ARG_NAME`, default `video_spec`), and parses the result for a URL/path from MCP-standard shapes (`content[]` text/json/resource, `structuredContent`) plus flat dicts (`video_url`/`url`/`result_url`/`video_path`/`path`). The exact `video_spec` schema is a best guess — confirm it against the real MCP and override `HIGGSFIELD_TOOL_NAME`/`HIGGSFIELD_ARG_NAME` if needed. Render output may be a URL (downloaded) or a local path.
- **Render provider is pluggable** (mirrors the LLM-provider pattern). `RENDER_PROVIDER` selects the backend; `pipeline._build_renderer` returns the dedicated `HiggsfieldClient` for `higgsfield` (keeps the module binding stub-able in tests) or `mcp/render.py::build_render_provider` for the rest. Two transports implement the same `list_tools`/`call_tool` interface: `mcp/http_client.py::McpHttpClient` (HTTP JSON-RPC) and `mcp/stdio_client.py::McpStdioClient` (spawns a local server like `npx -y pkg@x.y.z`, newline-delimited JSON-RPC; injectable `popen_factory` for tests). `McpRenderClient` adapts the canonical `video_spec` to each tool (`input_kind="spec"` uses `_build_tool_arguments`; `"prompt"` flattens via `build_prompt_from_video_spec`). Pipeline cost/state/budget are generalized to `settings.render_provider` (states `failed_<provider>` / `blocked_<provider>_budget`; cost via `_render_cost_config`). Vetted providers: `higgsfield` (HTTP), `mcp` (generic HTTP, `RENDER_MCP_URL`), `glif` (stdio, pinned, locked to `GLIF_RENDER_ID`), `remotion_media` (stdio, pinned, kie.ai), `remotion_app` (HTTP, **self-host only** — `build_render_provider` rejects non-local URLs because it executes AI-generated code). **Security stance:** stdio commands pin exact npm versions, no dynamic tool registration, third-party render providers are off unless selected + keyed. Excluded by review: gongrzhe (archived), qhdrl12 (unofficial/unpinned), mcpmarket ai-video-generator (unverifiable), Remotion official MCP (docs-only), open-design (read-only MCP/daemon).
- **Image generation is official Gemini only.** `services/gemini.py::generate_image` calls `<image_model>:generateContent` (`GEMINI_IMAGE_MODEL`, default `gemini-2.5-flash-image`) and decodes `inlineData`. `pipeline._maybe_generate_carousel_images` runs it for IG carousel slides when `ENABLE_IMAGE_GEN=true` (off by default); failures never block a job. Multi-image IG carousel *publishing* is a follow-up.
- **Cost/budget gating:** before rendering, `pipeline` checks monthly Higgsfield spend (`cost_events`) against `HIGGSFIELD_FREE_TIER_MONTHLY_{USD,VIDEOS}` and may set `blocked_higgsfield_budget`. After a successful render it records a `cost_event`. `preflight` and the `costs` command read the same aggregates.
- **Instagram publishing requires a public URL.** Reels need the video reachable at `PUBLIC_BASE_URL/assets/<JOB_ID>/video.mp4`; rendered videos are copied to `out/assets/<JOB_ID>/video.mp4` and served by `serve-assets` (optionally exposed via Cloudflare tunnel).

### Gotchas

- `src/xai_automation/tunnel_manager.py` is a thin re-export shim; the real implementation is `services/tunnel_manager.py`. Edit the latter.
- `serve-assets` defaults its port to `WEBHOOK_PORT` (which defaults to `ASSET_SERVER_PORT`), not `ASSET_SERVER_PORT` directly — check both when ports look wrong.
- `Settings` default for `X_SOURCES` is `"timeline"`, which `_sources()` maps to recent search unless `list`/`accounts` sources are also set.

## Testing approach

Tests are hermetic and offline. `tests/conftest.py` puts `src/` on `sys.path`. Patterns to follow when adding tests:
- Use `monkeypatch.setenv(...)` for all config and `tmp_path` for `DATA_DIR`/`SQLITE_PATH`/`OUTPUT_DIR`/`ASSETS_DIR`.
- Stub external clients by `monkeypatch.setattr` on the *pipeline module's* binding (e.g. `pmod.XApiClient`, `pmod.DeepSeekClient`, `pmod.HiggsfieldClient`), then assert on rows read back from the SQLite DB. See `tests/test_e2e_pipeline.py` for the canonical end-to-end example.
