import asyncio
import os
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent
from dotenv import load_dotenv

load_dotenv()

async def main():
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="app", session_service=session_service)
    
    user_id = "live_test_user"
    session_id = "live_test_session"
    query = "What is the phone number of my business?"

    print(f"Querying agent: '{query}'")
    # Ensure session exists
    await session_service.create_session(app_name="app", user_id=user_id, session_id=session_id)

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
    ):
        if event.is_final_response():
            print(f"Agent response: {event.content.parts[0].text}")

if __name__ == "__main__":
    asyncio.run(main())
