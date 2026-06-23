import os
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.adk.apps import App

from app.app_utils.memory_manager import MemoryManager
from app.gbp_tools import tools

target_business = os.getenv("TARGET_BUSINESS_NAME", "Eritage ENT Care - Entebbe")
memory = MemoryManager()

from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

# ... existing code ...

async def persist_interaction(callback_context: CallbackContext) -> genai_types.Content | None:
    # Use callback_context to access state/events
    # 'request' and 'response' are typically in session history/events
    # For now, as a starting point for adaptation:
    events = callback_context.session.events
    if len(events) >= 2:
        last_request = events[-2]
        last_response = events[-1]
        
        location_id = callback_context.session.state.get("location_id", "default_location")
        memory.save_interaction(location_id, str(last_request.content), str(last_response.content))
    return None

root_agent = Agent(
    name="synapse_root",
    model="gemini-2.5-flash",
    description="Autonomous Google Business Profile Growth Agent",
    instruction=f"""You are Synapse, an autonomous AI operator managing the Google Business Profile for {target_business}.
Your current capability is Level 1 (Assistant).
Always respond professionally, concisely, and analyze requests strictly through the lens of GBP growth.

Operational Protocol:
1. Discovery: If you do not know the location_name for {target_business}, first call `list_accounts` to see available accounts.
2. Mapping: For each account, call `list_locations(account_name=...)` to find a location title matching "{target_business}".
3. Interaction: Once the `location_name` is identified, use it to fulfill user requests like `get_location_details` or `list_reviews`.
4. Persistence: If you successfully identify the location, mention it to the user so it can be verified.

You have access to tools to manage Google Business Profile:
- list_accounts: Get the list of accounts the user has access to.
- list_locations: Get the list of business locations under an account.
- get_location_details: Get specific details (phone, hours, etc.) for a location.
- list_reviews, reply_to_review: Manage customer engagement.
- create_local_post: Share updates/offers.
- get_performance_insights: Track impact.
- list_questions, answer_question: Manage Q&A.

Always prioritize activities that improve local visibility, engagement, and reputation.""",
    tools=tools,
    after_agent_callback=persist_interaction,
)

app = App(root_agent=root_agent, name="app")

