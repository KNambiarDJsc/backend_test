from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from google.adk.sessions.state import State
from typing import Dict, Any
import os
import json

SAMPLE_STATE_PATH = os.getenv(
    "SAMPLE_STATE_PATH",
    "chat/profiles/user_empty_default.json"
)

def create_risk_profile(
        triggering_statement: str, 
        risk_category: str, 
        tool_context: ToolContext
    ) -> Dict[str, Any]:
    
    """
    Creates a risk profile for the user if the user's query
    contains any statements that fall under the risk categories
    
    Args:
        triggering_statement: The statement that triggered the risk profile
        risk_category: The risk category that the statement falls under
        tool_context: The tool context
        
    Returns:
        A dictionary containing the status of the operation and the risk profile
    """
    
    try:
        memory = tool_context.state
        
        risk_profile = memory["risk_profile"]
        
        if not risk_profile:
            risk_profile = {
                "triggering_statement": "",
                "risk_categories": [],
                "assessment_history": [],
                "verdict": "CLEARED"
            }
        
        risk_profile["triggering_statement"] = triggering_statement
        risk_profile["risk_categories"].append(risk_category)
        risk_profile["verdict"] = "UNCONFIRMED"

        memory["at_risk"] = "True"
        memory["risk_profile"] = risk_profile
        
        ret = {
            "status": "SUCCESS",
            "risk_profile": tool_context.state["risk_profile"]
        }
    except Exception as e:
        ret = {
            "status": "ERROR",
            "error": str(e)
        }
        
    return ret

def update_recent_memory_queue(callback_context: CallbackContext):
    """
    Updates the recent memory queue in the session state.
    Stores the latest user input and persona agent response.
    Maintains a maximum queue length of 3 conversation turns.

    Args:
        callback_context: The callback context
    """
    memory = callback_context.state
    
    # Initialize recent_memory_queue if it doesn't exist
    if "recent_memory_queue" not in memory:
        memory["recent_memory_queue"] = []
    
    recent_memory_queue = memory["recent_memory_queue"]
    
    # Add new entries to the queue
    new_entries = [
        {
            "role": callback_context.user_content.role,
            "text": callback_context.user_content.parts[0].text
        },
        {
            "role": "model",
            "text": memory["persona_agent_response"]
        }
    ]
    
    # Add new entries to the queue
    recent_memory_queue.extend(new_entries)
    
    # Limit the queue to the 3 most recent turns (6 entries)
    # Each turn consists of a user message and a model response
    if len(recent_memory_queue) > 6:
        recent_memory_queue = recent_memory_queue[-6:]
    
    # Update the memory with the new queue
    memory["recent_memory_queue"] = recent_memory_queue

def _update_assessment_history(callback_context: CallbackContext):
    """
    Updates the assessment history in the memory

    Args:
        callback_context: The callback context
    """
    memory = callback_context.state
    risk_profile = memory["risk_profile"]
    assessment_history = risk_profile["assessment_history"]
    new_assessment_history = assessment_history + [
        {
            "role": callback_context.user_content.role,
            "text": callback_context.user_content.parts[0].text
        },
        {
            "role": "model",
            "text": callback_context.state["agent_response"]
        }
    ]
    
    risk_profile = { 
            **risk_profile, 
            "assessment_history": new_assessment_history
        }
    
    memory["risk_profile"] = risk_profile
    
def _set_initial_states(source: Dict[str, Any], target: State | dict[str, Any]):
    """
    Setting the initial session state given the JSON object of states
    
    Args:
        source: A JSON object of states
        target: The session state object to insert into
    """
    
    target.update(source)
    
def _load_sample_state(callback_context: CallbackContext):
    """
    Sets up the initial state.
    Set this as a callback as before_agent_call of the root_agent.
    This gets called before the system instruction is constructed
    
    Args:
        callback_context: the callback context
    """
    
    if callback_context.state.get("user_profile"):
        return
    
    data = {}
    with open(SAMPLE_STATE_PATH, "r") as f:
        data = json.load(f)
        print(f"\nLoading Initial State: {data}\n")
    
    _set_initial_states(data["state"], callback_context.state)