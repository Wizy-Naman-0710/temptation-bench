# Memory tools: scratchpad, key-value store, vector DB, notes, reminders

Checked 2026-11-21. Package versions are from PyPI on that date.

## 1. What the Vending-Bench papers did

- **Vending-Bench 1** ([arXiv 2502.15840](https://arxiv.org/abs/2502.15840)):
  - Context = last 30k tokens. Memory tools = read/write/delete on a **scratchpad**, a **key-value store**, and a **vector database**, "no explicit storage limit".
  - The vector DB used OpenAI `text-embedding-3-small` with cosine similarity.
  - Its finding: there was "no clear correlation" between failures and the point where context filled up. So memory limits were **not** the main cause of breakdowns.
- **Vending-Bench 2** ([Andon Labs page](https://andonlabs.com/evals/vending-bench-2)):
  - Context "limited to roughly 69000 tokens". "Older messages will be trimmed automatically, keeping approximately 61% of messages."
  - "Better planning tools, such as proper note-taking and reminder systems have been added."
  - The page does **not** mention the scratchpad / key-value / vector DB, or sub-agents.
  - Other VB2 changes: a full simulated year, adversarial suppliers, negotiation, delivery delays, suppliers going out of business, refund demands, and a simpler score (bank balance only).
- **Epoch AI review of VB2** ([2026-10-21](https://epoch.ai/benchmarks/vending-bench-2/review)), useful harness lessons:
  - Trimming keeps "the system prompt, the first message, and the most recent 61%". The rest is deleted with no summary.
  - The harness counts tokens with OpenAI's `tiktoken` for **every** provider, and counts encrypted reasoning strings as text. So the real usable context was ~45k for one model instead of 69k. **Lesson: count tokens with each provider's own counter (`model.count_tokens`), and say how reasoning is counted.**
  - `create_reminder` "always reports success, but the reminders never appear". **Lesson: test every tool with scripted policies** (see [project-structure-patterns.md](project-structure-patterns.md)).
  - A nightly report of unread emails filled ~40% of one model's window. **Lesson: watch how big your daily report gets.**
- **Prosus Vending Bench** (open source, [GitHub](https://github.com/ProsusAI/vending-bench)) memory tools: `write_note`, `read_notes`, `set_reminder`, `list_reminders`.

## 2. Simplest ways to build each memory tool (recommended for a 3-day build)

All of these can live in your pure-Python engine (or a `StoreModel`) and are exposed as `@tool`s. All are deterministic and free.

### Scratchpad (free text)

- One string per run. Tools: `scratchpad_read()`, `scratchpad_write(text, mode="append"|"replace")`.
- Add a size cap (e.g. 8k characters, proposal) so it can't become a second, unlimited context window.

### Key-value store

- `dict[str, str]` in the state. Tools: `kv_set(key, value)`, `kv_get(key)`, `kv_delete(key)`, `kv_list()`.
- Return a sorted list from `kv_list` (keeps output deterministic and cache-friendly).

### Notes + reminders (VB2 style)

- Notes: an append-only list of `(sim_time, text)`.
- Reminders: `set_reminder(day, text)`. Your engine puts due reminders into the **morning report**. This is the part VB2 got wrong, so write a test that a reminder set for day 5 appears on day 5.

### Built-in inspect `memory()` tool

- `from inspect_ai.tool import memory` → `memory(initial_data=None, readonly=False, instance=None)` (signature checked on 0.3.291). Docs: [Memory tool](https://inspect.aisi.org.uk/tools-standard.html#sec-memory).
- It gives a virtual `/memories` folder of files. Data is stored in the sample store, with **no sandbox needed**. The model can create, view, edit, delete and search files.
- It is based on Anthropic's [memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool), and "binds to it natively on Anthropic models". So Claude models get a tool shape they were trained on, while others get a normal function tool. **This may favour Claude in a cross-model benchmark.** Your own simple tools are more neutral.
- Compaction strategies (`CompactionTrim(memory=True)` etc.) warn the model to save to memory before trimming, but only when `memory()` is present.

### Vector DB (semantic search over notes)

- The honest answer for a small benchmark: **you probably don't need a real vector DB.** A few hundred notes fit in a NumPy array, and a brute-force cosine search takes microseconds.
- Pattern: embed each note when it is written. On `memory_search(query, k=5)`, embed the query, compute `scores = M @ q` (embeddings normalised), take the top k.
- Embedding options:

| Option | Cost | Notes |
|---|---|---|
| [fastembed](https://github.com/qdrant/fastembed) 0.9.1 | free, CPU, ONNX (no PyTorch) | `TextEmbedding(model_name="BAAI/bge-small-en-v1.5")`, then `list(model.embed(docs))`. Lightest install. Default model is `BAAI/bge-small-en-v1.5`. |
| [sentence-transformers](https://sbert.net/) 6.3.0 | free, CPU/GPU, needs PyTorch | Current quickstart uses `SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")` with `model.encode_query(...)`, `model.encode_document(...)`, `model.similarity(...)`. Small classic model: [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (still on HF, ~167M downloads). |
| OpenAI `text-embedding-3-small` (what VB1 used) | \$0.02 / 1M tokens ([pricing](https://developers.openai.com/api/docs/pricing), checked 2026-11-21) | Needs network, adds an API dependency. It's cheap, but not free and not offline. |

- For **reproducibility**, local embeddings are better: the same model files give the same vectors, with no API version drift. Pin the model name and revision, and cache embeddings by text hash.
- If you want a real store anyway: [sqlite-vec](https://github.com/asg017/sqlite-vec) 0.1.9 (one SQLite file, `vec0` virtual tables), [LanceDB](https://lancedb.github.io/lancedb/) 0.41.0, or [Chroma](https://docs.trychroma.com/) 1.5.9. All are overkill for under ~10k notes.

## 3. Suggested default for Temptation-Bench (proposal, can change)

- Context: `CompactionTrim(threshold=30_000 or 60_000, preserve=0.6, memory=False)`. This follows VB2's shape and stays cache-friendly.
- Memory tools: scratchpad + key-value + notes/reminders, all written by you, all in the engine. Add vector search only if you have time: fastembed + NumPy, ~40 lines.
- Log every memory read/write as an engine event too. Then you can measure things like "did the agent write down the suspicious transfer and later act against its own note?"
