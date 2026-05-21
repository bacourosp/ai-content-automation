from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from xai_automation.config.settings import Settings
from xai_automation.connectors.x_api import XApiClient, build_ai_query
from xai_automation.mcp.http_client import McpHttpClient
from xai_automation.services.deepseek import DeepSeekClient, DeepSeekConfig
from xai_automation.storage.repo import Repo


log = logging.getLogger("xai_automation.preflight")


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "level": self.level, "message": self.message}


def run_preflight(*, settings: Settings, network: bool = True, repo: Repo | None = None) -> dict[str, Any]:
    checks: dict[str, CheckResult] = {}

    checks["env.nvidia_api_key"] = _req(settings.nvidia_api_key, "NVIDIA_API_KEY")
    checks["env.deepseek_model"] = _req(settings.deepseek_model, "DEEPSEEK_MODEL")
    checks["env.x_bearer_token"] = _req(settings.x_bearer_token, "X_BEARER_TOKEN")
    checks["env.higgsfield_mcp_url"] = _req(settings.higgsfield_mcp_url, "HIGGSFIELD_MCP_URL")
    checks["env.higgsfield_api_key"] = _req(settings.higgsfield_api_key, "HIGGSFIELD_API_KEY")

    if repo is not None:
        checks.update(_check_costs(settings=settings, repo=repo))

    if settings.require_approval:
        checks["env.publisher_tokens"] = CheckResult(
            ok=True,
            level="warn",
            message="REQUIRE_APPROVAL=true: tokens de publicación pueden faltar sin bloquear la validación E2E (no se publicará).",
        )
    else:
        checks["env.meta_access_token"] = _req(settings.meta_access_token, "META_ACCESS_TOKEN")
        checks["env.instagram_business_account_id"] = _req(settings.instagram_business_account_id, "INSTAGRAM_BUSINESS_ACCOUNT_ID")
        checks["env.facebook_page_id"] = _req(settings.facebook_page_id, "FACEBOOK_PAGE_ID")
        checks["env.tiktok_access_token"] = _req(settings.tiktok_access_token, "TIKTOK_ACCESS_TOKEN")

    if not network:
        return _finalize(checks)

    if checks["env.x_bearer_token"].ok:
        checks["net.x_api"] = _check_x(settings)
    else:
        checks["net.x_api"] = CheckResult(ok=False, level="error", message="omitido: falta X_BEARER_TOKEN")

    if checks["env.nvidia_api_key"].ok and checks["env.deepseek_model"].ok:
        checks["net.deepseek"] = _check_deepseek(settings)
    else:
        checks["net.deepseek"] = CheckResult(ok=False, level="error", message="omitido: falta NVIDIA_API_KEY/DEEPSEEK_MODEL")

    if checks["env.higgsfield_mcp_url"].ok and checks["env.higgsfield_api_key"].ok:
        checks["net.higgsfield_mcp"] = _check_higgsfield(settings)
    else:
        checks["net.higgsfield_mcp"] = CheckResult(ok=False, level="error", message="omitido: falta HIGGSFIELD_MCP_URL/HIGGSFIELD_API_KEY")

    return _finalize(checks)


def _req(value: str, name: str) -> CheckResult:
    if (value or "").strip() == "":
        return CheckResult(ok=False, level="error", message=f"falta {name}")
    return CheckResult(ok=True, level="ok", message="ok")


def _check_x(settings: Settings) -> CheckResult:
    try:
        x = XApiClient(bearer_token=settings.x_bearer_token, timeout_seconds=min(15, settings.timeout_seconds_x))
        q = build_ai_query(settings.x_include_keywords, settings.x_exclude_keywords, settings.x_language_hint)
        posts, _ = x.fetch_recent_search(query=q, since_id=None, max_results=10, languages=settings.x_language_hint)
        return CheckResult(ok=True, level="ok", message=f"ok (search recent; got={len(posts)})")
    except Exception as e:
        return CheckResult(ok=False, level="error", message=f"failed: {str(e)[:300]}")


def _check_deepseek(settings: Settings) -> CheckResult:
    try:
        ds = DeepSeekClient(
            DeepSeekConfig(
                api_key=settings.nvidia_api_key,
                base_url=settings.nvidia_api_base_url,
                model=settings.deepseek_model,
                timeout_seconds=min(20, settings.timeout_seconds_deepseek),
                max_output_tokens=32,
            )
        )
        ds.ping()
        return CheckResult(ok=True, level="ok", message="ok (chat/completions ping)")
    except Exception as e:
        return CheckResult(ok=False, level="error", message=f"failed: {str(e)[:300]}")


def _check_higgsfield(settings: Settings) -> CheckResult:
    try:
        mcp = McpHttpClient(url=settings.higgsfield_mcp_url, api_key=settings.higgsfield_api_key, timeout_seconds=min(25, settings.higgsfield_timeout_seconds))
        tools = mcp.list_tools()
        if not tools:
            return CheckResult(ok=False, level="error", message="connected but tools/list empty")
        return CheckResult(ok=True, level="ok", message=f"ok (tools={len(tools)})")
    except Exception as e:
        return CheckResult(ok=False, level="error", message=f"failed: {str(e)[:300]}")


def _finalize(checks: dict[str, CheckResult]) -> dict[str, Any]:
    ok = True
    errors: list[str] = []
    warns: list[str] = []
    for k, r in checks.items():
        if r.level == "error":
            ok = False
            errors.append(k)
        if r.level == "warn":
            warns.append(k)
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warns,
        "checks": {k: v.to_dict() for k, v in checks.items()},
    }


def _check_costs(*, settings: Settings, repo: Repo) -> dict[str, CheckResult]:
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    used_usd = repo.get_monthly_cost_total(provider="higgsfield", month_key=month_key)
    used_units = repo.get_monthly_cost_units(provider="higgsfield", month_key=month_key)
    free_usd = float(settings.higgsfield_free_tier_monthly_usd)
    free_videos = int(settings.higgsfield_free_tier_monthly_videos)

    level = "ok"
    ok = True
    msg_parts = [f"month={month_key}", f"used_usd={used_usd:.6f}", f"used_videos={used_units}"]
    if free_usd > 0:
        msg_parts.append(f"free_tier_usd={free_usd:.6f}")
        if used_usd >= free_usd:
            ok = False
            level = "error"
        elif used_usd >= free_usd * 0.9:
            level = "warn"
    if free_videos > 0:
        msg_parts.append(f"free_tier_videos={free_videos}")
        if used_units >= free_videos:
            ok = False
            level = "error"
        elif used_units >= int(free_videos * 0.9):
            if level != "error":
                level = "warn"

    checks: dict[str, CheckResult] = {}
    checks["cost.higgsfield_month"] = CheckResult(ok=ok, level=level, message="; ".join(msg_parts))
    recent = repo.list_api_errors(limit=1, provider="higgsfield", job_id=None)
    if recent and int(recent[0].get("is_quota") or 0) == 1:
        checks["logs.higgsfield_quota_recent"] = CheckResult(ok=True, level="warn", message="se detectó al menos 1 error reciente de cuota/límite")
    else:
        checks["logs.higgsfield_quota_recent"] = CheckResult(ok=True, level="ok", message="ok")
    return checks
