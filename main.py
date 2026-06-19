import os
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

# The directory where our agent(s) are located. 
# ADK will look for subdirectories (like 'app/') containing agent.py
AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

# get_fast_api_app creates a FastAPI application with standard ADK endpoints:
# - POST /apps/{app_name}/run : Send a message and get a response
# - GET /apps/{app_name}/status : Check agent status
app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=True, # Enables the built-in Playground UI at /
)

if __name__ == "__main__":
    # Start the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
