from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from xai_automation.services.http import HttpClient


log = logging.getLogger("xai_automation.x_api")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class XPost:
    id: str
    author_handle: str
    created_at: str
    text: str
    url: str
    lang: str


class XApiClient:
    def __init__(self, *, bearer_token: str, timeout_seconds: int):
        self._bearer = bearer_token
        self._http = HttpClient(timeout_seconds=timeout_seconds)
        self._base = "https://api.twitter.com/2"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._bearer}"}

    def _resolve_user_id(self, handle: str) -> str:
        u = handle.lstrip("@")
        url = f"{self._base}/users/by/username/{u}"
        j = self._http.get_json(url, headers=self._headers(), provider="x")
        return str(j["data"]["id"])

    def fetch_recent_search(
        self,
        *,
        query: str,
        since_id: str | None,
        max_results: int,
        languages: list[str],
    ) -> tuple[list[XPost], str | None]:
        url = f"{self._base}/tweets/search/recent"
        params: dict[str, str] = {
            "query": query,
            "max_results": str(max_results),
            "tweet.fields": "author_id,created_at,lang",
            "expansions": "author_id",
            "user.fields": "username",
            "sort_order": "recency",
        }
        if since_id:
            params["since_id"] = since_id
        j = self._http.get_json(url, headers=self._headers(), params=params, provider="x")
        posts = _parse_tweets(j, base_url="https://x.com")
        newest = _newest_id(posts)
        return posts, newest

    def fetch_list_tweets(
        self,
        *,
        list_id: str,
        since_id: str | None,
        max_results: int,
    ) -> tuple[list[XPost], str | None]:
        url = f"{self._base}/lists/{list_id}/tweets"
        params: dict[str, str] = {
            "max_results": str(max_results),
            "tweet.fields": "author_id,created_at,lang",
            "expansions": "author_id",
            "user.fields": "username",
        }
        if since_id:
            params["since_id"] = since_id
        j = self._http.get_json(url, headers=self._headers(), params=params, provider="x")
        posts = _parse_tweets(j, base_url="https://x.com")
        newest = _newest_id(posts)
        return posts, newest

    def fetch_user_tweets(
        self,
        *,
        handle: str,
        since_id: str | None,
        max_results: int,
        user_id_cache: dict[str, str],
    ) -> tuple[list[XPost], str | None, str]:
        u = handle.lstrip("@")
        user_id = user_id_cache.get(u)
        if not user_id:
            user_id = self._resolve_user_id(u)
            user_id_cache[u] = user_id

        url = f"{self._base}/users/{user_id}/tweets"
        params: dict[str, str] = {
            "max_results": str(max_results),
            "tweet.fields": "author_id,created_at,lang",
        }
        if since_id:
            params["since_id"] = since_id
        j = self._http.get_json(url, headers=self._headers(), params=params, provider="x")
        posts: list[XPost] = []
        data = j.get("data") or []
        for t in data:
            tid = str(t["id"])
            created_at = str(t.get("created_at") or _utc_now_iso())
            lang = str(t.get("lang") or "")
            text = str(t.get("text") or "")
            url2 = f"https://x.com/{u}/status/{tid}"
            posts.append(XPost(id=tid, author_handle=u, created_at=created_at, text=text, url=url2, lang=lang))
        newest = _newest_id(posts)
        return posts, newest, user_id


def _newest_id(posts: list[XPost]) -> str | None:
    if not posts:
        return None
    best = None
    for p in posts:
        if best is None or int(p.id) > int(best):
            best = p.id
    return best


def _parse_tweets(j: dict[str, Any], *, base_url: str) -> list[XPost]:
    users_by_id: dict[str, str] = {}
    includes = j.get("includes") or {}
    users = includes.get("users") or []
    for u in users:
        uid = str(u.get("id") or "")
        un = str(u.get("username") or "")
        if uid and un:
            users_by_id[uid] = un

    posts: list[XPost] = []
    data = j.get("data") or []
    for t in data:
        tid = str(t.get("id") or "")
        if tid == "":
            continue
        author_id = str(t.get("author_id") or "")
        author_handle = users_by_id.get(author_id, "")
        created_at = str(t.get("created_at") or _utc_now_iso())
        lang = str(t.get("lang") or "")
        text = str(t.get("text") or "")
        url = f"{base_url}/{author_handle}/status/{tid}" if author_handle else f"{base_url}/i/web/status/{tid}"
        posts.append(XPost(id=tid, author_handle=author_handle, created_at=created_at, text=text, url=url, lang=lang))
    return posts


def build_ai_query(include_keywords: list[str], exclude_keywords: list[str], languages: list[str]) -> str:
    inc = [k.strip() for k in include_keywords if k.strip()]
    exc = [k.strip() for k in exclude_keywords if k.strip()]
    parts: list[str] = []
    if inc:
        or_block = " OR ".join([f"({k})" if " " in k else k for k in inc[:25]])
        parts.append(f"({or_block})")
    for k in exc[:25]:
        parts.append(f"-{k}")
    parts.append("-is:retweet")
    parts.append("-is:reply")
    if languages:
        lang_block = " OR ".join([f"lang:{l}" for l in languages[:5]])
        parts.append(f"({lang_block})")
    return " ".join(parts).strip()
