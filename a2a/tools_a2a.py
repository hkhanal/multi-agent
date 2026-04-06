from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents import RunContextWrapper, function_tool
from a2a.client import create_text_message_object
from a2a.types import Message, MessageSendConfiguration, Role
from a2a.utils import get_artifact_text, get_message_text

from a2a_registry import A2ARegistry


@dataclass
class OrchestratorContext:
    """Local runtime context passed into the OpenAI orchestrator."""

    registry: A2ARegistry


def _extract_text_from_task(task: Any) -> str:
    """Best-effort extraction of text from a Task returned by the A2A client."""
    artifacts = getattr(task, "artifacts", None) or []
    artifact_texts = [get_artifact_text(artifact).strip() for artifact in artifacts]
    artifact_texts = [text for text in artifact_texts if text]
    if artifact_texts:
        return "\n\n".join(artifact_texts)

    status = getattr(task, "status", None)
    status_message = getattr(status, "message", None) if status else None
    if status_message is not None:
        status_text = get_message_text(status_message).strip()
        if status_text:
            return status_text

    history = getattr(task, "history", None) or []
    message_texts: list[str] = []
    for message in history:
        text = get_message_text(message).strip()
        if text:
            message_texts.append(text)
    if message_texts:
        return "\n\n".join(message_texts[-2:])

    return ""


async def _ask_remote_agent(
    registry: A2ARegistry,
    *,
    agent_name: str,
    question: str,
) -> str:
    """Send one question to one remote A2A agent and return plain text."""
    remote = registry.get(agent_name)

    request_message: Message = create_text_message_object(
        role=Role.user,
        content=question,
    )

    # blocking=True asks the server for a completed task when possible.
    config = MessageSendConfiguration(
        blocking=True,
        history_length=8,
    )

    latest_task = None
    latest_message = None

    async for event in remote.client.send_message(
        request_message,
        configuration=config,
    ):
        if isinstance(event, tuple):
            latest_task, _update = event
        else:
            latest_message = event

    if latest_task is not None:
        text = _extract_text_from_task(latest_task).strip()
        if text:
            return text

    if latest_message is not None:
        text = get_message_text(latest_message).strip()
        if text:
            return text

    raise RuntimeError(f"Remote agent '{agent_name}' returned no readable text.")


@function_tool
async def ask_current_data_agent(
    context: RunContextWrapper[OrchestratorContext],
    question: str,
) -> str:
    """Ask the current-data A2A agent about the active Excel or CSV dataset.

    Use this for factual spreadsheet questions, grouping, sorting, filtering,
    totals, counts, or top-N queries.
    """
    return await _ask_remote_agent(
        context.context.registry,
        agent_name="current_data",
        question=question,
    )


@function_tool
async def ask_model1_agent(
    context: RunContextWrapper[OrchestratorContext],
    question: str,
) -> str:
    """Ask the model1 A2A agent.

    Use this only when the user request clearly matches the specialty of model1.
    """
    return await _ask_remote_agent(
        context.context.registry,
        agent_name="model1",
        question=question,
    )


@function_tool
async def ask_model2_agent(
    context: RunContextWrapper[OrchestratorContext],
    question: str,
) -> str:
    """Ask the model2 A2A agent.

    Use this only when the user request clearly matches the specialty of model2.
    """
    return await _ask_remote_agent(
        context.context.registry,
        agent_name="model2",
        question=question,
    )
