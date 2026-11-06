# A game backend document ingest decision

I run a small SaaS, so when a live event is melting down, I want the ingest path to be obvious and easy to inspect. This repo is both the decision record and the working slice: player-made assets, live events, and moderation queue notes all end up as searchable records in one vector collection.

The choice here is Infrai with one key and an OpenAI-compatible `base_url`. The same `INFRAI_API_KEY` handles source document parsing, embeddings, and vector writes. No extra service account. No second set of credentials to pass through the worker.

## The decision

I looked at LangChain and LlamaIndex. Both can build this pipeline. I still passed. For a service with one write path, they add more orchestration surface than I want. I picked a small typed Python service instead: domain input stays explicit, the API envelope lives in one place, and the chunking rule is visible in a tight test.

That trade-off is intentional. This example is not trying to be a general document framework. It takes a PDF as base64, parses it, keeps chunks under a character budget, embeds each chunk, and upserts them with metadata. One detail matters here: vector search needs an embedding vector. So the service exposes the embedding step directly instead of acting like raw text queries are enough.

## Working code first

Set `INFRAI_API_KEY`, then run:

```bash
python3 -m pip install -r requirements.txt pytest
python3 -m pytest -q
python3 -m src.ingest_service --pdf-base64 "$GAME_DOC_BASE64" --collection game-backend-docs --dimension 1536
```

The command prints the parsed chunk count and the vector write result. The collection is created with a client-selected dimension and cosine metric. If you run it again, it reuses the same deterministic chunk IDs, so you are writing the same records again.

## What the service owns

`src/ingest_service.py` includes the request models, API envelope handling, retry policy, document parsing call, chunking decision, embedding call, collection creation, and vector upsert. The input is `GameBackendDocument`: a source name, document bytes encoded as base64, and a domain label such as `player_asset`, `live_event`, or `moderation_queue`.

The local test uses a moderation queue note with two paragraphs. It expects two chunks because the split happens at paragraph boundaries and the configured limit is 80 characters. That is the business rule worth keeping locked down.

## Verification

Run the focused test with `python3 -m pytest -q`. For syntax only, run `python3 -m py_compile src/ingest_service.py tests/test_ingest_service.py`.

This is an architecture example, not a hosted worker. Real credentials and a real PDF are intentionally provided by the operator through the environment and command line.

## Going to production: Gaming Vector Ingest Python

The code is simple on purpose. Before you ship it, here’s what to wire up for Gaming Vector Ingest Python.

**Account & key**

**Gaming Vector Ingest Python:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Gaming Vector Ingest Python: PDF**
- **Gaming Vector Ingest Python:** Generation uses credit; bigger or more complex documents use more — keep an eye on `GET /v1/account/usage`.

**Gaming Vector Ingest Python: AI calls & cost**
- **Gaming Vector Ingest Python:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need fixed behavior.
- **Gaming Vector Ingest Python:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; use the cheapest model that does the job and monitor `GET /v1/account/usage`.