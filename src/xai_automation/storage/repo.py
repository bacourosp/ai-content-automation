from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xai_automation.storage.db import Database
from xai_automation.services.errors import ApiCallError, dumps_redacted


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            size += len(b)
            h.update(b)
    return h.hexdigest(), size


@dataclass(frozen=True)
class PostIn:
    id: str
    source: str
    author_handle: str
    created_at: str
    text: str
    url: str
    lang: str


class Repo:
    def __init__(self, db: Database):
        self._db = db

    def get_kv(self, key: str) -> str | None:
        with self._db.connect() as con:
            r = con.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
            return None if r is None else str(r["v"])

    def set_kv(self, key: str, value: str) -> None:
        with self._db.connect() as con:
            con.execute(
                "INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, value),
            )
            con.commit()

    def upsert_post(self, p: PostIn) -> bool:
        text_hash = hashlib.sha256(p.text.encode("utf-8")).hexdigest()
        with self._db.connect() as con:
            existing = con.execute("SELECT 1 FROM posts WHERE id = ?", (p.id,)).fetchone()
            con.execute(
                """
                INSERT INTO posts(id, source, author_handle, created_at, text, url, lang, text_hash)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (p.id, p.source, p.author_handle, p.created_at, p.text, p.url, p.lang, text_hash),
            )
            con.commit()
            return existing is None

    def create_job(self, *, post_id: str, state: str) -> str:
        jid = uuid.uuid4().hex
        now = _utc_now_iso()
        with self._db.connect() as con:
            con.execute(
                """
                INSERT INTO jobs(id, post_id, state, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (jid, post_id, state, now, now),
            )
            con.commit()
        return jid

    def update_job(
        self,
        *,
        job_id: str,
        state: str | None = None,
        topic_score: int | None = None,
        score_json: dict[str, Any] | None = None,
        attempts_inc: bool = False,
        last_error: str | None = None,
    ) -> None:
        sets: list[str] = []
        args: list[Any] = []
        if state is not None:
            sets.append("state = ?")
            args.append(state)
        if topic_score is not None:
            sets.append("topic_score = ?")
            args.append(int(topic_score))
        if score_json is not None:
            sets.append("score_json = ?")
            args.append(json.dumps(score_json, ensure_ascii=False, separators=(",", ":")))
        if attempts_inc:
            sets.append("attempts = attempts + 1")
        if last_error is not None:
            sets.append("last_error = ?")
            args.append(last_error[:2000])
        sets.append("updated_at = ?")
        args.append(_utc_now_iso())
        args.append(job_id)
        q = f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?"
        with self._db.connect() as con:
            con.execute(q, tuple(args))
            con.commit()

    def get_job_score_json(self, job_id: str) -> dict[str, Any] | None:
        with self._db.connect() as con:
            r = con.execute("SELECT score_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if r is None:
                return None
            raw = str(r["score_json"] or "")
            if raw == "":
                return None
            return json.loads(raw)

    def get_job_post(self, job_id: str) -> dict[str, Any] | None:
        with self._db.connect() as con:
            r = con.execute(
                """
                SELECT j.id as job_id, j.post_id, j.state, j.topic_score, j.score_json, p.text, p.url, p.author_handle, p.created_at, p.lang
                FROM jobs j JOIN posts p ON p.id = j.post_id
                WHERE j.id = ?
                """,
                (job_id,),
            ).fetchone()
            return None if r is None else dict(r)

    def add_asset(self, *, job_id: str, kind: str, platform: str, path: Path) -> str:
        asset_id = uuid.uuid4().hex
        sha, size = _sha256_file(path)
        now = _utc_now_iso()
        with self._db.connect() as con:
            con.execute(
                """
                INSERT INTO assets(id, job_id, kind, platform, path, sha256, bytes, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (asset_id, job_id, kind, platform, str(path), sha, int(size), now),
            )
            con.commit()
        return asset_id

    def enqueue_publish(self, *, job_id: str, platform: str, payload: dict[str, Any], status: str) -> str:
        qid = uuid.uuid4().hex
        now = _utc_now_iso()
        with self._db.connect() as con:
            con.execute(
                """
                INSERT INTO publish_queue(id, job_id, platform, status, payload_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    qid,
                    job_id,
                    platform,
                    status,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    now,
                    now,
                ),
            )
            con.commit()
        return qid

    def list_publish_queue(self, *, statuses: list[str], limit: int) -> list[dict[str, Any]]:
        if not statuses:
            return []
        ph = ",".join(["?"] * len(statuses))
        q = f"SELECT * FROM publish_queue WHERE status IN ({ph}) ORDER BY created_at ASC LIMIT ?"
        with self._db.connect() as con:
            rows = con.execute(q, tuple(statuses) + (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_publish_item(self, queue_id: str) -> dict[str, Any] | None:
        with self._db.connect() as con:
            r = con.execute("SELECT * FROM publish_queue WHERE id = ?", (queue_id,)).fetchone()
            return None if r is None else dict(r)

    def update_publish_item(
        self,
        *,
        queue_id: str,
        status: str | None = None,
        attempts_inc: bool = False,
        last_error: str | None = None,
    ) -> None:
        sets: list[str] = []
        args: list[Any] = []
        if status is not None:
            sets.append("status = ?")
            args.append(status)
        if attempts_inc:
            sets.append("attempts = attempts + 1")
        if last_error is not None:
            sets.append("last_error = ?")
            args.append(last_error[:2000])
        sets.append("updated_at = ?")
        args.append(_utc_now_iso())
        args.append(queue_id)
        q = f"UPDATE publish_queue SET {', '.join(sets)} WHERE id = ?"
        with self._db.connect() as con:
            con.execute(q, tuple(args))
            con.commit()

    def add_cost_event(
        self,
        *,
        provider: str,
        job_id: str,
        asset_id: str,
        month_key: str,
        cost_usd: float,
        units: int,
        details: dict[str, Any] | None,
    ) -> str:
        cid = uuid.uuid4().hex
        now = _utc_now_iso()
        details_json = json.dumps(details or {}, ensure_ascii=False, separators=(",", ":"))
        with self._db.connect() as con:
            con.execute(
                """
                INSERT INTO cost_events(id, provider, job_id, asset_id, month_key, cost_usd, units, details_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, provider, job_id, asset_id, month_key, float(cost_usd), int(units), details_json, now),
            )
            con.commit()
        return cid

    def get_monthly_cost_total(self, *, provider: str, month_key: str) -> float:
        with self._db.connect() as con:
            r = con.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) as total FROM cost_events WHERE provider = ? AND month_key = ?",
                (provider, month_key),
            ).fetchone()
            return 0.0 if r is None else float(r["total"] or 0.0)

    def get_monthly_cost_units(self, *, provider: str, month_key: str) -> int:
        with self._db.connect() as con:
            r = con.execute(
                "SELECT COALESCE(SUM(units), 0) as total FROM cost_events WHERE provider = ? AND month_key = ?",
                (provider, month_key),
            ).fetchone()
            return 0 if r is None else int(r["total"] or 0)

    def list_cost_events(self, *, provider: str, month_key: str, limit: int) -> list[dict[str, Any]]:
        with self._db.connect() as con:
            rows = con.execute(
                "SELECT * FROM cost_events WHERE provider = ? AND month_key = ? ORDER BY created_at ASC LIMIT ?",
                (provider, month_key, int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]

    def log_api_error(self, *, job_id: str, asset_id: str, err: ApiCallError) -> str:
        eid = uuid.uuid4().hex
        now = _utc_now_iso()
        req = "" if err.request is None else dumps_redacted(err.request)
        resp = (err.response_text or "")[:20000]
        with self._db.connect() as con:
            con.execute(
                """
                INSERT INTO api_errors(id, provider, job_id, asset_id, method, url, status_code, message, request_json, response_text, is_quota, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    err.provider,
                    job_id,
                    asset_id,
                    err.method,
                    err.url,
                    err.status_code,
                    (err.message or "")[:2000],
                    req,
                    resp,
                    1 if err.is_quota else 0,
                    now,
                ),
            )
            con.commit()
        return eid

    def get_api_error(self, err_id: str) -> dict[str, Any]:
        with self._db.connect() as con:
            r = con.execute("SELECT * FROM api_errors WHERE id = ?", (err_id,)).fetchone()
            if r is None:
                raise KeyError(err_id)
            return dict(r)

    def list_api_errors(
        self,
        *,
        limit: int,
        provider: str | None = None,
        job_id: str | None = None,
    ) -> list[dict[str, Any]]:
        q = "SELECT * FROM api_errors"
        where: list[str] = []
        args: list[Any] = []
        if provider is not None and provider.strip() != "":
            where.append("provider = ?")
            args.append(provider)
        if job_id is not None and job_id.strip() != "":
            where.append("job_id = ?")
            args.append(job_id)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(int(limit))
        with self._db.connect() as con:
            rows = con.execute(q, tuple(args)).fetchall()
            return [dict(r) for r in rows]
