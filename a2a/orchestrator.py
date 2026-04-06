from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from agents import Agent, Runner
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from a2a_registry import A2AAgentSpec, A2ARegistry
from tools_a2a import (
    OrchestratorContext,
    ask_current_data_agent,
    ask_model1_agent,
    ask_model2_agent,
)

ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "gpt-5.4")
CURRENT_DATA_A2A_URL = os.getenv("CURRENT_DATA_A2A_URL", "http://127.0.0.1:9101")
MODEL1_A2A_URL = os.getenv("MODEL1_A2A_URL", "http://127.0.0.1:9102")
MODEL2_A2A_URL = os.getenv("MODEL2_A2A_URL", "http://127.0.0.1:9103")


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    last_agent: Optional[str] = None
    history_items: int = 0


class HealthResponse(BaseModel):
    ok: bool
    agents: list[dict[str, str]]


# You can swap this for Redis, a database, or the Responses API conversation_id.
conversation_store: dict[str, list[dict[str, Any]]] = {}


orchestrator_agent = Agent[OrchestratorContext](
    name="A2A Orchestrator",
    model=ORCHESTRATOR_MODEL,
    instructions=(
        "You are the front-door agent that receives the user's question and routes it to the right remote specialist. "
        "Use ask_current_data_agent for Excel/CSV questions about the active data file. "
        "Use ask_model1_agent only for requests that belong to model1's specialty. "
        "Use ask_model2_agent only for requests that belong to model2's specialty. "
        "You may call more than one remote agent if the user's question needs combined reasoning. "
        "Do not invent facts from remote agents. Base factual claims on tool results."
    ),
    tools=[
        ask_current_data_agent,
        ask_model1_agent,
        ask_model2_agent,
    ],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = A2ARegistry()
    specs = [
        A2AAgentSpec(
            name="current_data",
            base_url=CURRENT_DATA_A2A_URL,
            description="Spreadsheet agent for the current Excel/CSV file.",
        ),
        A2AAgentSpec(
            name="model1",
            base_url=MODEL1_A2A_URL,
            description="Specialist A2A agent for model1.",
        ),
        A2AAgentSpec(
            name="model2",
            base_url=MODEL2_A2A_URL,
            description="Specialist A2A agent for model2.",
        ),
    ]

    # In production you may want to make model1/model2 optional.
    for spec in specs:
        try:
            await registry.register(spec)
        except Exception:
            # Keep startup resilient. The /health endpoint will show which agents registered.
            pass

    app.state.registry = registry
    yield
    await registry.close()


app = FastAPI(title="OpenAI Orchestrator over A2A", lifespan=lifespan)


async def run_orchestrator(
    user_message: str,
    *,
    registry: A2ARegistry,
    conversation_id: Optional[str] = None,
) -> dict[str, Any]:
    previous_items = conversation_store.get(conversation_id, []) if conversation_id else []
    if previous_items:
        agent_input: Any = previous_items + [{"role": "user", "content": user_message}]
    else:
        agent_input = user_message

    result = await Runner.run(
        orchestrator_agent,
        input=agent_input,
        context=OrchestratorContext(registry=registry),
    )

    if conversation_id:
        conversation_store[conversation_id] = result.to_input_list()

    return {
        "answer": result.final_output,
        "last_agent": result.last_agent.name if result.last_agent else None,
        "history_items": len(conversation_store.get(conversation_id, [])) if conversation_id else 0,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Missing 'message'")

    try:
        result = await run_orchestrator(
            body.message,
            registry=app.state.registry,
            conversation_id=body.conversation_id,
        )
        return ChatResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health", response_model=HealthResponse)
async def health():
    registry: A2ARegistry = app.state.registry
    return HealthResponse(ok=True, agents=registry.list_agents())
