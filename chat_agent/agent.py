# from google.adk.agents import Agent

# from chat_agent.prompt import ROOT_AGENT_PROMPT

# from chat_agent.sub_agents.persona_agent import persona_agent

# from chat_agent.tools.memory import _load_sample_state

# MODEL = "gemini-2.5-flash"

# root_agent = Agent(
#     model=MODEL,
#     name="ChatAgent",
#     description="""
#     A mental health chatbot
#     """,
#     instruction=ROOT_AGENT_PROMPT,
#     sub_agents=[
#         persona_agent
#     ],
#     before_agent_callback=_load_sample_state,
# )
import logging

from google.adk.agents import Agent, LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event 

from typing_extensions import override
from typing import AsyncGenerator, Optional

from .sub_agents.persona_agent.agent import persona_agent
from .sub_agents.crisis_detection_agent.agent import crisis_detection_agent
from .sub_agents.context_collection_agent.agent import context_collection_agent
from .tools.memory import _load_sample_state

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RootAgent(BaseAgent):
    """
    The main controller. For each query, it first runs the crisis detector to
    update the state, then reads the state to route the conversation to the
    correct sub-agent.
    """
    persona: LlmAgent
    crisis_detection: LlmAgent
    context_collection: LlmAgent
    
    def __init__(
        self,
        name: str,
        persona: LlmAgent,
        crisis_detection: LlmAgent,
        context_collection: LlmAgent,
    ):
        super().__init__(
            name=name,
            persona=persona,
            crisis_detection=crisis_detection,
            context_collection=context_collection,
            before_agent_callback=_load_sample_state,
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Overrides the default execution to directly delegate to the persona_agent,
        passing the original context.
        """
        logger.info(f"\nMemory before turn: {ctx.session.state}")

        string_to_bool = {
            "True": True,
            "False": False,
        }
        
        is_at_risk = string_to_bool[ctx.session.state.get("at_risk")]
        
        if not is_at_risk:
            logger.info(f"\n--- [{self.name}]: Analyzing User Query ---")
            # TODO: Don't show events on chat UI
            async for event in self.crisis_detection.run_async(ctx):
                yield event

        logger.info(f"\n--- [{self.name}]: Routing to {"Context Collection Agent" if is_at_risk else "Persona Agent"} ---")
        is_at_risk = string_to_bool[ctx.session.state.get("at_risk")]
        
        if is_at_risk:
            async for event in self.context_collection.run_async(ctx):
                yield event
        else:
            async for event in self.persona.run_async(ctx):
                yield event
        
        logger.info(f"\nMemory after turn: {ctx.session.state}")

root_agent = RootAgent(
    name="RootAgent",
    persona=persona_agent,
    crisis_detection=crisis_detection_agent,
    context_collection=context_collection_agent,
)
