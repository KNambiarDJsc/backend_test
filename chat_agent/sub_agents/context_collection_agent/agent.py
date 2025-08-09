from google.adk.agents import Agent
from ...tools.memory import _update_assessment_history
from .prompt import CONTEXT_COLLECTION_AGENT_PROMPT

MODEL = "gemini-2.5-flash"

context_collection_agent = Agent(
    model=MODEL,
    name="ContextCollectionAgent",
    description="""
    A context collection agent
    """,
    instruction=CONTEXT_COLLECTION_AGENT_PROMPT,
    output_key="agent_response",
    # before_agent_callback=_update_assessment_history_user,
    after_agent_callback=_update_assessment_history,
)