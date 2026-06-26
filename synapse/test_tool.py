from app.gbp_tools import gbp_tools_instance
import os
import logging

logging.basicConfig(level=logging.DEBUG)

# Mock environment variables
os.environ["GBP_CLIENT_ID"] = "dummy"
os.environ["GOOGLE_CLIENT_SECRET"] = "dummy"
os.environ["GOOGLE_REFRESH_TOKEN"] = "dummy"

print(f"Testing list_accounts...")
print(gbp_tools_instance.list_accounts())
print(f"Testing list_reviews...")
print(gbp_tools_instance.list_reviews("accounts/123/locations/456"))
