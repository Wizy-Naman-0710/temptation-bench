# Claude Code tooling for Temptation-Bench

This is a short guide to the skills and plugins installed for this project, and when to use each one.
It's written for future Claude sessions, so they can pick the right tool without searching again.

- Last checked: 2026-11-22
- Everything is installed at **user scope** (`~/.claude/`), so nothing third-party lives in this repo.
- Files in this folder:
  - `README.md`: this guide
  - `install_skills.md`: the original recommendation write-up (the "why")
  - `inspect-ai-context.md`: an index of every Inspect AI docs page (an `llms.txt`-style list of `.md` URLs). Fetch a page from here when you need Inspect details.

## Which tool for which job

| When you are… | Use |
|---|---|
| Starting any new feature or design | `superpowers:brainstorming`, then `superpowers:writing-plans` |
| Writing simulator code | `superpowers:test-driven-development` + `property-based-testing` |
| Fixing a bug or a failing test | `superpowers:systematic-debugging` |
| About to say "done" or "tests pass" | `superpowers:verification-before-completion` |
| Setting up Python tooling (uv, ruff, pytest, pyproject) | `modern-python` |
| Checking money/time/rate formulas for unit mix-ups | `dimensional-analysis` |
| Checking whether the tests really catch bugs | `mutation-testing` |
| Planning experiments (factors, twins, randomization, blocking, replication) | `experimental-design` |
| Turning ideas into testable hypotheses or a pre-registration | `hypothesis-generation` |
| Working out how many runs/seeds are needed, or the minimum detectable effect | `statistical-power` |
| Analyzing results (tests, effect sizes, CIs, Bayesian methods) | `statistical-analysis` |
| Checking novelty or doing a literature search | `literature-review` |
| Making paper-quality figures | `scientific-visualization` |
| Creating or testing the project's own skills | `anthropic-skills:skill-creator` |
| Looking up Inspect AI or library APIs | Context7 MCP (`resolve-library-id` → `query-docs`), or a page from `inspect-ai-context.md` |
| Reviewing a diff, or cleaning up code | `/code-review`, `/simplify` (built in) |

## What's installed and where it came from

| Ecosystem | Items | Source / install |
|---|---|---|
| Superpowers | brainstorming, writing-plans, TDD, systematic-debugging, verification, code review, subagent-driven-development | `superpowers@claude-plugins-official` |
| Trail of Bits | `property-based-testing`, `modern-python`, `dimensional-analysis`, `mutation-testing` | `claude plugin marketplace add trailofbits/skills`, then `claude plugin install <name>@trailofbits` |
| K-Dense science | `experimental-design`, `hypothesis-generation`, `statistical-power`, `statistical-analysis`, `literature-review`, `scientific-visualization` | `gh skill install K-Dense-AI/scientific-agent-skills <name> --agent claude-code --scope user` |
| Skill Creator | `anthropic-skills:skill-creator` | Built in |
| Context7 | Docs lookup MCP | `context7@claude-plugins-official` |

## Caveats

- **`modern-python` changes `python` and `pip`.** At the start of every session it adds small wrapper scripts ("shims") that intercept `python script.py`, `pip install` and `python -m pip`, and suggest `uv` instead. `python -c` and `python -m <module>` pass straight through. Prefer `uv run` / `uv add` in this project (`uv` 0.12.5 is installed).
- **`literature-review` has optional paid scripts.** These are the AI-drawn diagrams (OpenRouter) and the Parallel search API. They only run if `OPENROUTER_API_KEY` / `PARALLEL_API_KEY` are set, and they aren't. **Ask the user before setting them or using paid APIs.**
- **K-Dense skills expect Python 3.12+** and their own isolated environment for their scripts.
- **The old `statistical-analysis`** skill (a simpler one from `anthropics/knowledge-work-plugins`) was replaced. A backup is at `~/.claude/skill-backups/statistical-analysis-old`.
- **All of these are third-party.** They've been scanned for network calls but not read line by line. Review one with `gh skill preview K-Dense-AI/scientific-agent-skills <name>`.

## Not installed (yet)

- **Pyright LSP** (Python type checking): add it once real Python code exists.
- **Plugin Developer Toolkit**: "later" in the recommendation.
- **Project-specific skills** (`temptation-bench-architect`, `banking-simulation-domain`, `benchmark-methodology`) and a project `CLAUDE.md`: planned but not written. See section 3 of `install_skills.md`. Build them with `skill-creator` when the user asks.

## Keep tooling lean

- Don't add more skill packs without a clear need. Overlapping skills cause context bloat and conflicting instructions.
- If you install or remove something, update this file.
