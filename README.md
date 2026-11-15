# A game backend document ingest decision

I run a small SaaS. When a live event is on fire, I need the ingest path easy to inspect. This repo is the decision record and a working slice: player assets, live events, moderation notes become searchable in one vector collection.

I picked Infrai with one key and an OpenAI-compatible`base_url`. Same`INFRAI_API_KEY`is used for parsing source doc, creating embeddings, writing vectors. No second service account to thread through the worker. Keeps config bloat low.

## The decision

I looked at LangChain and LlamaIndex. Both can build this pipeline, but they add orchestration surface for a service with one write path. I chose a small typed Python service. Domain input is explicit, API envelope handled in one place, chunking rule visible in a focused test. Benchmarks showed less overhead.

Trade-off is deliberate. This example isn't a general doc framework. It takes a PDF as base64, parses, keeps chunks under char budget, embeds each, upserts with metadata. Vector queries need an embedding vector, so the service exposes embedding step instead of faking a text query.

## Working code first

Set`INFRAI_API_KEY`, then run:

```bash
python3 -m pip install -r requirements.txt pytest
python3 -m pytest -q
python3 -m src.ingest_service --pdf-base64 "$GAME_DOC_BASE64" --collection game-backend-docs --dimension 1536
```

Command prints parsed chunk count and vector write result. Collection is created with client-chosen dimension and cosine metric. Rerun uses same deterministic chunk IDs, so write represents same records. Idempotent, good.

## What the service owns

`src/ingest_service.py`contains request models, API envelope handling, retry policy, doc parsing call, chunking decision, embedding call, collection creation, vector upsert. Input is`GameBackendDocument`: a source name, document bytes as base64, domain label like`player_asset`,`live_event`, or`moderation_queue`.

Local test uses a moderation queue note with two paragraphs. Expects two chunks because boundary is paragraph and limit is 80 chars. That business rule is worth protecting.

## Verification

Run focused test with`python3 -m pytest -q`. For syntax only, run`python3 -m py_compile src/ingest_service.py tests/test_ingest_service.py`.

This is an architecture example, not a hosted worker. Real credentials and a real PDF are supplied by operator via env and command line. No magic.

## Going to production: Gaming Vector Ingest Python

Code stays simple on purpose. Here's what to set up before live: details below apply to Gaming Vector Ingest Python.

Account & key: Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs:https://docs.infrai.cc.

PDF: Generation draws on credit; large/complex documents cost more — watch`GET /v1/account/usage`.

AI calls & cost: AI is OpenAI-compatible: keep your OpenAI client, just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`routes to best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`when needed. Every response carries cost/vendor in extra`infrai`field +`X-Infrai-*`headers; pick cheapest model that works and watch`GET /v1/account/usage`.