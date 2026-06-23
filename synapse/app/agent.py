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

async def persist_interaction(callback_context: CallbackContext) -> genai_types.Content | None:
    events = callback_context.session.events
    if len(events) >= 2:
        last_request = events[-2]
        last_response = events[-1]
        
        location_id = callback_context.session.state.get("location_id", "default_location")
        memory.save_interaction(location_id, str(last_request.content), str(last_response.content))
    return None

root_agent = Agent(
    name="synapse_root",
    model="gemini-2.5-flash", # Stable model for production E2E
    description="Autonomous Google Business Profile Growth Agent",
    instruction=f"""You are Synapse, an autonomous AI operator managing the Google Business Profile for {target_business}.
Your current capability is Level 1 (Assistant).
CRITICAL: You are operating on a paid tier. Be extremely concise. Avoid conversational filler.
Respond with the minimum number of tokens necessary to be helpful and professional.

Operational Protocol:
1. Discovery: If you do not know the location_name for {target_business}, first call `list_accounts` to see available accounts.
2. Mapping: For each account, call `list_locations(account_name=...)` to find a location title matching "{target_business}".
3. Interaction: Once the `location_name` is identified, use it to fulfill user requests like `get_location_details` or `list_reviews`.
4. Efficiency: Use the fewest tool calls possible. Do not repeat successful calls.

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
