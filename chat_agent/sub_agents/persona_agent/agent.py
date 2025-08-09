from google.adk.agents import Agent

from .prompt import PERSONA_AGENT_PROMPT

MODEL = "gemini-2.5-flash"

persona_agent = Agent(
    model=MODEL,
    name="PersonaAgent",
    description="""
    A persona agent
    """,
    instruction=PERSONA_AGENT_PROMPT,
)