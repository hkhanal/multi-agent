# demo.py
from agent import Agent, AgentGraph
import datetime, json
from helper import safe_json_merge

clarifier = Agent(
    name="clarifier",
    llm_system_prompt="You are a helpful assistant who extracts key mission parameters "
                      "from the user's free-text into JSON {objective, location, deadline}.",
    fn_after_llm=safe_json_merge
)

planner = Agent(
    name="planner",
    llm_system_prompt="You are an operations planner. Given JSON {objective, location, deadline}, "
                      "produce bullet-point steps labeled 'plan'.",
)

summarizer = Agent(
    name="summary",
    llm_system_prompt="Summarize the mission plan in <100 words."
)

g = AgentGraph(start="clarifier")
for ag in (clarifier, planner, summarizer):
    g.add_agent(ag)

g.add_edge("clarifier", "planner")
g.add_edge("planner", "summary")

state0 = {
    "user_input": "Set up a temporary med-evac site near Springfield by tomorrow evening.",
    "history": []
}

final_state = g.run(state0)

# save graph
with open("graph.dot", "w") as f:
    f.write(g.to_dot())
print("\n=== Conversation ===")
for turn in final_state["history"]:
    print(f"{turn['agent']}: {turn['msg']}\n")
