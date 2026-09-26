"""Task use cases: delegate, per-agent queue, execution, questions, time limits and finish."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from embers.contracts.errors import ErrorCode
from embers.contracts.ws import (
    AckData,
    AnswerData,
    ArtifactOut,
    AskData,
    DelegateData,
    FinishData,
    TaskError,
    TaskStatus,
    TaskUsage,
)
from embers.domain.agents import to_agent_out
from embers.domain.ports import (
    AgentRepository,
    QuestionNotFoundError,
    QuestionNotPendingError,
    TaskArtifacts,
    TaskNotifier,
    TaskRecord,
    TaskRepository,
)
from embers.errors import ApiError
from embers.runtime.base import (
    AgentRuntime,
    Completed,
    ModelProviderError,
    RunOutcome,
    RunRequest,
    Usage,
)

logger = logging.getLogger(__name__)

PREVIEW_CHARS = 80


def preview(text: str | None) -> str | None:
    """Truncated text for logs; never log full instructions, answers or results."""
    if text is None or len(text) <= PREVIEW_CHARS:
        return text
    return text[:PREVIEW_CHARS] + "..."


class TaskSupervisor:
    """Keeps references to background coroutines and cancels them on shutdown."""

    def __init__(self) -> None:
        self._running: set[asyncio.Task[None]] = set()

    def spawn(self, coroutine: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        task = asyncio.create_task(coroutine)
        self._running.add(task)
        task.add_done_callback(self._running.discard)
        return task

    async def shutdown(self) -> None:
        for task in list(self._running):
            task.cancel()
        await asyncio.gather(*self._running, return_exceptions=True)


@dataclass(frozen=True)
class TaskLimits:
    task_timeout_s: float
    ask_timeout_s: float


@dataclass
class _AgentLane:
    """One task at a time per agent: `current` is working or waiting_user."""

    current: UUID | None = None
    queue: deque[UUID] = field(default_factory=deque)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def busy(self) -> bool:
        return self.current is not None or bool(self.queue)


def _usage_dict(usage: dict[str, Any] | None, step: Usage, model_id: str | None) -> dict[str, Any]:
    current = TaskUsage.model_validate(usage) if usage else TaskUsage(model_id=model_id)
    return TaskUsage(
        input_tokens=current.input_tokens + step.input_tokens,
        output_tokens=current.output_tokens + step.output_tokens,
        total_tokens=current.total_tokens + step.total_tokens,
        model_id=current.model_id or model_id,
    ).model_dump(mode="json")


def _model_id(task: TaskRecord) -> str | None:
    model_config = task.agent_snapshot.get("model_config") or {}
    value = model_config.get("model_id")
    return value if isinstance(value, str) else None


class TaskService:
    def __init__(
        self,
        *,
        tasks: TaskRepository,
        agents: AgentRepository,
        runtime: AgentRuntime,
        notifier: TaskNotifier,
        supervisor: TaskSupervisor,
        workspace_id: UUID,
        provider_available: Callable[[str], bool],
        limits: TaskLimits,
        artifacts: TaskArtifacts,
    ) -> None:
        self._tasks = tasks
        self._agents = agents
        self._runtime = runtime
        self._notifier = notifier
        self._supervisor = supervisor
        self._workspace_id = workspace_id
        self._provider_available = provider_available
        self._limits = limits
        self._artifacts = artifacts
        self._lanes: dict[UUID, _AgentLane] = {}
        self._worked_s: dict[UUID, float] = {}
        self._ask_timers: dict[UUID, asyncio.Task[None]] = {}

    # --- delegate ---

    async def create_task(self, data: DelegateData) -> TaskRecord:
        """Validate a delegate and persist the task as working or queued. Does not start it."""
        record = await self._agents.get(self._workspace_id, data.agent_id)
        if record is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Agent not found.", status_code=404)
        agent = to_agent_out(record)
        if agent.status == "archived":
            raise ApiError(ErrorCode.AGENT_ARCHIVED, "The agent is archived.", status_code=409)
        provider = agent.model_cfg.provider
        if not self._provider_available(provider):
            raise ApiError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"The server has no API key for provider '{provider}'.",
                status_code=409,
            )
        dumped = agent.model_dump(mode="json", by_alias=True)
        snapshot = {
            key: dumped[key]
            for key in ("name", "version", "model_config", "identity", "instructions", "tools")
        }
        lane = self._lanes.setdefault(agent.id, _AgentLane())
        async with lane.lock:
            status = TaskStatus.QUEUED if lane.busy else TaskStatus.WORKING
            task = await self._tasks.create(
                self._workspace_id,
                agent_id=agent.id,
                instruction=data.instruction,
                expected_output=data.expected_output.value if data.expected_output else None,
                agent_snapshot=snapshot,
                status=status,
            )
            if status == TaskStatus.WORKING:
                lane.current = task.id
            else:
                lane.queue.append(task.id)
        return task

    @staticmethod
    def ack_for(task: TaskRecord) -> AckData:
        return AckData(task_id=task.id, status=TaskStatus(task.status))

    def start(self, task: TaskRecord) -> None:
        """Start the task if it is its agent's current one; queued tasks start later."""
        if task.status != TaskStatus.WORKING:
            return
        request = RunRequest(
            task_id=task.id,
            agent_id=task.agent_id,
            agent_snapshot=task.agent_snapshot,
            instruction=task.instruction,
            expected_output=task.expected_output,
        )
        self._supervisor.spawn(self._run(task.id, lambda: self._start_step(task.id, request)))

    async def _start_step(self, task_id: UUID, request: RunRequest) -> RunOutcome:
        await self._tasks.mark_working(task_id)
        return await self._runtime.start(request)

    # --- answer ---

    async def accept_answer(self, data: AnswerData) -> tuple[TaskRecord, str | None]:
        """Validate and store an answer. Returns the task and the interrupt id to resume."""
        try:
            accepted = await self._tasks.accept_answer(
                self._workspace_id,
                task_id=data.task_id,
                question_id=data.question_id,
                answer=data.answer,
            )
        except QuestionNotFoundError:
            raise ApiError(
                ErrorCode.NOT_FOUND, "Task or question not found.", status_code=404
            ) from None
        except QuestionNotPendingError:
            raise ApiError(
                ErrorCode.QUESTION_NOT_PENDING,
                "The question is not pending or the task is not waiting for an answer.",
                status_code=409,
            ) from None
        self._cancel_ask_timer(accepted.task.id)
        return accepted.task, accepted.question.interrupt_id

    def resume(self, task: TaskRecord, interrupt_id: str | None, answer: str) -> None:
        async def step() -> RunOutcome:
            if interrupt_id is None:
                raise RuntimeError("Question has no interrupt id to resume")
            return await self._runtime.resume(task.id, interrupt_id, answer)

        self._supervisor.spawn(self._run(task.id, step))

    # --- execution ---

    async def _run(self, task_id: UUID, step: Callable[[], Awaitable[RunOutcome]]) -> None:
        """Run one working stretch (start or resume) within the remaining time budget."""
        remaining = self._limits.task_timeout_s - self._worked_s.get(task_id, 0.0)
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            async with asyncio.timeout(max(remaining, 0.0)):
                outcome = await step()
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            await self._fail(
                task_id, ErrorCode.TIMEOUT, "The agent exceeded the maximum working time."
            )
            return
        except ModelProviderError as exc:
            logger.warning("model provider error", extra={"task_id": str(task_id)})
            await self._fail(task_id, ErrorCode.MODEL_ERROR, str(exc))
            return
        except Exception:
            logger.exception("task execution failed", extra={"task_id": str(task_id)})
            await self._fail(task_id, ErrorCode.INTERNAL_ERROR, "Unexpected error.")
            return
        finally:
            self._worked_s[task_id] = self._worked_s.get(task_id, 0.0) + loop.time() - started

        try:
            await self._handle_outcome(task_id, outcome)
        except Exception:
            logger.exception("task outcome handling failed", extra={"task_id": str(task_id)})
            await self._fail(task_id, ErrorCode.INTERNAL_ERROR, "Unexpected error.")

    async def _handle_outcome(self, task_id: UUID, outcome: RunOutcome) -> None:
        task = await self._require(task_id)
        usage = _usage_dict(task.usage, outcome.usage, _model_id(task))
        if isinstance(outcome, Completed):
            if task.expected_output and not await self._has_ready(task.id, task.expected_output):
                error = TaskError(
                    code=ErrorCode.ARTIFACT_ERROR,
                    message=f"The task expected a {task.expected_output} file and none is ready.",
                )
                await self._finish(task, TaskStatus.FAILED, outcome.text, error, usage)
                return
            await self._finish(task, TaskStatus.COMPLETED, outcome.text, None, usage)
            return
        question = await self._tasks.ask(
            task_id,
            question=outcome.question,
            options=outcome.options,
            interrupt_id=outcome.interrupt_id,
            usage=usage,
        )
        logger.info(
            "task waiting for user",
            extra={"task_id": str(task_id), "question": preview(outcome.question)},
        )
        self._ask_timers[task_id] = self._supervisor.spawn(
            self._expire_question(task_id, question.id)
        )
        await self._notifier.ask(
            task,
            AskData(question_id=question.id, question=question.question, options=question.options),
        )

    async def _expire_question(self, task_id: UUID, question_id: UUID) -> None:
        await asyncio.sleep(self._limits.ask_timeout_s)
        self._ask_timers.pop(task_id, None)
        if not await self._tasks.expire_question(question_id):
            return  # answered in the meantime
        logger.info("question expired", extra={"task_id": str(task_id)})
        await self._fail(task_id, ErrorCode.TIMEOUT, "The question was not answered in time.")

    async def _fail(self, task_id: UUID, code: ErrorCode, message: str) -> None:
        task = await self._require(task_id)
        usage = _usage_dict(task.usage, Usage(), _model_id(task))
        await self._finish(
            task, TaskStatus.FAILED, None, TaskError(code=code, message=message), usage
        )

    async def _finish(
        self,
        task: TaskRecord,
        status: TaskStatus,
        result_text: str | None,
        error: TaskError | None,
        usage: dict[str, Any],
    ) -> None:
        finished = await self._tasks.finish(
            task.id,
            status=status,
            result_text=result_text,
            error=error.model_dump(mode="json") if error else None,
            usage=usage,
        )
        self._runtime.discard(task.id)
        self._worked_s.pop(task.id, None)
        self._cancel_ask_timer(task.id)
        logger.info(
            "task finished",
            extra={
                "task_id": str(task.id),
                "status": status.value,
                "error_code": error.code.value if error else None,
                "result": preview(result_text),
            },
        )
        try:
            artifacts = await self._ready_artifacts(task.id)
            await self._notifier.finish(
                finished,
                FinishData(
                    status=status,
                    result_text=result_text,
                    artifacts=artifacts,
                    error=error,
                    usage=TaskUsage.model_validate(usage),
                ),
            )
        finally:
            await self._advance(task.agent_id, task.id)

    async def _has_ready(self, task_id: UUID, artifact_type: str) -> bool:
        return any(a.type == artifact_type for a in await self._artifacts.ready_for_task(task_id))

    async def _ready_artifacts(self, task_id: UUID) -> list[ArtifactOut]:
        # A signing failure must not prevent the finish from being delivered.
        try:
            return await self._artifacts.ready_for_task(task_id)
        except Exception:
            logger.exception("could not sign task artifacts", extra={"task_id": str(task_id)})
            return []

    async def _advance(self, agent_id: UUID, finished_id: UUID) -> None:
        """Free the agent and start the next queued task, if any."""
        lane = self._lanes.setdefault(agent_id, _AgentLane())
        async with lane.lock:
            if lane.current != finished_id:
                return
            lane.current = lane.queue.popleft() if lane.queue else None
            next_id = lane.current
        if next_id is None:
            return
        task = await self._require(next_id)
        logger.info("starting queued task", extra={"task_id": str(next_id)})
        self.start(replace(task, status=TaskStatus.WORKING.value))

    def _cancel_ask_timer(self, task_id: UUID) -> None:
        timer = self._ask_timers.pop(task_id, None)
        if timer is not None and timer is not asyncio.current_task():
            timer.cancel()

    async def _require(self, task_id: UUID) -> TaskRecord:
        task = await self._tasks.get(self._workspace_id, task_id)
        if task is None:
            raise RuntimeError(f"Task {task_id} disappeared")
        return task

    async def recover(self) -> int:
        """Fail tasks left open by a previous process (their agents lived in memory)."""
        error = TaskError(
            code=ErrorCode.INTERNAL_ERROR, message="The backend restarted before finishing."
        )
        return await self._tasks.fail_open_tasks(self._workspace_id, error.model_dump(mode="json"))
