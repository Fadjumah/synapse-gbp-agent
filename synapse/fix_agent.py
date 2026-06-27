import vertexai
from vertexai.preview import reasoning_engines
from agent import synapse_root

vertexai.init(
    project="gen-lang-client-0479504041",
    location="europe-west1",
    staging_bucket="gs://gen-lang-client-0479504041-synapse-staging-eu"
)

class SynapseAgentWrapper:
    def __init__(self, runner):
        self.runner = runner
    def set_up(self):
        pass
    def query(self, input: str):
        if hasattr(self.runner, 'invoke'):
            return self.runner.invoke({"input": input})
        return self.runner.query(input)

print("🚀 Starting deployment to Europe (with google-adk)...")
remote_app = reasoning_engines.ReasoningEngine.create(
    SynapseAgentWrapper(synapse_root),
    display_name="Synapse Bot dependency Fix",
    # ADDING THE MISSING MODULE HERE:
    requirements=[
        "google-cloud-aiplatform[reasoningengine]",
        "google-adk",
        "cloudpickle"
    ]
)
print(f"\n✅ SUCCESS! New Bot ID: {remote_app.resource_name}")
