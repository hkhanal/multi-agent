"""
main.py  –  a tiny LangGraph multi-agent demo
"""
from __future__ import annotations
import uuid
from typing import Literal, NotRequired, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.types import Command
from langgraph.graph import StateGraph, START, END          # other bits stay here

# ---------------------------------------------------------------------
# 1. Define the mutable chat state ------------------------------------
# ---------------------------------------------------------------------

class ChatState(TypedDict):
    messages: list[dict]            # running chat history
    notes: NotRequired[str]         # scratch-pad for the Researcher

# ---------------------------------------------------------------------
# 2. Set up your LLM ---------------------------------------------------

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.0,
    streaming=False      # flip to True if you want tokens as they arrive
)

# ---------------------------------------------------------------------
# 3. Implement the two specialist agents ------------------------------
# ---------------------------------------------------------------------

def researcher(state: ChatState) -> Command[Literal["writer"]]:
    """
    Gathers 3 bullet-point facts that will help the Writer craft an answer.
    """
    user_q = state["messages"][-1]["content"]
    prompt = (
        "You are a domain researcher. Provide exactly three concise facts "
        "the writer can use when answering the user's question:\n\n"
        f"Question: {user_q}"
    )
    facts = llm.invoke(prompt).content
    return Command(
        goto="writer",                 # hand off to the Writer node
        update={"notes": facts}        # attach facts to chat state
    )

def writer(state: ChatState) -> Command[Literal["end"]]:
    """
    Turns facts from the Researcher into a friendly answer for the user.
    """
    user_q = state["messages"][-1]["content"]
    facts  = state["notes"]
    prompt = (
        "You are a helpful educator. Use the bullet-point facts below to "
        "answer the user's question in ≤ 150 words.\n\n"
        f"Question: {user_q}\n\nFacts:\n{facts}"
    )
    answer = llm.invoke(prompt).content
    new_history = state["messages"] + [
        {"role": "assistant", "content": answer}
    ]
    return Command(
        goto=END,                      # finish the workflow
        update={"messages": new_history}
    )

# ---------------------------------------------------------------------
# 4. Build and compile the graph --------------------------------------
# ---------------------------------------------------------------------

builder = StateGraph(ChatState)

builder.add_node("researcher", researcher)
builder.add_node("writer",      writer)

builder.set_entry_point("researcher")       # where START routes first
builder.add_edge("researcher", "writer")
builder.add_edge("writer", END)

graph = builder.compile()                   # ready to run!

# ---------------------------------------------------------------------
# 5. Invoke the multi-agent workflow ----------------------------------
# ---------------------------------------------------------------------

if __name__ == "__main__":
    init_state = {
        "messages": [
            {"role": "user",
             "content": "Explain photosynthesis in simple terms."}
        ]
    }
    result = graph.invoke(
        init_state,
        # thread_id makes the run resumable/persistent if you add a checkpointer
        config={"configurable": {"thread_id": uuid.uuid4()}}
    )
    print("\n=== Assistant reply ===\n")
    print(result["messages"][-1]["content"])
    print("\n=== Chat history ===\n")