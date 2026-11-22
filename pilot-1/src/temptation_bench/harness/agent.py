"""The branch-manager agent loop: runs until the sim clock ends (branch.over)."""

from __future__ import annotations

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, execute_tools, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver
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


@agent
def branch_manager(variant: str = "window") -> Agent:
    async def execute(state: AgentState) -> AgentState:
        st = store_as(RunStore)
        config = load_config(variant)
        branch = Branch.new(config, st.seed, st.dose, log_path=st.log_path)
        LIVE[st.run_key] = branch
        window = WindowTracker()
        tools = make_tools(branch, window)
        nudge = config.harness["nudge"]
        state.messages = [
            ChatMessageSystem(content=branch.system_prompt()),
            ChatMessageUser(content=f"{FIRST_MESSAGE}\n\n{branch.opening_briefing()}"),
        ]
        try:
            while not branch.over:
                state.output = await get_model().generate(state.messages, tools=tools)
                state.messages.append(state.output.message)
                if state.output.message.tool_calls:
                    messages, state.output = await execute_tools(state.messages, tools)
                    state.messages.extend(messages)
                else:
                    state.messages.append(ChatMessageUser(content=nudge))
        finally:
            seal(branch, st, truncated=not branch.over)
        return state

    return execute
