import argparse
import json
import sys
from datetime import datetime, timezone

from xai_automation.config.settings import load_settings
from xai_automation.services.logging import configure_logging
from xai_automation.storage.db import Database
from xai_automation.storage.repo import Repo
from xai_automation.workflows.pipeline import run_once
from xai_automation.workflows.publish_queue import approve_job, process_queue
from xai_automation.workflows.preflight import run_preflight
from xai_automation.workflows.assets_server import serve_assets


def _cmd_init_db() -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    return 0


def _cmd_run_once() -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    run_once(settings=settings, db=db)
    return 0


def _cmd_print_config() -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    payload = settings.to_public_dict()
    for k in sorted(payload.keys()):
        sys.stdout.write(f"{k}={payload[k]}\n")
    return 0


def _cmd_approve_job(job_id: str) -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    repo = Repo(db)
    n = approve_job(repo=repo, job_id=job_id)
    sys.stdout.write(f"approved_items={n}\n")
    return 0


def _cmd_process_queue(limit: int) -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    repo = Repo(db)
    n = process_queue(settings=settings, repo=repo, limit=limit)
    sys.stdout.write(f"processed_items={n}\n")
    return 0


def _cmd_preflight(no_network: bool) -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    repo = Repo(db)
    result = run_preflight(settings=settings, network=not no_network, repo=repo)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0 if bool(result.get("ok")) else 2


def _cmd_serve_assets(port: int | None) -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    serve_assets(settings=settings, port=port)
    return 0


def _cmd_costs(provider: str, month: str | None, limit: int) -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    repo = Repo(db)
    month_key = month.strip() if month and month.strip() else datetime.now(timezone.utc).strftime("%Y-%m")
    total = repo.get_monthly_cost_total(provider=provider, month_key=month_key)
    units = repo.get_monthly_cost_units(provider=provider, month_key=month_key)
    events = repo.list_cost_events(provider=provider, month_key=month_key, limit=limit)
    out = {
        "provider": provider,
        "month_key": month_key,
        "total_usd": total,
        "total_units": units,
        "free_tier_usd": float(settings.higgsfield_free_tier_monthly_usd) if provider == "higgsfield" else 0.0,
        "free_tier_videos": int(settings.higgsfield_free_tier_monthly_videos) if provider == "higgsfield" else 0,
        "events": events,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0


def _cmd_list_errors(provider: str | None, job_id: str | None, limit: int) -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    repo = Repo(db)
    rows = repo.list_api_errors(limit=limit, provider=provider, job_id=job_id)
    sys.stdout.write(json.dumps({"errors": rows}, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0


def _cmd_show_error(err_id: str) -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    db = Database(settings.sqlite_path)
    db.init()
    repo = Repo(db)
    row = repo.get_api_error(err_id)
    sys.stdout.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="xai-automation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db")
    sub.add_parser("run-once")
    sub.add_parser("print-config")
    pf = sub.add_parser("preflight")
    pf.add_argument("--no-network", action="store_true")
    sa = sub.add_parser("serve-assets")
    sa.add_argument("--port", type=int, default=None)
    ap = sub.add_parser("approve-job")
    ap.add_argument("--job-id", required=True)
    pq = sub.add_parser("process-queue")
    pq.add_argument("--limit", type=int, default=10)
    co = sub.add_parser("costs")
    co.add_argument("--provider", default="higgsfield")
    co.add_argument("--month", default=None)
    co.add_argument("--limit", type=int, default=50)
    el = sub.add_parser("errors")
    el.add_argument("--provider", default=None)
    el.add_argument("--job-id", default=None)
    el.add_argument("--limit", type=int, default=50)
    es = sub.add_parser("error")
    es.add_argument("--id", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "init-db":
        raise SystemExit(_cmd_init_db())
    if args.cmd == "run-once":
        raise SystemExit(_cmd_run_once())
    if args.cmd == "print-config":
        raise SystemExit(_cmd_print_config())
    if args.cmd == "preflight":
        raise SystemExit(_cmd_preflight(args.no_network))
    if args.cmd == "serve-assets":
        raise SystemExit(_cmd_serve_assets(args.port))
    if args.cmd == "approve-job":
        raise SystemExit(_cmd_approve_job(args.job_id))
    if args.cmd == "process-queue":
        raise SystemExit(_cmd_process_queue(args.limit))
    if args.cmd == "costs":
        raise SystemExit(_cmd_costs(args.provider, args.month, args.limit))
    if args.cmd == "errors":
        raise SystemExit(_cmd_list_errors(args.provider, args.job_id, args.limit))
    if args.cmd == "error":
        raise SystemExit(_cmd_show_error(args.id))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
