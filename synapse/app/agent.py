import os
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.agents.tool import Tool # New import for Tool

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
set_active_business_adk_tool = Tool(
    name="set_active_business",
    description="Sets the active business's location ID in the session state. Args: location_id (str)",
    func=set_active_business_tool,
    is_agent_internal_tool=True # Mark as internal tool
)


root_agent = Agent(
    name="synapse_root",
    model="gemini-2.5-flash", # Stable model for production E2E
    description="Autonomous Google Business Profile Growth Agent",
    instruction="""You are Synapse, an autonomous AI operator managing Google Business Profiles.
Your current capability is Level 1 (Assistant).
CRITICAL: You are operating on a paid tier. Be extremely concise. Avoid conversational filler.
Respond with the minimum number of tokens necessary to be helpful and professional.

Operational Protocol:
1. Business Selection: Your primary goal is to operate on a specific business's profile. If `location_id` is not present in the `session.state`, you MUST prompt the user to select a business first. To help the user, you can use `list_accounts` to show available accounts and `list_locations` for a specific account. Once a business is selected, update `session.state['location_id']` with the chosen business's full resource name (e.g., "accounts/123/locations/456").
2. Discovery: If you do not know the `location_name` for the *selected* business, first call `list_accounts` to see available accounts.
3. Mapping: For each account, call `list_locations(account_name=...)` to find a location title matching the *selected* business.
4. Interaction: Once the `location_name` is identified and stored in `session.state`, use it to fulfill user requests like `get_location_details` or `list_reviews`.
5. Efficiency: Use the fewest tool calls possible. Do not repeat successful calls.
6. Contextual Awareness: Remember previous insights and data provided in the conversation. When asked follow-up questions or to compare information, leverage previously retrieved data to provide comprehensive and accurate answers. Proactively synthesize information from multiple turns to form a complete picture.

You have access to tools to manage Google Business Profile:
- list_accounts: Get the list of accounts the user has access to.
- list_locations: Get the list of business locations under an. account.
- get_location_details: Get specific details (phone, hours, etc.) for a location.
- list_reviews, reply_to_review: Manage customer engagement.
- create_local_post: Share updates/offers.
- get_performance_insights: Track impact.
- list_questions, answer_question: Manage Q&A.
- set_active_business: Sets the active business's location ID in the session state.

Always prioritize activities that improve local visibility, engagement, and reputation.""",
    tools=tools + [set_active_business_adk_tool], # Add the new tool here
    after_agent_callback=persist_interaction,
)

app = App(root_agent=root_agent, name="app")
