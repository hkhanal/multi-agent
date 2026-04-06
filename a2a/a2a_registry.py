from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory


@dataclass(frozen=True)
class A2AAgentSpec:
    """Configuration for one remote A2A agent."""

    name: str
    base_url: str
    description: str


@dataclass
class RegisteredA2AAgent:
    """Resolved remote agent information.

    `client` is the reusable A2A client created from the remote Agent Card.
    `card` is the fetched Agent Card metadata.
    """

    name: str
    base_url: str
    description: str
    card: object
    client: object


class A2ARegistry:
    """Resolve Agent Cards once and keep reusable clients for the orchestrator.

    Why this layer exists:
    - The OpenAI agent should not see raw A2A URLs.
    - Your Python app should discover agents, build clients, and expose a small,
      meaningful tool surface to the LLM.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 60.0,
        streaming: bool = True,
        polling: bool = False,
    ) -> None:
        self._httpx_client = httpx.AsyncClient(timeout=timeout_seconds)
        self._factory = ClientFactory(
            ClientConfig(
                streaming=streaming,
                polling=polling,
                httpx_client=self._httpx_client,
            )
        )
        self._agents: Dict[str, RegisteredA2AAgent] = {}

    async def register(self, spec: A2AAgentSpec) -> RegisteredA2AAgent:
        """Fetch the remote Agent Card and build a reusable client."""
        resolver = A2ACardResolver(
            httpx_client=self._httpx_client,
            base_url=spec.base_url,
        )
        card = await resolver.get_agent_card()
        client = self._factory.create(card)

        entry = RegisteredA2AAgent(
            name=spec.name,
            base_url=spec.base_url,
            description=spec.description,
            card=card,
            client=client,
        )
        self._agents[spec.name] = entry
        return entry

    async def register_many(self, specs: Iterable[A2AAgentSpec]) -> None:
        for spec in specs:
            await self.register(spec)

    def get(self, name: str) -> RegisteredA2AAgent:
        try:
            return self._agents[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._agents)) or "<none>"
            raise KeyError(f"Unknown A2A agent '{name}'. Known agents: {known}") from exc

    def list_agents(self) -> list[dict[str, str]]:
        return [
            {
                "name": entry.name,
                "base_url": entry.base_url,
                "description": entry.description,
            }
            for entry in sorted(self._agents.values(), key=lambda x: x.name)
        ]

    def has(self, name: str) -> bool:
        return name in self._agents

    async def close(self) -> None:
        # Close the shared transport used by all A2A clients.
        await self._httpx_client.aclose()


async def build_default_registry(
    current_data_url: str,
    model1_url: Optional[str] = None,
    model2_url: Optional[str] = None,
) -> A2ARegistry:
    """Helper for the common 3-agent setup discussed in the flow diagram."""
    registry = A2ARegistry()

    specs = [
        A2AAgentSpec(
            name="current_data",
            base_url=current_data_url,
            description="Answers factual questions from the current Excel/CSV dataset.",
        ),
    ]

    if model1_url:
        specs.append(
            A2AAgentSpec(
                name="model1",
                base_url=model1_url,
                description="Specialist remote agent for model1 analysis.",
            )
        )

    if model2_url:
        specs.append(
            A2AAgentSpec(
                name="model2",
                base_url=model2_url,
                description="Specialist remote agent for model2 analysis.",
            )
        )

    await registry.register_many(specs)
    return registry
