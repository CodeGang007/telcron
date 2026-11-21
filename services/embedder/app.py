"""Telcron's embedding service: turns text into vectors with an open-source model, on our own server.

    POST /embed   {"texts": [...up to 64], "kind": "query" | "passage"}
               -> {"model": "bge-small-en-v1.5", "dimensions": 384, "vectors": [[...], ...]}
    GET  /health  -> {"status": "ok", "model": ...}

The model (BAAI/bge-small-en-v1.5, MIT licence) runs on the CPU through ONNX (fastembed). Queries and
passages are embedded differently, as the model expects. When EMBED_TOKEN is set, callers must send
it as a bearer token; on the server the service is reachable only inside the Docker network anyway.
"""

import os
import secrets
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastembed import TextEmbedding
from pydantic import BaseModel, Field

MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
CODE = MODEL.split("/")[-1].lower()
TOKEN = os.environ.get("EMBED_TOKEN", "")

model = TextEmbedding(MODEL, cache_dir=os.environ.get("EMBED_CACHE", "/models"), threads=2)
DIMENSIONS = len(next(iter(model.query_embed(["probe"]))))
app = FastAPI(title="Telcron embedder", docs_url=None, redoc_url=None)


class EmbedIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)
    kind: Literal["query", "passage"] = "passage"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": CODE, "dimensions": DIMENSIONS}


@app.post("/embed")
def embed(data: EmbedIn, authorization: str = Header("")) -> dict:
    if TOKEN and not secrets.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(401, "bad token")
    texts = [t[:2000] or " " for t in data.texts]
    vectors = model.query_embed(texts) if data.kind == "query" else model.passage_embed(texts)
    return {"model": CODE, "dimensions": DIMENSIONS,
            "vectors": [[round(float(x), 6) for x in v] for v in vectors]}
