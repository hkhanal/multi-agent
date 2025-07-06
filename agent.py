# agents_graph.py
from __future__ import annotations
import uuid, json
from typing import Callable, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from openai import OpenAI

client = OpenAI()  

@dataclass
class Agent:
    name: str
    llm_system_prompt: str
    fn_after_llm: Callable[[str, Dict[str, Any]], Dict[str, Any]] = lambda r, s: s

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the LLM turn then optional post-processing."""
        user_input = state.get("user_input", "")
        messages = [
            {"role": "system", "content": self.llm_system_prompt},
            {"role": "user", "content": user_input},
        ]
        completion = client.chat.completions.create(model="gpt-4o",
        messages=messages,
        temperature=0.2)
        response = completion.choices[0].message.content.strip()
        state["history"].append({"agent": self.name, "msg": response})
        return self.fn_after_llm(response, state)

Edge = Tuple[str, str, Callable[[Dict[str, Any]], bool]]  # (src, dst, predicate)

@dataclass
class AgentGraph:
    agents: Dict[str, Agent] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    start: str = ""

    def add_agent(self, agent: Agent) -> None:
        self.agents[agent.name] = agent

    def add_edge(self, src: str, dst: str,
                 predicate: Callable[[Dict[str, Any]], bool] = lambda s: True) -> None:
        self.edges.append((src, dst, predicate))

    # -------- runner --------
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        state = initial_state
        current = self.start
        visited = set()
        while current:
            if current in visited:          # avoid loops unless you want them
                break
            visited.add(current)
            state = self.agents[current](state)
            # find first outbound edge whose predicate is true
            next_nodes = [
                dst for src, dst, pred in self.edges
                if src == current and pred(state)
            ]
            current = next_nodes[0] if next_nodes else None
        return state

    # -------- visualization --------
    def to_dot(self) -> str:
        lines = ["digraph G {"]
        for name in self.agents:
            lines.append(f'  "{name}" [shape=box, style=rounded];')
        for src, dst, _ in self.edges:
            lines.append(f'  "{src}" -> "{dst}";')
        lines.append("}")
        return "\n".join(lines)
