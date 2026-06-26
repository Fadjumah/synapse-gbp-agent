import asyncio
import os
from datetime import datetime
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent

async def test_date_awareness():
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="app", session_service=session_service)
    
    user_id = "test_user"
    session_id = "test_session"
    
    await session_service.create_session(app_name="app", user_id=user_id, session_id=session_id)
    
    # Simulate the injection logic from telegram_bot.py
    current_time_str = "Friday, June 26, 2026" # Mocking the date from user's request
    context_string = f"### System Context:\n- Current Date: {current_time_str}\n\n"
    user_message = "What is today's date according to your system?"
    full_user_message = context_string + user_message
    
    print(f"Sending message:\n{full_user_message}\n")
    
    response_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=full_user_message)]),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                response_text += event.content.parts[0].text
                
    print(f"Agent Response: {response_text}")
    
    if "2026" in response_text:
        print("SUCCESS: Agent is aware of the current date (2026).")
    else:
        print("FAILURE: Agent is still stuck in the past or didn't use the context.")

if __name__ == "__main__":
    asyncio.run(test_date_awareness())
