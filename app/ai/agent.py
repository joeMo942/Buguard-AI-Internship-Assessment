from langgraph.prebuilt import create_react_agent
from app.ai.llm import get_llm
from app.ai.tools import create_tools

AGENT_SYSTEM_PROMPT = """You are a cybersecurity asset management assistant.
You have access to tools that query a real asset database. 
Use them to answer the user's question.

RULES:
- ONLY reference assets returned by your tools. Never invent data.
- If a tool returns no results, say so honestly.
- Always cite specific asset IDs and values from tool output.
"""

async def run_agent(db, user_input: str, org_id: str = "default") -> str:
    tools = create_tools(db, org_id=org_id)
    llm = get_llm(temperature=0.0)
    
    agent = create_react_agent(llm, tools, state_modifier=AGENT_SYSTEM_PROMPT)
    
    result = await agent.ainvoke({"messages": [("user", user_input)]})
    return result["messages"][-1].content
