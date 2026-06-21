import functools
import json
import logging
import os
from typing import Any, Callable

from google.auth import default
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


def gbp_tool_error_handler(func):
    """
    A decorator to handle errors in GBP tool functions, providing a feedback loop to the agent.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            logger.error(f"API Error in {func.__name__}: {e}")
            if "list" in func.__name__:
                return []

            error_message = f"Tool '{func.__name__}' failed with an API error."
            try:
                error_content = json.loads(e.content.decode("utf-8"))
                if "error" in error_content and "message" in error_content["error"]:
                    error_message += (
                        f" API Response: {error_content['error']['message']}"
                    )
                else:
                    error_message += f" Reason: {e.reason}"
            except Exception:
                error_message += f" Reason: {e.reason}"

            return {"error": error_message, "tool_name": func.__name__}
        except Exception as e:
            logger.error(f"Unexpected Error in {func.__name__}: {e}")
            if "list" in func.__name__:
                return []
            return {
                "error": f"Tool '{func.__name__}' failed unexpectedly.",
                "details": str(e),
                "tool_name": func.__name__,
            }

    return wrapper


class Tool:
    """A class to represent a tool that the agent can use."""

    def __init__(self, function: Callable, name: str, description: str):
        self.function = function
        self.name = name
        self.description = description

        def tool_runner(*args, **kwargs):
            return self.function(*args, **kwargs)

        tool_runner.__name__ = self.name
        tool_runner.__doc__ = self.description
        self.run = tool_runner


def get_gbp_credentials():
    """Get GBP credentials using OAuth2 refresh token if available, else default credentials."""
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    scopes = ["https://www.googleapis.com/auth/business.manage"]

    if refresh_token and client_id and client_secret:
        return Credentials(
            None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )

    credentials, _ = default(scopes=scopes)
    return credentials


class GBPTools:
    """A collection of tools to interact with the Google Business Profile API."""

    def _build_gbp_service(self, service_name: str, version: str) -> Any:
        """Build a Google Business Profile service."""
        credentials = get_gbp_credentials()
        return build(service_name, version, credentials=credentials, cache_discovery=False)

    @gbp_tool_error_handler
    def list_accounts(self) -> list[dict[str, Any]]:
        """List all Google Business Profile accounts accessible."""
        service = self._build_gbp_service("mybusinessaccountmanagement", "v1")
        accounts = service.accounts().list().execute()
        return accounts.get("accounts", [])

    @gbp_tool_error_handler
    def list_locations(self, account_name: str) -> list[dict[str, Any]]:
        """
        List all locations for a specific Google Business Profile account.

        Args:
            account_name: The resource name of the account, e.g., 'accounts/{accountId}'
        """
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        locations = (
            service.accounts()
            .locations()
            .list(parent=account_name, readMask="name,title,storeCode")
            .execute()
        )
        return locations.get("locations", [])

    @gbp_tool_error_handler
    def list_reviews(self, location_name: str) -> list[dict[str, Any]]:
        """
        List reviews for a specific Google Business Profile location.

        Args:
            location_name: The resource name of the location, e.g., 'accounts/{accountId}/locations/{locationId}'
        """
        service = self._build_gbp_service("mybusinessreviews", "v1")
        reviews = (
            service.accounts().locations().reviews().list(parent=location_name).execute()
        )
        return reviews.get("reviews", [])

    @gbp_tool_error_handler
    def reply_to_review(self, review_name: str, reply_text: str) -> dict[str, Any]:
        """
        Reply to a Google Business Profile review.

        Args:
            review_name: The resource name of the review, e.g., 'accounts/{accountId}/locations/{locationId}/reviews/{reviewId}'
            reply_text: The text of the reply.
        """
        service = self._build_gbp_service("mybusinessreviews", "v1")
        body = {"comment": reply_text}
        response = (
            service.accounts()
            .locations()
            .reviews()
            .updateReply(name=review_name, body=body)
            .execute()
        )
        return response

    @gbp_tool_error_handler
    def create_local_post(
        self, location_name: str, summary: str, call_to_action_url: str | None = None
    ) -> dict[str, Any]:
        """
        Create a local post (Update) on Google Business Profile.

        Args:
            location_name: The resource name of the location, e.g., 'accounts/{accountId}/locations/{locationId}'
            summary: The content of the post.
            call_to_action_url: Optional URL for a 'LEARN_MORE' button.
        """
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        body = {"languageCode": "en-US", "summary": summary}
        if call_to_action_url:
            body["callToAction"] = {
                "actionType": "LEARN_MORE",
                "uri": call_to_action_url,
            }

        response = (
            service.accounts()
            .locations()
            .localPosts()
            .create(parent=location_name, body=body)
            .execute()
        )
        return response

    @gbp_tool_error_handler
    def get_performance_insights(
        self, location_name: str, start_day: str, end_day: str
    ) -> dict[str, Any]:
        """
        Get performance insights for a location.

        Args:
            location_name: The resource name of the location, e.g., 'locations/{locationId}'
            start_day: Start day in YYYY-MM-DD format.
            end_day: End day in YYYY-MM-DD format.
        """
        # Note: businessprofileperformance uses a different location name format: 'locations/{locationId}'
        # If location_name is 'accounts/{acc}/locations/{loc}', we need to strip the accounts part.
        if location_name.startswith("accounts/"):
            location_id = location_name.split("/")[-1]
            perf_location_name = f"locations/{location_id}"
        else:
            perf_location_name = location_name

        service = self._build_gbp_service("businessprofileperformance", "v1")

        # Example metrics
        metrics = [
            "CALL_CLICKS",
            "WEBSITE_CLICKS",
            "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
            "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
            "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
            "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
            "BUSINESS_CONVERSATIONS",
            "BUSINESS_BOOKINGS",
            "BUSINESS_FOOD_ORDERS",
            "BUSINESS_DIRECTION_REQUESTS",
        ]

        start_date = {
            "year": int(start_day[:4]),
            "month": int(start_day[5:7]),
            "day": int(start_day[8:10]),
        }
        end_date = {
            "year": int(end_day[:4]),
            "month": int(end_day[5:7]),
            "day": int(end_day[8:10]),
        }

        results = {}
        for metric in metrics:
            response = (
                service.locations()
                .getDailyMetricsTimeSeries(
                    name=perf_location_name,
                    dailyMetric=metric,
                    dailyRange_startDate_year=start_date["year"],
                    dailyRange_startDate_month=start_date["month"],
                    dailyRange_startDate_day=start_date["day"],
                    dailyRange_endDate_year=end_date["year"],
                    dailyRange_endDate_month=end_date["month"],
                    dailyRange_endDate_day=end_date["day"],
                )
                .execute()
            )
            results[metric] = response.get("timeSeries", {})

        return results


gbp_tools_instance = GBPTools()

tools = [
    Tool(
        function=gbp_tools_instance.list_accounts,
        name="list_accounts",
        description="List all Google Business Profile accounts accessible.",
    ),
    Tool(
        function=gbp_tools_instance.list_locations,
        name="list_locations",
        description="List all locations for a specific Google Business Profile account.",
    ),
    Tool(
        function=gbp_tools_instance.list_reviews,
        name="list_reviews",
        description="List reviews for a specific Google Business Profile location.",
    ),
    Tool(
        function=gbp_tools_instance.reply_to_review,
        name="reply_to_review",
        description="Reply to a Google Business Profile review.",
    ),
    Tool(
        function=gbp_tools_instance.create_local_post,
        name="create_local_post",
        description="Create a local post (Update) on Google Business Profile.",
    ),
    Tool(
        function=gbp_tools_instance.get_performance_insights,
        name="get_performance_insights",
        description="Get performance insights for a location.",
    ),
]
