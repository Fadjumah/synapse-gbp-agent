import os
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.tools import FunctionTool
from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

from app.app_utils.memory_manager import MemoryManager
from app.gbp_tools import tools, gbp_tools_instance
from app.retrievers import create_search_tool

memory = MemoryManager()

# RAG Configuration
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
data_store_region = os.getenv("DATA_STORE_REGION", "global")
data_store_id = os.getenv("DATA_STORE_ID")
data_store_path = (
    f"projects/{project_id}/locations/{data_store_region}"
    f"/collections/default_collection/dataStores/{data_store_id}"
)

# Initialize Search Tool if ID is provided
search_tool = []
if data_store_id:
    search_tool = [create_search_tool(data_store_path)]

async def persist_interaction(callback_context: CallbackContext) -> genai_types.Content | None:
    events = callback_context.session.events
    if len(events) >= 2:
        last_request = events[-2]
        last_response = events[-1]
        
        user_id = callback_context.session.user_id or "default_user"
        memory.save_interaction(user_id, str(last_request.content), str(last_response.content))
    return None

# New internal tool to set active business in session state
async def set_active_business_tool(location_id: str, callback_context: CallbackContext) -> str:
    """Sets the active business's location ID in the session state for multi-tenant support."""
    callback_context.session.state['location_id'] = location_id
    return f"Active business set to location_id: {location_id}"

# Interactive tool to remind agent to ask for media
async def create_local_post_with_media_help(location_name: str, summary: str) -> str:
    """Guidelines for creating a local post with media."""
    return "To include an image, please ask the user for a publicly accessible image URL (JPEG/PNG), then call 'create_local_post' with that URL in the 'media_url' parameter."

set_active_business_adk_tool = FunctionTool(set_active_business_tool)
media_help_tool = FunctionTool(create_local_post_with_media_help)

root_agent = Agent(
    name="synapse_root",
    model="gemini-3.1-pro", 
    description="Autonomous Google Business Profile Growth Agent",
    instruction="""You are Synapse, an autonomous AI operator managing Google Business Profiles.
    Your current capability is Level 1 (Assistant).
    CRITICAL: You are operating on a paid tier. Be concise and professional, but ensure you are helpful and guide the user when information is missing.

    Temporal Awareness:
    - Always refer to the 'Current Date' provided in the system context to determine 'today', 'this month', or 'last week'.
    - Performance queries for 'today' should generally look at the last 7 or 30 days including today, as same-day metrics might be incomplete in Google Business Profile.

    Operational Protocol:
    1. Business Selection: Ensure `location_id` is present in `session.state` before proceeding with business-specific tools. If missing, check the 'Previous Conversation' for a recently used business and use `set_active_business` to restore it. If you cannot find a business, ask the user to select one after calling `list_accounts` and `list_locations`.
    2. Performance Insights: When asked how the business is doing, use `get_performance_insights`. Always default to the last 30 days unless specified otherwise.
    3. Response Style: Synthesize tool output into 3-5 concise, actionable bullet points focusing on trends (e.g., "Visibility is up 15%") and business impact. Avoid dumping raw numbers.
    4. Tool Usage: Use the fewest tool calls possible. Synthesize info from multiple turns.

    You have access to tools for Google Business Profile management:
    - list_accounts, list_locations, get_location_details
    - list_reviews, reply_to_review
    - create_local_post: Can take an optional `media_url` for images.
    - create_local_post_with_media_help: Use this to get instructions on how to handle image posts.
    - get_performance_insights
    - set_active_business
    - RAG Tools: Use available search tools for grounding answers in provided documentation.

    Always prioritize activities that improve local visibility, engagement, and reputation.""",
    tools=tools + [set_active_business_adk_tool, media_help_tool] + search_tool,
    after_agent_callback=persist_interaction,
)

app = App(root_agent=root_agent, name="app")
