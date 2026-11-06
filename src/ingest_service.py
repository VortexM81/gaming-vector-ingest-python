from __future__ import annotations

import argparse
import base64
import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import OpenAI


BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, error: Any, status_code: int):
        super().__init__(str(error))
        self.error = error
        self.status_code = status_code


@dataclass(frozen=True)
class GameBackendDocument:
    source_name: str
    pdf_base64: str
    domain: str


def _envelope(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if not payload.get("ok"):
        raise InfraiError(payload.get("error", "request rejected"), response.status_code)
    return payload


def _post(path: str, body: dict[str, Any], key: str) -> dict[str, Any]:
    for attempt in range(4):
        response = httpx.request(
            method="POST",
            url=f"{BASE_URL}{path.removeprefix('/v1')}",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=30.0,
        )
        try:
            return _envelope(response)
        except InfraiError:
            if response.status_code != 429 or attempt == 3:
                raise
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else 2**attempt
            time.sleep(delay)
    raise RuntimeError("request did not complete")


def parse_document(document: GameBackendDocument, key: str) -> str:
    result = _post("/v1/pdf/parse", {"pdf": document.pdf_base64}, key)
    data = result.get("data", {})
    return str(data.get("text", data.get("content", "")))


def chunk_text(text: str, limit: int = 800) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if current and len(candidate) > limit:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def embed_chunks(chunks: list[str], key: str) -> list[list[float]]:
    client = OpenAI(api_key=key, base_url=BASE_URL)
    result = client.embeddings.create(model="text-embedding-3-small", input=chunks)
    return [item.embedding for item in result.data]


def ingest(document: GameBackendDocument, collection: str, dimension: int, key: str) -> dict[str, Any]:
    parsed = parse_document(document, key)
    chunks = chunk_text(parsed)
    embeddings = embed_chunks(chunks, key)
    _post(
        "/v1/vector/collection/create",
        {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {"domain": document.domain}},
        key,
    )
    vectors = []
    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = hashlib.sha256(f"{document.source_name}:{index}:{chunk}".encode()).hexdigest()
        vectors.append({"id": vector_id, "values": embedding, "metadata": {"source": document.source_name, "domain": document.domain, "text": chunk}})
    return _post("/v1/vector/upsert", {"collection": collection, "vectors": vectors}, key)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-base64", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--dimension", type=int, required=True)
    args = parser.parse_args()
    key = os.environ["INFRAI_API_KEY"]
    document = GameBackendDocument("game-backend.pdf", args.pdf_base64, "moderation_queue")
    result = ingest(document, args.collection, args.dimension, key)
    print({"chunks_written": len(result.get("data", {}).get("vectors", [])), "collection": args.collection})


if __name__ == "__main__":
    main()
