"""
title: Nodehome AI History
author: Nodehome
description: Query the private Claude/Codex/Claude Code history knowledge base for prior project context and decisions, including Nodehome GPU naming conventions.
required_open_webui_version: 0.9.0
version: 0.1.1
license: MIT
"""

import json
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        endpoint: str = Field(
            default="http://host.docker.internal:8765",
            description="Base URL for scripts/ai_history_kb.py serve.",
        )
        token: str = Field(
            default="",
            description="Optional bearer token matching AI_HISTORY_TOKEN.",
        )
        default_limit: int = Field(
            default=8,
            description="Default maximum number of history snippets to return.",
        )
        timeout_seconds: int = Field(
            default=10,
            description="HTTP timeout for the local history service.",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def get_project_history_context(
        self,
        query: str,
        source: str = "",
        limit: int = 0,
        force: bool = False,
        __event_emitter__=None,
    ) -> str:
        """
        Look up private project-history context from prior Claude, Codex, and Claude Code chats.

        Use this only when the user asks about prior decisions, previous work, current local project
        state, handovers, Nodehome/Local_AI/MealMastery history, GPU/vLLM/Open WebUI setup, or other
        named local systems. Do not use this for general world knowledge.

        Before interpreting snippets, apply the returned PROJECT_CONTEXT_CONTRACT. It contains
        canonical project aliases, evidence rules, and known Nodehome naming conventions.
        """

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Searching private AI history...",
                        "done": False,
                    },
                }
            )

        payload: dict[str, Any] = {
            "query": query,
            "limit": limit or self.valves.default_limit,
            "force": force,
        }
        if source in {"claude-desktop", "codex", "claude-code"}:
            payload["source"] = source

        try:
            data = self._post_json("/context", payload)
        except Exception as exc:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "AI history lookup failed",
                            "done": True,
                            "hidden": False,
                        },
                    }
                )
            return f"AI_HISTORY_ERROR: {exc}"

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "AI history lookup complete",
                        "done": True,
                        "hidden": True,
                    },
                }
            )

        return self._format_context(data)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        url = self.valves.endpoint.rstrip("/") + path
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                **self._auth_header(),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.valves.timeout_seconds) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc

    def _auth_header(self) -> dict[str, str]:
        if not self.valves.token:
            return {}
        return {"Authorization": f"Bearer {self.valves.token}"}

    def _project_context_contract(self) -> list[str]:
        return [
            "PROJECT_CONTEXT_CONTRACT",
            "- Treat retrieved snippets as private local project evidence, not as general world knowledge.",
            "- Prefer durable docs/current-state snippets over older chat speculation when they conflict.",
            "- Preserve source provenance and say when retrieved history is incomplete, stale, or conflicting.",
            "- Resolve known Nodehome aliases before answering; do not treat alias differences as uncertainty.",
            "Canonical Nodehome aliases:",
            "- GPU0 = NVIDIA index 0 = physical GPU #1 = bus 81:00.0.",
            "- GPU1 = NVIDIA index 1 = physical GPU #2 = bus C1:00.0.",
            "- GPU2 = NVIDIA index 2 = physical GPU #3 = bus C2:00.0 = pigtail-fed restricted card.",
            "- vLLM sustained workloads currently use GPU0/GPU1 only.",
            "- Ollama is restricted to CUDA_VISIBLE_DEVICES=0,1 while the pigtail rule is active.",
            "- The 300 W power cap applies to GPU0/GPU1 only; GPU2 is not targeted for sustained load.",
            "- The temporary pigtail rule retires only after the proper SF-1600F14HT PCIe cable is installed.",
        ]

    def _format_context(self, data: dict[str, Any]) -> str:
        status = data.get("status", "UNKNOWN")
        if status == "NO_HISTORY_CONTEXT":
            return "\n".join(
                [
                    "NO_HISTORY_CONTEXT",
                    f"query: {data.get('query', '')}",
                    f"reason: {data.get('reason', '')}",
                    "Do not use private history for this answer unless the user explicitly asks to force it.",
                ]
            )

        lines = [
            "HISTORY_CONTEXT",
            "Use these snippets only as private project/reference memory.",
            "Preserve uncertainty if the snippets do not fully answer the user.",
            *self._project_context_contract(),
            f"query: {data.get('query', '')}",
            f"router: {data.get('reason', '')}",
            f"fts_query: {data.get('fts_query', '')}",
            "",
        ]

        results = data.get("results") or []
        if not results:
            lines.append("No matching history snippets found.")
            return "\n".join(lines)

        for idx, row in enumerate(results, 1):
            lines.append(
                "{idx}. {source_system} | {kind} | {title} | {path}:{line}".format(
                    idx=idx,
                    source_system=row.get("source_system", ""),
                    kind=row.get("kind", ""),
                    title=row.get("title", ""),
                    path=row.get("source_path", ""),
                    line=row.get("line_no", ""),
                )
            )
            lines.append(str(row.get("snippet", "")).strip())
            lines.append("")

        return "\n".join(lines).strip()
