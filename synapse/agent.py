from google.adk import Agent
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part

synapse_root = Agent(
    name="synapse_root",
    model="gemini-3.5-flash",
    description="Autonomous Google Business Profile Growth Agent",
    instruction="You are Synapse, an autonomous AI operator managing the Google Business Profile for Eritage ENT Care - Entebbe. Your current capability is Level 1 (Assistant). Always respond professionally, concisely, and analyze requests strictly through the lens of GBP growth."
)

runner = InMemoryRunner(synapse_root)

async def process_user_message(user_id: str, message: str) -> str:
    try:
        session_id = f"session_{user_id}"
        
        # Create input content
        content = Content(role="user", parts=[Part.from_text(text=message)])
        
        response_text = ""
        
        # Iterate through the event stream from the runner
        async for event in runner.run_async(session_id=session_id, input=content):
            # ADK event handling to extract text
            if hasattr(event, "text"):
                response_text += event.text
            elif hasattr(event, "content"):
                response_text += event.content
        
        return response_text if response_text else "I am sorry, I couldn't generate a response."
    except Exception as e:
        return f"Error processing message: {str(e)}"
