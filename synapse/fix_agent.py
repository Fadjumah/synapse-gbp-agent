import vertexai
from vertexai.preview import reasoning_engines
import asyncio
import nest_asyncio

# Ensure nest_asyncio is applied for environments with running loops
nest_asyncio.apply()

class SynapseReasoningEngine:
    def __init__(self):
        self.agent = None

    def set_up(self):
        # Import inside set_up to ensure it's available in the remote environment
        from app.agent import root_agent
        self.agent = root_agent
    
    def query(self, message: str):
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        
        if not self.agent:
            self.set_up()

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

        return asyncio.run(_run())

if __name__ == "__main__":
    # Initialize Vertex AI
    vertexai.init(
        project="gen-lang-client-0479504041",
        location="europe-west1",
        staging_bucket="gs://gen-lang-client-0479504041-synapse-staging-eu"
    )

    print("Redeploying agent to europe-west1...")
    
    # Redeploy the agent using supported parameters
    remote_app = reasoning_engines.ReasoningEngine.create(
        SynapseReasoningEngine(),
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
