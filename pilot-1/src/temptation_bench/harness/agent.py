"""The branch-manager agent loop: runs until the sim clock ends (branch.over)."""

from __future__ import annotations

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.log import transcript
from inspect_ai.model import (
    ChatMessageSystem,
    ChatMessageUser,
    Compact,
    CompactionTrim,
    ModelOutput,
    compaction,
    execute_tools,
    get_model,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import Tool
from inspect_ai.util import StoreModel, store_as

from ..engine.branch import Branch
from ..engine.config import load_config, runs_dir
from .tools import make_tools
from .window import WindowTracker

FIRST_MESSAGE = "Your first day starts now."
LIVE: dict[str, Branch] = {}


class RunStore(StoreModel):
    jsonl_path: str | None = None
    sha256: str | None = None
    truncated: bool = False
    seed: int = 0
    dose: int = 0
    run_key: str = ""
    log_path: str = ""


@solver
def setup_run() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        st = store_as(RunStore)
        st.seed = int(state.metadata["seed"])
        st.dose = int(state.metadata["dose"])
        st.run_key = f"{state.sample_id}|{state.epoch}"
        run_id = state.metadata.get("run_id", "local")
        st.log_path = str(runs_dir() / run_id / f"{state.sample_id}-e{state.epoch}.jsonl")
        return state

    return solve


def seal(branch: Branch, st: RunStore, truncated: bool) -> None:
    sealed = branch.finalize(truncated=truncated)
    st.jsonl_path = str(sealed.path)
    st.sha256 = sealed.sha256
    st.truncated = sealed.truncated
    LIVE.pop(st.run_key, None)


async def _generate(
    state: AgentState, compact: Compact, window: WindowTracker, tools: list[Tool]
) -> ModelOutput | None:
    """One generate on the compacted input. On `model_length`, force a trim and retry once;
    None if the retry overflows too (or the forced trim cannot fit). The window tracker
    always sees exactly the input that was sent."""
    for force in (False, True):
        try:
            input, c_message = await compact.compact_input(state.messages, force=force)
        except RuntimeError:  # Inspect: "Compaction insufficient"
            if not force:
                raise
            return None
        if c_message is not None:
            state.messages.append(c_message)
        window.update(input)
        output = await get_model().generate(input, tools=tools)
        if output.stop_reason == "model_length":
            continue  # the failed turn is not kept (as in Inspect's react())
        state.output = output
        state.messages.append(output.message)
        await compact.record_output(input, output)
        return output
    return None


@agent
def branch_manager(variant: str = "window") -> Agent:
    async def execute(state: AgentState) -> AgentState:
        st = store_as(RunStore)
        config = load_config(variant)
        branch = Branch.new(config, st.seed, st.dose, log_path=st.log_path)
        LIVE[st.run_key] = branch
        window = WindowTracker(offer_email_id=config.scenario["t1"]["email_id"])
        tools = make_tools(branch, window)
        nudge = config.harness["nudge"]
        state.messages = [
            ChatMessageSystem(content=branch.system_prompt()),
            ChatMessageUser(content=f"{FIRST_MESSAGE}\n\n{branch.opening_briefing()}"),
        ]
        compact = compaction(
            CompactionTrim(
                threshold=int(config.harness["trim_tokens"]), preserve=0.6, memory=False
            ),
            prefix=list(state.messages),  # system + first user message: always kept
            tools=tools,
        )
        try:
            while not branch.over:
                output = await _generate(state, compact, window, tools)
                if output is None:  # still too long after a forced trim: end the run
                    transcript().info("Run ended: input too long after a forced trim.")
                    break
                if output.message.tool_calls:
                    messages, state.output = await execute_tools(state.messages, tools)
                    window.observe(output.message, messages)
                    state.messages.extend(messages)
                else:
                    state.messages.append(ChatMessageUser(content=nudge))
        finally:
            seal(branch, st, truncated=not branch.over)
        return state

    return execute
