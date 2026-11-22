"""Route check (spec §6/§7 route-check row, §7.1, §7.2; Task 30): the first paid call.

Two Haiku generates with the same fixed >= 5k-token prefix (local counter) and one tool,
then one `qwen3.7-flash` generate (the `people` role, openai-api, `strict_tools=False`).
Each uses the harness settings (`settings.generate_config`: reasoning effort low, no
temperature, no seed, `cache_prompt="auto"`, `max_retries`) with a small `max_tokens`.

- Inspect's local response cache is OFF (`cache=False`): otherwise a re-run would read
  call 2 from disk and prove nothing about provider caching. `--reuse-cache` turns it on
  with one fixed scope (`REUSE_SCOPE`), so a second `--reuse-cache` run in a new process
  reads all three calls from disk ($0, `ModelEvent.cache == "read"`).
- `check_log` reads the written `.eval`: call 2 has `input_tokens_cache_read > 0`, both
  Haiku requests carry `output_config.effort == "low"` (the field Inspect's Anthropic
  provider sets for Claude 5 from `reasoning_effort`: `anthropic.py` `completion_config`,
  logged as `ModelEvent.call.request`), and qwen returned text. On FAIL the runner exits
  non-zero with the §7.2 note; it never tries another route.

No text here is agent-facing in a run, but it still holds no banned word."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.event import ModelEvent
from inspect_ai.log import EvalLog
from inspect_ai.model import (
    CachePolicy,
    ChatMessageSystem,
    ChatMessageUser,
    GenerateConfig,
    get_model,
)
from inspect_ai.model._tokens import count_text_tokens
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import ToolInfo, ToolParam, ToolParams

from ..engine.config import load_config
from .pricing import DEFAULT_PRICING, register_prices
from .routes import PEOPLE_MODEL, model_args_for
from .settings import generate_config

HAIKU = "anthropic/claude-haiku-5-5"
MIN_PREFIX_TOKENS = 5000  # spec: ">= 5k-token prefix" (local o200k counter)
HAIKU_MAX_TOKENS = 512  # small, but room for low-effort adaptive thinking plus a sentence
PEOPLE_MAX_TOKENS = 1024  # qwen may reason first; too small could leave no text
INPUT_MARGIN = 2  # worst case: provider tokenizers may count up to 2 x the local counter
REUSE_SCOPE = {"route_check": "fixed-v1"}
FALLBACK_NOTE = "route fallback needs a fresh owner OK (spec §7.2); no other route was tried"
SAMPLE_INPUT = "Branch policy lookup."

TOOL = ToolInfo(
    name="read_policy_section",
    description="Read one section of the branch policy handbook by its number.",
    parameters=ToolParams(
        properties={"section": ToolParam(type="integer", description="The section number.")},
        required=["section"],
    ),
)
QUESTIONS = (
    "Which section of the handbook covers a new small business credit application? "
    "Answer in one short sentence.",
    "Which section of the handbook covers cash limits at the counter? "
    "Answer in one short sentence.",
)
PEOPLE_PROMPT = (
    "Rewrite this note as one friendly sentence: The branch opens at 09:00 on Monday "
    "and the counter closes at 16:30."
)

_TOPICS = (
    "new small business credit applications",
    "cash limits at the counter",
    "identity checks for new customers",
    "collateral and its valuation",
    "repayment schedules and due dates",
    "overdue loans and reminders",
    "complaints and how to answer them",
    "record keeping and file versions",
    "branch opening hours and staffing",
    "weekly management reports",
    "interest rates and fees",
    "income documents and payslips",
    "large deposits and their source",
    "staff conduct and gifts",
    "internal audit visits",
    "loan restructuring requests",
)
_LINES = (
    "This section sets the branch rules for {topic}.",
    "Staff follow these rules on every business day, from opening at 09:00 to closing at 17:00.",
    "Each case is written up in the customer file with the date, the officer name and the "
    "documents seen.",
    "Where a rule leaves room for judgement, the officer records the reason for the choice "
    "in plain words.",
    "The branch manager reviews a sample of these cases each week and signs the review sheet.",
    "Numbers are copied from the source documents exactly, with no rounding, and any "
    "difference is noted.",
    "A case that does not fit these rules is sent to the regional credit office with a "
    "short summary.",
    "Customers are told the outcome in writing within five business days, in clear and "
    "polite language.",
    "Paper copies are scanned on the same day and the originals are kept in the locked "
    "cabinet for seven years.",
    "Changes to these rules are announced by the regional office and take effect on the "
    "first Monday after notice.",
)


def policy_prefix() -> str:
    """The fixed handbook text (the shared prefix of both Haiku calls)."""
    parts = ["Woz Valley Bank, Branch 014: branch policy handbook.", ""]
    for n, topic in enumerate(_TOPICS, 1):
        parts.append(f"Section {n}: {topic}.")
        for k, line in enumerate(_LINES, 1):
            parts.append(f"{n}.{k} " + line.format(topic=topic))
        parts.append("")
    for n, topic in enumerate(_TOPICS, len(_TOPICS) + 1):
        parts.append(f"Section {n}: notes on {topic}, part two.")
        for k, line in enumerate(_LINES, 1):
            parts.append(f"{n}.{k} " + line.format(topic=topic))
        parts.append("")
    return "\n".join(parts)


def _harness() -> dict[str, Any]:
    return load_config("window").harness


def call_config(model: str, max_tokens: int) -> GenerateConfig:
    """The harness config for `model` (effort low, no temperature or seed, cache_prompt,
    max_retries) with a small `max_tokens` and no response-cache policy (see
    `response_cache`)."""
    base = generate_config(model, 0, 0, _harness(), people="template", variant="window")
    return base.model_copy(update={"cache": None, "max_tokens": int(max_tokens)})


def response_cache(reuse_cache: bool) -> CachePolicy | bool:
    """Off by default; with `--reuse-cache`, on with one fixed scope."""
    if not reuse_cache:
        return False
    return CachePolicy(expiry=_harness()["cache_expiry"], scopes=dict(REUSE_SCOPE))


# ---- worst case ----------------------------------------------------------------------------


def haiku_input_tokens() -> int:
    """Local count of one Haiku call's input: prefix + the longer question + the tool."""
    tool = json.dumps(TOOL.model_dump(mode="json", exclude_none=True))
    return (
        count_text_tokens(policy_prefix())
        + max(map(count_text_tokens, QUESTIONS))
        + (count_text_tokens(tool))
    )


def people_input_tokens() -> int:
    return count_text_tokens(PEOPLE_PROMPT)


def _worst_in(p: dict[str, Any]) -> float:
    return max(
        float(p.get(k, p["input"])) for k in ("input", "input_cache_write", "input_cache_read")
    )


def worst_case(
    prices: dict[str, Any] | None = None, max_retries: int | None = None
) -> tuple[float, str]:
    """Worst-case $ of the three calls from spec prices (`configs/pricing.yaml`):
    each call = INPUT_MARGIN x local input tokens x the highest input price (input, cache
    write, cache read) + max_tokens x output price, times (1 + max_retries) attempts."""
    prices = prices or yaml.safe_load(DEFAULT_PRICING.read_text())
    retries = int(_harness()["max_retries"]) if max_retries is None else int(max_retries)
    attempts = 1 + retries
    h, q = prices[HAIKU], prices[PEOPLE_MODEL]
    h_in, q_in = INPUT_MARGIN * haiku_input_tokens(), INPUT_MARGIN * people_input_tokens()
    h_call = (h_in * _worst_in(h) + HAIKU_MAX_TOKENS * float(h["output"])) / 1e6
    q_call = (q_in * _worst_in(q) + PEOPLE_MAX_TOKENS * float(q["output"])) / 1e6
    total = (2 * h_call + q_call) * attempts
    how = (
        f"2 Haiku x ({h_in} in x ${_worst_in(h)}/M + {HAIKU_MAX_TOKENS} out x "
        f"${float(h['output'])}/M) + 1 qwen x ({q_in} in x ${_worst_in(q)}/M + "
        f"{PEOPLE_MAX_TOKENS} out x ${float(q['output'])}/M), x {attempts} attempts"
    )
    return total, how


# ---- the task ------------------------------------------------------------------------------


@solver
def route_calls(people_model: str, reuse_cache: bool) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        cache = response_cache(reuse_cache)
        haiku = get_model()  # the eval's model
        prefix = policy_prefix()
        for question in QUESTIONS:  # call 1 writes the provider cache, call 2 reads it
            out = await haiku.generate(
                [ChatMessageSystem(content=prefix), ChatMessageUser(content=question)],
                tools=[TOOL],
                config=call_config(str(haiku), HAIKU_MAX_TOKENS),
                cache=cache,
            )
            state.messages.append(out.message)
        people = get_model(people_model, **model_args_for(people_model))
        out = await people.generate(
            [ChatMessageUser(content=PEOPLE_PROMPT)],
            config=call_config(people_model, PEOPLE_MAX_TOKENS),
            cache=cache,
        )
        state.messages.append(out.message)
        state.output = out
        return state

    return solve


@task
def route_check(people_model: str = PEOPLE_MODEL, reuse_cache: bool = False) -> Task:
    register_prices()
    return Task(
        dataset=[
            Sample(
                id="route_check",
                input=SAMPLE_INPUT,
                metadata={"people_model": people_model, "reuse_cache": reuse_cache},
            )
        ],
        solver=route_calls(people_model, reuse_cache),
        time_limit=600,
    )


# ---- assertions on the written log ---------------------------------------------------------


@dataclass(frozen=True)
class Row:
    name: str
    ok: bool
    detail: str


def effective_request(req: dict[str, Any]) -> dict[str, Any]:
    """The body the SDK sends: `extra_body` shallow-merged over the other request keys."""
    extra = req.get("extra_body")
    body = {k: v for k, v in req.items() if k != "extra_body"}
    return body | extra if isinstance(extra, dict) else body


def _sent(e: ModelEvent) -> dict[str, Any]:
    req = e.call.request if e.call is not None else {}
    return effective_request(req) if isinstance(req, dict) else {}


def _effort(e: ModelEvent) -> Any:
    oc = _sent(e).get("output_config")
    return oc.get("effort") if isinstance(oc, dict) else None


def _provider_rows(evs: list[ModelEvent]) -> list[Row]:
    h1, h2, q = evs
    rows = [
        Row(
            "call 1 and 2 share prefix and tool",
            bool(h1.input and h2.input)
            and h1.input[0].text == h2.input[0].text
            and len(h1.tools) == len(h2.tools) == 1,
            f"tools {len(h1.tools)}/{len(h2.tools)}",
        )
    ]
    u = h2.output.usage
    read = (u.input_tokens_cache_read or 0) if u is not None else 0
    rows.append(Row("call 2 cache_read > 0", read > 0, f"input_tokens_cache_read={read}"))
    for n, e in ((1, h1), (2, h2)):
        eff = _effort(e)
        rows.append(
            Row(
                f"call {n} request effort low",
                eff == "low",
                f"call.request.output_config.effort={eff!r}",
            )
        )
        thinking = _sent(e).get("thinking")
        rows.append(
            Row(
                f"call {n} thinking has no block_binding",
                isinstance(thinking, dict) and "block_binding" not in thinking,
                f"thinking keys={sorted(thinking) if isinstance(thinking, dict) else thinking}",
            )
        )
    return rows


def check_log(log: EvalLog, *, reuse_cache: bool) -> list[Row]:
    """The PASS/FAIL rows for one route-check log."""
    samples = log.samples or []
    evs = [e for s in samples for e in s.events if isinstance(e, ModelEvent) and e.error is None]
    rows = [Row("3 model calls logged", len(evs) == 3, f"{len(evs)} without error")]
    if len(evs) != 3:
        return rows
    caches = [e.cache for e in evs]
    if not reuse_cache:
        rows.append(Row("local response cache off", caches == [None] * 3, f"cache={caches}"))
        rows += _provider_rows(evs)
    elif caches == ["read"] * 3:
        rows.append(Row("all 3 calls read from the local response cache", True, "$0 re-run"))
    elif "read" not in caches:
        rows.append(
            Row(
                "local response cache written",
                caches == ["write"] * 3,
                f"cache={caches}; run --reuse-cache again for the $0 hit",
            )
        )
        rows += _provider_rows(evs)
    else:
        rows.append(Row("local cache: all or none read", False, f"cache={caches}"))
    text = evs[2].output.completion.strip()
    rows.append(Row("qwen answered (non-empty text)", bool(text), f"{len(text)} chars"))
    return rows


def passed(rows: list[Row]) -> bool:
    return all(r.ok for r in rows)


def table(rows: list[Row]) -> str:
    width = max(len(r.name) for r in rows)
    return "\n".join(
        f"{'PASS' if r.ok else 'FAIL'}  {r.name.ljust(width)}  {r.detail}" for r in rows
    )
