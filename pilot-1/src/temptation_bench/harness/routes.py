"""Per-route model args (Task 29 fix: gateway 400 on strict tools).

Inspect's `openai-api` provider defaults to `strict_tools=True`
(`inspect_ai/model/_providers/openai_compatible.py:99`) and sets `"strict"` on every tool from
it (`:566`, `tools_to_openai`). OpenAI strict mode needs every property in `required`, and
our tools have optional params (e.g. `list_applications.status`), so the gateway refused the
first generate. The openai-api routes (Luna, and qwen for the `people` role) therefore run
with `strict_tools=False`. The tool schemas stay the same for every model; the Anthropic
route is unchanged."""

from __future__ import annotations

from typing import Any

from inspect_ai.model import Model

OPENAI_API = "openai-api/"
PEOPLE_MODEL = "openai-api/xpl/qwen3.7-flash"  # spec D4: the `people` role


def model_args_for(slug: str) -> dict[str, Any]:
    """Model args for an eval's main model (`inspect_eval(model_args=...)`, `-M`)."""
    return {"strict_tools": False} if str(slug).startswith(OPENAI_API) else {}


def non_strict_tools(model: Model) -> Model:
    """For a model Inspect already built without our args (a role given as a string), turn
    strict tools off on its openai-api provider. Other providers are returned untouched."""
    from inspect_ai.model._providers.openai_compatible import OpenAICompatibleAPI

    if isinstance(model.api, OpenAICompatibleAPI):
        model.api.strict_tools = False
    return model
