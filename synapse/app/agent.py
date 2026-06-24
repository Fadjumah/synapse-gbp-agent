import os
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.tools import FunctionTool

from app.app_utils.memory_manager import MemoryManager
from app.gbp_tools import tools

memory = MemoryManager()

from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

async def persist_interaction(callback_context: CallbackContext) -> genai_types.Content | None:
    events = callback_context.session.events
    if len(events) >= 2:
        last_request = events[-2]
        last_response = events[-1]
        
        location_id = callback_context.session.state.get("location_id", "default_location")
        memory.save_interaction(location_id, str(last_request.content), str(last_response.content))
    return None

# New internal tool to set active business in session state
async def set_active_business_tool(location_id: str, callback_context: CallbackContext) -> str:
    """Sets the active business's location ID in the session state for multi-tenant support."""
    callback_context.session.state['location_id'] = location_id
    return f"Active business set to location_id: {location_id}"

# Create a Tool instance for set_active_business_tool
set_active_business_adk_tool = FunctionTool(
    set_active_business_tool,
)


root_agent = Agent(
    name="synapse_root",
    model="gemini-2.5-flash", # Stable model for production E2E
    description="Autonomous Google Business Profile Growth Agent",
    instruction="""You are Synapse, an autonomous AI operator managing Google Business Profiles.
Your current capability is Level 1 (Assistant).
CRITICAL: You are operating on a paid tier. Be extremely concise. Avoid conversational filler.

Operational Protocol:
1. Business Selection: Ensure `location_id` is present in `session.state` before proceeding. If not, prompt the user to select a business using `list_accounts` and `list_locations`.
2. Response Style: NEVER dump raw data or long lists. Synthesize all tool output into 3-5 concise, actionable bullet points. Focus on trends, anomalies, and business impact rather than daily data points.
3. Tool Usage: Use the fewest tool calls possible. Synthesize information from multiple turns.
4. Contextual Awareness: Proactively synthesize data to provide comprehensive insights.

You have access to tools for Google Business Profile management:
- list_accounts, list_locations, get_location_details
- list_reviews, reply_to_review
- create_local_post
- get_performance_insights
- list_questions, answer_question
- set_active_business

Always prioritize activities that improve local visibility, engagement, and reputation.""",
    tools=tools + [set_active_business_adk_tool], # Add the new tool here
    after_agent_callback=persist_interaction,
)

app = App(root_agent=root_agent, name="app")
