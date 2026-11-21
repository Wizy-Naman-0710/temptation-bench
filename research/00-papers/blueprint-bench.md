# Blueprint-Bench (Andon Labs, Sep 2025)

- Paper: [arXiv 2509.25229](https://arxiv.org/abs/2509.25229) · local copy `~/Downloads/2509.25229v1.pdf`
- Code: [AndonLabs/Blueprint-Bench-generation](https://github.com/AndonLabs/Blueprint-Bench-generation)
- One line: turn ~20 apartment photos into a 2D floor plan; compared by code with the ground-truth plan.

## The idea we copy: strict output format → code scoring
- The model must follow **9 drawing rules** (black walls, green doors, one red dot per room, only 4 pure colours, no gaps…).
- Why: strict rules make the scoring robust. Trade-off they accept: some expressiveness is lost, and bad instruction following gets punished.
- **Extraction step (code):** find red dots → flood fill each room → find green door pixels between rooms → JSON graph (rooms, doors, size ranks).
- **Scoring step (code):** weighted mix of 6 parts:
  - 50% edge overlap (Jaccard), 20% degree correlation, 10% graph density, 10% room count, 5% door count, 5% door orientation.
  - Score in [0, 1].
- They **tried an LLM for extraction and dropped it**: LLMs misread floor plans (claimed rooms were connected without a door; assumed the living room is biggest).

## Baselines
- Human baseline.
- "Random" baseline: generate a typical floor plan without seeing the photos. Many models scored at or below it.

## Other findings
- Agents (Codex CLI, Claude Code) with iteration did **not** beat single-pass models.
- Claude Code claimed "each room is fully enclosed" when it wasn't → a small example of an agent's self-report not matching reality.

## What we reuse for Temptation-Bench
- Every report the agent files (quarterly report, inspector answers, `deliver` claims) has a **fixed, strict format** (CSV / enum / numbers) so code can compare it with true state.
- Keep an LLM judge out of the main score. Use it only for secondary analysis, marked as such.
- Have baselines: a **scripted honest policy** and a **scripted greedy cheater** to show the score range.
- Be explicit about the trade-off: strict formats may punish format errors; keep a "format error" count separate from a "lie" count.
