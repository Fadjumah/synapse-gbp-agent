from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

synapse_root = Agent(
    name="synapse_root",
    model="gemini-3.1-pro",
    description="Autonomous Google Business Profile Growth Agent",
    instruction="You are Synapse, an autonomous AI operator managing the Google Business Profile for Eritage ENT Care - Entebbe. Your current capability is Level 1 (Assistant). Always respond professionally, concisely, and analyze requests strictly through the lens of GBP growth."
)

session_service = InMemorySessionService()
runner = Runner(agent=synapse_root, app_name="app", session_service=session_service)

async def process_user_message(user_id: str, message: str) -> str:
    try:
        session_id = f"session_{user_id}"
        await session_service.create_session(app_name="app", user_id=user_id, session_id=session_id)

        # Create input content
        content = Content(role="user", parts=[Part.from_text(text=message)])

        response_text = ""

        # Iterate through the event stream from the runner
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            # ADK event handling to extract text
            if event.is_final_response():
                if event.content and event.content.parts:
                    response_text += event.content.parts[0].text

        return response_text if response_text else "I am sorry, I couldn't generate a response."
    except Exception as e:
        return f"Error processing message: {e!s}"
