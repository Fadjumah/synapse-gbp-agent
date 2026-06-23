import asyncio
import os
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent
from dotenv import load_dotenv

load_dotenv(override=True)

# Diagnostic print to verify correct credentials (masking for security)
def mask(s): return f"...{s[-4:]}" if s else "None"
print(f"DEBUG: Using Client ID {mask(os.getenv('GBP_CLIENT_ID'))}")
print(f"DEBUG: Using Refresh Token {mask(os.getenv('GOOGLE_REFRESH_TOKEN'))}")

async def interrogate(runner, user_id, session_id, query):
    print(f"\n--- Query: {query} ---")
    response_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text
            print(f"Agent: {response_text}")
    return response_text

async def main():
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="app", session_service=session_service)
    
    user_id = "live_test_user_v2"
    session_id = "live_test_session_v2"

    # Ensure session exists
    await session_service.create_session(app_name="app", user_id=user_id, session_id=session_id)

    queries = [
        "What is the phone number and address of my business?",
        "What are our recent reviews saying? Provide a summary.",
        "Are there any unanswered questions? List them.",
        "How has our performance been lately?"
    ]

    for query in queries:
        await interrogate(runner, user_id, session_id, query)

if __name__ == "__main__":
    asyncio.run(main())
