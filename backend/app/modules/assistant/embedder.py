"""Turns text into vectors through Telcron's own embedder service (services/embedder: the open-source
BAAI bge-small model). The ONLY code that talks to it; replaced wholesale in tests."""

import httpx

from app.core.config import get_settings

BATCH = 64


class EmbedderUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(get_settings().embed_url)


async def embed(texts: list[str], kind: str = "passage") -> list[list[float]]:
    """One vector per text. `kind` is "query" for a question or search, "passage" for stored text."""
    s = get_settings()
    if not s.embed_url:
        raise EmbedderUnavailable("no embedder configured")
    headers = {"Authorization": f"Bearer {s.embed_token}"} if s.embed_token else {}
    out: list[list[float]] = []
    try:
        async with httpx.AsyncClient(base_url=s.embed_url, timeout=30, headers=headers) as http:
            for i in range(0, len(texts), BATCH):
                response = await http.post("/embed", json={"texts": texts[i:i + BATCH], "kind": kind})
                response.raise_for_status()
                out += response.json()["vectors"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise EmbedderUnavailable(f"{type(exc).__name__}: {exc}"[:300]) from exc
    return out
