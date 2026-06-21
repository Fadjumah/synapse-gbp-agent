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


def _format_tool_error(
    tool_name: str, e: Exception, args: tuple, kwargs: dict, api_response: str = None
) -> str:
    """Format a tool error into a detailed string for the LLM."""
    error_details = [
        "[TOOL_ERROR]",
        f"tool_name: {tool_name}",
        f"exception_type: {type(e).__name__}",
        f"error_details: {str(e)}",
        f"tool_args: {args}",
        f"tool_kwargs: {kwargs}",
    ]
    if api_response:
        error_details.append(f"api_response: {api_response}")

    error_details.append(
        "instructions_for_llm: Analyze this traceback. If you passed invalid parameters, please correct your arguments and call the tool again."
    )
    return "\n".join(error_details)


def tool_exception_handler(func):
    """A decorator to handle exceptions in tool functions."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            logger.error(f"API Error in {tool_name}: {e}")
            try:
                api_response_obj = json.loads(e.content.decode("utf-8"))
                api_response_str = json.dumps(api_response_obj)
            except (json.JSONDecodeError, UnicodeDecodeError):
                api_response_str = (
                    "Unparseable content - "
                    f"{e.content.decode('utf-8', errors='ignore')}"
                )
            return _format_tool_error(
                tool_name, e, args, kwargs, api_response=api_response_str
            )
        except Exception as e:
            logger.error(f"Unexpected Error in {tool_name}: {e}")
            return _format_tool_error(tool_name, e, args, kwargs)

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

    @tool_exception_handler
    def list_accounts(self) -> list[dict[str, Any]]:
        """List all Google Business Profile accounts accessible."""
        service = self._build_gbp_service("mybusinessaccountmanagement", "v1")
        accounts = service.accounts().list().execute()
        return accounts.get("accounts", [])

    @tool_exception_handler
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

    @tool_exception_handler
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

    @tool_exception_handler
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

    @tool_exception_handler
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

    @tool_exception_handler
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

        start_date_parts = start_day.split("-")
        end_date_parts = end_day.split("-")

        api_params = {
            "name": perf_location_name,
            "dailyRange_startDate_year": int(start_date_parts[0]),
            "dailyRange_startDate_month": int(start_date_parts[1]),
            "dailyRange_startDate_day": int(start_date_parts[2]),
            "dailyRange_endDate_year": int(end_date_parts[0]),
            "dailyRange_endDate_month": int(end_date_parts[1]),
            "dailyRange_endDate_day": int(end_date_parts[2]),
        }

        results = {}
        for metric in metrics:
            response = (
                service.locations()
                .getDailyMetricsTimeSeries(dailyMetric=metric, **api_params)
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
