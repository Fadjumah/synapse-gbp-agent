import vertexai
from vertexai.preview import reasoning_engines
from app.agent import root_agent
import asyncio

class SynapseReasoningEngine:
    def __init__(self, agent):
        self.agent = agent

    def set_up(self):
        pass

    def query(self, message: str):
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        
        # Simple runner setup for RE
        session_service = InMemorySessionService()
        runner = Runner(agent=self.agent, app_name="app", session_service=session_service)
        
        async def _run():
            user_id = "re_user"
            session_id = "re_session"
            await session_service.create_session(app_name="app", user_id=user_id, session_id=session_id)
            
            response_text = ""
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=message)])
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    response_text = event.content.parts[0].text
            return response_text

        try:
            # Check if there is already an event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # This might happen in some environments
                import nest_asyncio
                nest_asyncio.apply()
            return asyncio.run(_run())
        except Exception:
            return asyncio.run(_run())

if __name__ == "__main__":
    # Initialize Vertex AI
    vertexai.init(
        project="gen-lang-client-0479504041",
        location="europe-west1",
        staging_bucket="gs://gen-lang-client-0479504041-synapse-staging-eu",
        service_account="468613454814-compute@developer.gserviceaccount.com"
    )

    print("Redeploying agent to europe-west1...")
    
    # Redeploy the agent without the invalid service_account parameter
    remote_app = reasoning_engines.ReasoningEngine.create(
        SynapseReasoningEngine(root_agent),
        display_name="Synapse Agent - Europe West 1",
        requirements=[
            "google-adk[gcp]>=2.0.0,<3.0.0",
            "google-cloud-aiplatform>=1.156.0",
            "nest-asyncio"
        ],
        extra_packages=["app"]
    )

    print(f"Redeployment successful.")
    print(f"New Resource Name: {remote_app.resource_name}")
