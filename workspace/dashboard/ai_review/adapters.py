"""Platform adapters. No unofficial APIs; LinkedIn/forums stay manual."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Callable

HttpFn = Callable[[str, str, dict[str, str], bytes | None], dict]


def default_http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http_{exc.code}:{detail[:200]}") from exc


class PlatformAdapter(ABC):
    key = ""

    @abstractmethod
    def publish(self, content: dict) -> dict:
        """Return {external_id, external_url}."""

    @abstractmethod
    def fetch_metrics(self, external_id: str) -> dict:
        """Return {views, reactions, comments_count}."""

    @abstractmethod
    def fetch_replies(self, external_id: str) -> list[dict]:
        """Return [{external_reply_id, author, body, url, posted_at}]."""


class DevtoAdapter(PlatformAdapter):
    key = "devto"

    def __init__(self, credentials: dict, http: HttpFn | None = None):
        self.api_key = str(credentials.get("api_key") or credentials.get("key") or "")
        self.http = http or default_http

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/vnd.forem.v1+json",
            "api-key": self.api_key,
        }

    def publish(self, content: dict) -> dict:
        payload = json.dumps(
            {
                "article": {
                    "title": content.get("title") or "Untitled",
                    "body_markdown": content.get("body") or "",
                    "published": True,
                }
            }
        ).encode()
        data = self.http("POST", "https://dev.to/api/articles", self._headers(), payload)
        return {
            "external_id": str(data.get("id") or ""),
            "external_url": str(data.get("url") or data.get("canonical_url") or ""),
        }

    def fetch_metrics(self, external_id: str) -> dict:
        data = self.http("GET", f"https://dev.to/api/articles/{external_id}", self._headers(), None)
        return {
            "views": int(data.get("page_views_count") or 0),
            "reactions": int(data.get("public_reactions_count") or data.get("reactions_count") or 0),
            "comments_count": int(data.get("comments_count") or 0),
        }

    def fetch_replies(self, external_id: str) -> list[dict]:
        data = self.http("GET", f"https://dev.to/api/comments?a_id={external_id}", self._headers(), None)
        comments = data if isinstance(data, list) else data.get("comments") or []
        out = []
        for item in comments:
            user = item.get("user") if isinstance(item.get("user"), dict) else {}
            out.append(
                {
                    "external_reply_id": str(item.get("id_code") or item.get("id") or ""),
                    "author": str(user.get("username") or item.get("author") or ""),
                    "body": str(item.get("body_html") or item.get("body") or ""),
                    "url": str(item.get("url") or ""),
                    "posted_at": str(item.get("created_at") or ""),
                }
            )
        return out


class HashnodeAdapter(PlatformAdapter):
    key = "hashnode"
    endpoint = "https://gql.hashnode.com/"

    def __init__(self, credentials: dict, http: HttpFn | None = None):
        self.token = str(credentials.get("token") or credentials.get("api_key") or "")
        self.publication_id = str(credentials.get("publication_id") or "")
        self.http = http or default_http

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": self.token,
        }

    def _gql(self, query: str, variables: dict) -> dict:
        payload = json.dumps({"query": query, "variables": variables}).encode()
        data = self.http("POST", self.endpoint, self._headers(), payload)
        if data.get("errors"):
            raise RuntimeError(str(data["errors"])[:200])
        return data.get("data") or {}

    def publish(self, content: dict) -> dict:
        data = self._gql(
            """
            mutation PublishPost($input: PublishPostInput!) {
              publishPost(input: $input) { post { id url } }
            }
            """,
            {
                "input": {
                    "title": content.get("title") or "Untitled",
                    "contentMarkdown": content.get("body") or "",
                    "publicationId": self.publication_id,
                }
            },
        )
        post = ((data.get("publishPost") or {}).get("post")) or {}
        return {"external_id": str(post.get("id") or ""), "external_url": str(post.get("url") or "")}

    def fetch_metrics(self, external_id: str) -> dict:
        data = self._gql(
            """
            query Post($id: ID!) {
              post(id: $id) { views reactionCount responseCount }
            }
            """,
            {"id": external_id},
        )
        post = data.get("post") or {}
        return {
            "views": int(post.get("views") or 0),
            "reactions": int(post.get("reactionCount") or post.get("reactionsCount") or 0),
            "comments_count": int(post.get("responseCount") or post.get("commentsCount") or 0),
        }

    def fetch_replies(self, external_id: str) -> list[dict]:
        data = self._gql(
            """
            query Post($id: ID!) {
              post(id: $id) {
                comments(first: 50) {
                  edges { node { id content { text } author { username } url dateAdded } }
                }
              }
            }
            """,
            {"id": external_id},
        )
        edges = (((data.get("post") or {}).get("comments") or {}).get("edges")) or []
        out = []
        for edge in edges:
            node = edge.get("node") or {}
            author = node.get("author") if isinstance(node.get("author"), dict) else {}
            content = node.get("content") if isinstance(node.get("content"), dict) else {}
            out.append(
                {
                    "external_reply_id": str(node.get("id") or ""),
                    "author": str(author.get("username") or ""),
                    "body": str(content.get("text") or node.get("body") or ""),
                    "url": str(node.get("url") or ""),
                    "posted_at": str(node.get("dateAdded") or ""),
                }
            )
        return out


class GmailAdapter:
    """Fetch new threads and send a reply. Not a publish/metrics adapter."""

    key = "gmail"

    def __init__(self, credentials: dict, http: HttpFn | None = None):
        self.token = str(credentials.get("access_token") or credentials.get("token") or "")
        self.http = http or default_http

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json", "Content-Type": "application/json"}

    def fetch_threads(self) -> list[dict]:
        if not self.token:
            return []
        data = self.http("GET", "https://gmail.googleapis.com/gmail/v1/users/me/threads?maxResults=20", self._headers(), None)
        threads = data.get("threads") or []
        out = []
        for item in threads:
            out.append(
                {
                    "external_thread_id": str(item.get("id") or ""),
                    "sender": str(item.get("from") or item.get("sender") or ""),
                    "subject": str(item.get("snippet") or item.get("subject") or ""),
                    "body": str(item.get("snippet") or ""),
                }
            )
        return out

    def reply(self, thread_id: str, body: str) -> dict:
        payload = json.dumps({"threadId": thread_id, "raw": body}).encode()
        data = self.http(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            self._headers(),
            payload,
        )
        return {"external_id": str(data.get("id") or thread_id)}


ADAPTERS: dict[str, type[PlatformAdapter]] = {
    "devto": DevtoAdapter,
    "hashnode": HashnodeAdapter,
}


def adapter_for(key: str, credentials: dict, http: HttpFn | None = None) -> PlatformAdapter | None:
    cls = ADAPTERS.get((key or "").strip().lower())
    if not cls:
        return None
    return cls(credentials, http=http)
