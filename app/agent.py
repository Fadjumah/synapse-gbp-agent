from google.adk.agents import Agent

root_agent = Agent(
    name="synapse_gbp_agent",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant for Synapse GBP (Google Business Profile). You can help users manage their business profiles, answer questions about GBP, and provide insights.",
)
