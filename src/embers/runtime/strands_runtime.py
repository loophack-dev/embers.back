"""Strands Agents runtime. This is the only module that imports `strands`."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import anthropic
import google.genai.errors
import openai
from pydantic import BaseModel
from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.anthropic import AnthropicModel
from strands.models.gemini import GeminiModel
from strands.models.model import Model
from strands.models.openai_responses import OpenAIResponsesModel
from strands.types.exceptions import (
    ContextWindowOverflowException,
    MaxTokensReachedException,
    ModelThrottledException,
)
from strands.types.tools import ToolContext

from embers.artifacts.specs import Section, Slide
from embers.config import Settings
from embers.domain.artifacts import ArtifactService
from embers.domain.prompt import build_system_prompt
from embers.runtime.base import (
    Completed,
    Interrupted,
    ModelProviderError,
    RunOutcome,
    RunRequest,
    Usage,
)

logger = logging.getLogger(__name__)

ANTHROPIC_DEFAULT_MAX_TOKENS = 8192
MAX_OPTIONS = 6
MAX_QUESTION_CHARS = 1000
QUESTION_LIMIT_REACHED = (
    "Question limit reached. Continue with reasonable assumptions and mention them in your summary."
)

_PROVIDER_ERRORS: tuple[type[Exception], ...] = (
    ModelThrottledException,
    ContextWindowOverflowException,
    MaxTokensReachedException,
    anthropic.APIError,
    openai.APIError,
    google.genai.errors.APIError,
)


def _as_dicts(items: list[Any]) -> list[Any]:
    return [item.model_dump() if isinstance(item, BaseModel) else item for item in items]


def _make_artifact_tools(artifacts: ArtifactService, request: RunRequest) -> dict[str, Any]:
    """File tools bound to one task. The service validates limits and records the artifact."""
    task_id, agent_id = request.task_id, request.agent_id

    @tool
    async def create_document(
        title: str, sections: list[Section], summary: str | None = None
    ) -> str:
        """Create a Word (.docx) report.

        Args:
            title: Document title (up to 200 characters).
            sections: 1 to 30 sections, each with heading, paragraphs, bullets and an optional
                table (headers and rows).
            summary: Optional short summary shown under the title.
        """
        raw = {"title": title, "summary": summary, "sections": _as_dicts(sections)}
        return await artifacts.create("docx", task_id=task_id, agent_id=agent_id, raw=raw)

    @tool
    async def create_presentation(
        title: str, slides: list[Slide], subtitle: str | None = None
    ) -> str:
        """Create a PowerPoint (.pptx) presentation with a cover slide plus content slides.

        Args:
            title: Presentation title for the cover slide (up to 200 characters).
            slides: 1 to 20 slides, each with a title, up to 6 bullets and optional speaker notes.
            subtitle: Optional subtitle for the cover slide.
        """
        raw = {"title": title, "subtitle": subtitle, "slides": _as_dicts(slides)}
        return await artifacts.create("pptx", task_id=task_id, agent_id=agent_id, raw=raw)

    @tool
    async def create_markdown(title: str, content: str) -> str:
        """Create a Markdown (.md) text document.

        Args:
            title: Document title; the file starts with "# <title>".
            content: Markdown body.
        """
        raw = {"title": title, "content": content}
        return await artifacts.create("md", task_id=task_id, agent_id=agent_id, raw=raw)

    return {
        "create_document": create_document,
        "create_presentation": create_presentation,
        "create_markdown": create_markdown,
    }


def build_model(snapshot: dict[str, Any], settings: Settings) -> Model:
    """Direct provider model from the task's agent snapshot, passing only non-null params."""
    model_config: dict[str, Any] = snapshot["model_config"]
    provider = model_config["provider"]
    model_id = model_config["model_id"]
    params: dict[str, Any] = model_config.get("params") or {}
    temperature = params.get("temperature")
    top_p = params.get("top_p")
    max_tokens = params.get("max_tokens")
    api_key = settings.provider_key(provider)
    if api_key is None:
        raise ModelProviderError(f"No API key configured for provider '{provider}'.")
    client_args = {"api_key": api_key}

    common: dict[str, Any] = {}
    if temperature is not None:
        common["temperature"] = temperature
    if top_p is not None:
        common["top_p"] = top_p

    match provider:
        case "anthropic":
            return AnthropicModel(
                client_args=client_args,
                model_id=model_id,
                max_tokens=max_tokens or ANTHROPIC_DEFAULT_MAX_TOKENS,
                params=common,
            )
        case "openai":
            # Responses API: current GPT models reject function tools with reasoning on
            # /v1/chat/completions, and every Embers agent has at least ask_user.
            if max_tokens is not None:
                common["max_output_tokens"] = max_tokens
            return OpenAIResponsesModel(client_args=client_args, model_id=model_id, params=common)
        case "gemini":
            if max_tokens is not None:
                common["max_output_tokens"] = max_tokens
            return GeminiModel(client_args=client_args, model_id=model_id, params=common)
    raise ValueError(f"Unsupported provider: {provider}")


def _make_ask_user(max_questions: int) -> Any:
    asked = {"count": 0}

    @tool(context=True)
    def ask_user(question: str, tool_context: ToolContext, options: list[str] | None = None) -> str:
        """Ask the person a question when essential information is missing.

        Args:
            question: One concrete question for the person.
            options: Optional list of up to 6 suggested answers.
        """
        if asked["count"] >= max_questions:
            return QUESTION_LIMIT_REACHED
        reason = {
            "question": question[:MAX_QUESTION_CHARS],
            "options": options[:MAX_OPTIONS] if options else None,
        }
        # First call raises the interrupt and pauses the agent. On resume, Strands replays
        # this call and `interrupt` returns the person's answer; only then it counts.
        answer = tool_context.interrupt("ask_user", reason=reason)
        asked["count"] += 1
        return str(answer)

    return ask_user


@dataclass
class _TaskAgent:
    agent: Agent
    reported: Usage = field(default_factory=Usage)


class StrandsRuntime:
    def __init__(self, settings: Settings, artifacts: ArtifactService) -> None:
        self._settings = settings
        self._artifacts = artifacts
        self._agents: dict[UUID, _TaskAgent] = {}

    async def start(self, request: RunRequest) -> RunOutcome:
        snapshot = request.agent_snapshot
        tools: list[Any] = [_make_ask_user(self._settings.max_questions_per_task)]
        available = _make_artifact_tools(self._artifacts, request)
        for tool_id in snapshot.get("tools") or []:
            file_tool = available.get(tool_id)
            if file_tool is None:
                logger.warning(
                    "tool not implemented yet; skipped",
                    extra={"task_id": str(request.task_id), "tool": tool_id},
                )
                continue
            tools.append(file_tool)
        agent = Agent(
            model=build_model(snapshot, self._settings),
            system_prompt=build_system_prompt(snapshot, request.expected_output),
            tools=tools,
            callback_handler=None,
        )
        task_agent = _TaskAgent(agent)
        self._agents[request.task_id] = task_agent
        return await self._invoke(task_agent, request.instruction)

    async def resume(self, task_id: UUID, interrupt_id: str, answer: str) -> RunOutcome:
        task_agent = self._agents.get(task_id)
        if task_agent is None:
            raise RuntimeError(f"No agent instance in memory for task {task_id}")
        response = [{"interruptResponse": {"interruptId": interrupt_id, "response": answer}}]
        return await self._invoke(task_agent, response)

    def discard(self, task_id: UUID) -> None:
        self._agents.pop(task_id, None)

    async def _invoke(self, task_agent: _TaskAgent, prompt: Any) -> RunOutcome:
        try:
            result = await task_agent.agent.invoke_async(prompt)
        except _PROVIDER_ERRORS as exc:
            raise ModelProviderError(
                f"The model provider returned an error ({type(exc).__name__})."
            ) from exc
        usage = self._usage_delta(task_agent, result)
        if result.stop_reason == "interrupt" and result.interrupts:
            interrupt = result.interrupts[0]
            reason: dict[str, Any] = interrupt.reason if isinstance(interrupt.reason, dict) else {}
            return Interrupted(
                interrupt_id=interrupt.id,
                question=str(reason.get("question") or ""),
                options=reason.get("options"),
                usage=usage,
            )
        return Completed(text=str(result).strip() or None, usage=usage)

    @staticmethod
    def _usage_delta(task_agent: _TaskAgent, result: AgentResult) -> Usage:
        # accumulated_usage is cumulative for the agent instance, including resumes.
        accumulated = result.metrics.accumulated_usage
        total = Usage(
            input_tokens=int(accumulated.get("inputTokens", 0)),
            output_tokens=int(accumulated.get("outputTokens", 0)),
            total_tokens=int(accumulated.get("totalTokens", 0)),
        )
        delta = Usage(
            input_tokens=total.input_tokens - task_agent.reported.input_tokens,
            output_tokens=total.output_tokens - task_agent.reported.output_tokens,
            total_tokens=total.total_tokens - task_agent.reported.total_tokens,
        )
        task_agent.reported = total
        return delta
