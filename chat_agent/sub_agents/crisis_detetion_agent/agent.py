from google.adk.agents import Agent
from ...tools.memory import create_risk_profile
from .prompt import CRISIS_DETECTION_AGENT_PROMPT
from google.adk.planners import BuiltInPlanner
from google.genai import types

MODEL = "gemini-2.5-flash"

crisis_detection_agent = Agent(
    model=MODEL,
    name="CrisisDetectionAgent",
    description="""
    A crisis detection agent
    """,
    tools=[
        create_risk_profile
    ],
    # output_key="at_risk",
    instruction=CRISIS_DETECTION_AGENT_PROMPT,
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False, thinking_budget=0
        )
    )
)