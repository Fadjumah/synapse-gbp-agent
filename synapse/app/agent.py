import os

from google.adk.agents.llm_agent import Agent
from google.adk.apps import App

from app.app_utils.memory_manager import MemoryManager
from app.gbp_tools import tools

target_business = os.getenv("TARGET_BUSINESS_NAME", "Eritage ENT Care - Entebbe")
memory = MemoryManager()

root_agent = Agent(
    name="synapse_root",
    model="gemini-3.5-flash",
    description="Autonomous Google Business Profile Growth Agent",
    instruction=f"""You are Synapse, an autonomous AI operator managing the Google Business Profile for {target_business}.
Your current capability is Level 1 (Assistant).
Always respond professionally, concisely, and analyze requests strictly through the lens of GBP growth.

You have access to tools to manage Google Business Profile:
1. Use list_accounts and list_locations to find the business location if not known.
2. Use list_reviews to see what customers are saying.
3. Use reply_to_review to engage with customers.
4. Use create_local_post to share updates, offers, and events.
5. Use get_performance_insights to track growth and impact.
6. Use get_location_details to retrieve and verify current business information like hours and phone number.
7. Use update_location_data to correct or update business details.
8. Use list_questions and answer_question to manage the Q&A section.
9. You can also manage posts and review replies by listing, deleting, or updating them.

Always prioritize activities that improve local visibility, engagement, and reputation.""",
    tools=[tool.run for tool in tools],
)

def persist_interaction(request: Any, response: Any):
    # This assumes a context exists where 'location_id' is available,
    # often passed in the request metadata in ADK applications.
    location_id = request.metadata.get("location_id", "default_location")
    memory.save_interaction(location_id, request.text, response.text)

root_agent.register_response_callback(persist_interaction)

app = App(root_agent=root_agent, name="app")
