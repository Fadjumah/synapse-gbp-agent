from datetime import datetime
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
    tool_name: str, e: Exception, args: tuple, kwargs: dict, api_response: str | None = None
) -> str:
    """Formats a tool error into a detailed string for the LLM.

    Args:
        tool_name: The name of the tool that failed.
        e: The exception that was raised.
        args: The positional arguments passed to the tool.
        kwargs: The keyword arguments passed to the tool.
        api_response: The API response content if the error was an HttpError.

    Returns:
        A formatted multi-line string with error details for the LLM.
    """
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


def tool_exception_handler(func: Callable) -> Callable:
    """A decorator to handle exceptions in tool functions, formatting them for the LLM.

    Args:
        func: The tool function to wrap.

    Returns:
        The wrapped function with exception handling.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
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
    """A class to represent a tool that the agent can use.

    Attributes:
        function: The callable function that implements the tool's logic.
        name: The name of the tool, as exposed to the LLM.
        description: A description of what the tool does.
        run: The wrapped tool function with a name and docstring for the LLM.
    """

    def __init__(self, function: Callable[..., Any], name: str, description: str):
        self.function = function
        self.name = name
        self.description = description

        def tool_runner(*args: Any, **kwargs: Any) -> Any:
            return self.function(*args, **kwargs)

        tool_runner.__name__ = self.name
        tool_runner.__doc__ = self.description
        self.run = tool_runner


def get_gbp_credentials() -> Credentials:
    """Get GBP credentials for Google Business Profile API.

    Uses OAuth2 refresh token flow if GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID,
    and GOOGLE_CLIENT_SECRET environment variables are set. Otherwise, falls
    back to Google Application Default Credentials.

    Returns:
        A google.oauth2.credentials.Credentials object.
    """
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
        """Build a Google API service object.

        Args:
            service_name: The name of the service to build (e.g., 'mybusinessbusinessinformation').
            version: The version of the service (e.g., 'v1').

        Returns:
            A Google API client service object.

        Raises:
            ValueError: If a deprecated service and version are requested.
        """
        if service_name == "mybusiness" and version == "v4":
            raise ValueError(
                "The 'mybusiness' v4 API is deprecated and no longer available. "
                "Please use modern v1 APIs like 'mybusinessbusinessinformation' or 'mybusinessreviews'."
            )
        credentials = get_gbp_credentials()
        return build(service_name, version, credentials=credentials, cache_discovery=False)

    @tool_exception_handler
    def list_accounts(self) -> list[dict[str, Any]]:
        """Lists all Google Business Profile accounts accessible to the authenticated user.

        Returns:
            A list of account dictionaries, or an empty list if none are found.
        """
        service = self._build_gbp_service("mybusinessaccountmanagement", "v1")
        accounts = service.accounts().list().execute()
        return accounts.get("accounts", [])

    @tool_exception_handler
    def list_locations(self, account_name: str) -> list[dict[str, Any]]:
        """Lists all locations for a specific Google Business Profile account.

        Args:
            account_name: The resource name of the account, e.g., 'accounts/{accountId}'.

        Returns:
            A list of location dictionaries, or an empty list if none are found.
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
        """Lists reviews for a specific Google Business Profile location.

        Args:
            location_name: The resource name of the location, e.g., 'accounts/{accountId}/locations/{locationId}'.

        Returns:
            A list of review dictionaries, or an empty list if none are found.
        """
        service = self._build_gbp_service("mybusinessreviews", "v1")
        reviews = (
            service.accounts().locations().reviews().list(parent=location_name).execute()
        )
        return reviews.get("reviews", [])

    @tool_exception_handler
    def reply_to_review(self, review_name: str, reply_text: str) -> dict[str, Any]:
        """Replies to a Google Business Profile review.

        Args:
            review_name: The resource name of the review, e.g., 'accounts/{accountId}/locations/{locationId}/reviews/{reviewId}'.
            reply_text: The text of the reply.

        Returns:
            A dictionary representing the updated review reply resource.
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
        self,
        location_name: str,
        summary: str,
        call_to_action_url: str | None = None,
        media_key: str | None = None,
    ) -> dict[str, Any]:
        """Creates a local post (Update) on Google Business Profile.

        Args:
            location_name: The resource name of the location, e.g., 'accounts/{accountId}/locations/{locationId}'.
            summary: The content of the post.
            call_to_action_url: Optional URL for a 'LEARN_MORE' button.
            media_key: Optional media key from `upload_media_for_post` to include an image.

        Returns:
            A dictionary representing the created post resource.
        """
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        body = {"languageCode": "en-US", "summary": summary}
        if call_to_action_url:
            body["callToAction"] = {
                "actionType": "LEARN_MORE",
                "uri": call_to_action_url,
            }
        if media_key:
            body["media"] = [{"mediaFormat": "PHOTO", "googleMediaId": media_key}]

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
        """Gets performance insights for a specific location over a date range.

        Args:
            location_name: The resource name of the location, e.g., 'locations/{locationId}'.
            start_day: Start day in YYYY-MM-DD format.
            end_day: End day in YYYY-MM-DD format.

        Returns:
            A dictionary of metric names to their time series data.

        Raises:
            ValueError: If start_day is after end_day.
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

        start_dt = datetime.strptime(start_day, "%Y-%m-%d")
        end_dt = datetime.strptime(end_day, "%Y-%m-%d")

        if start_dt > end_dt:
            raise ValueError("start_day cannot be after end_day")

        api_params = {
            "name": perf_location_name,
            "dailyRange_startDate_year": start_dt.year,
            "dailyRange_startDate_month": start_dt.month,
            "dailyRange_startDate_day": start_dt.day,
            "dailyRange_endDate_year": end_dt.year,
            "dailyRange_endDate_month": end_dt.month,
            "dailyRange_endDate_day": end_dt.day,
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

    @tool_exception_handler
    def search_google_for_business_id(
        self, business_name: str, address: str
    ) -> dict[str, Any]:
        """Searches for a business on Google Maps and returns its Place ID.

        Uses the Places API to find a business based on its name and address.

        Args:
            business_name: The name of the business.
            address: The address of the business.

        Returns:
            A dictionary containing the place_id, name, and formatted_address,
            or an error dictionary if no business is found.
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")

        service = build("places", "v1", developerKey=api_key, cache_discovery=False)
        response = (
            service.places()
            .findPlaceFromText(
                body={
                    "text": f"{business_name}, {address}",
                },
                fields="places.id,places.displayName,places.formattedAddress",
            )
            .execute()
        )

        candidates = response.get("places", [])
        if not candidates:
            return {"error": "No business found with that name and address."}

        first_candidate = candidates[0]
        # The v1 API returns fields with different names. We remap them for compatibility.
        return {
            "place_id": first_candidate.get("id"),
            "name": first_candidate.get("displayName", {}).get("text"),
            "formatted_address": first_candidate.get("formattedAddress"),
        }

    @tool_exception_handler
    def upload_media_for_post(self, location_name: str, media_url: str) -> str:
        """Uploads media to a GBP location for use in a local post.

        Args:
            location_name: The resource name of the location, e.g., 'accounts/{accountId}/locations/{locationId}'.
            media_url: The publicly accessible URL of the media to upload.

        Returns:
            The resource name of the uploaded media item (i.e., the media_key).
        """
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        body = {"mediaFormat": "PHOTO", "sourceUrl": media_url}
        response = (
            service.locations()
            .media()
            .create(parent=location_name, body=body)
            .execute()
        )
        return response.get("name")


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
    Tool(
        function=gbp_tools_instance.search_google_for_business_id,
        name="search_google_for_business_id",
        description="Search for a business on Google Maps and return its Place ID.",
    ),
    Tool(
        function=gbp_tools_instance.upload_media_for_post,
        name="upload_media_for_post",
        description="Uploads media to a GBP location and returns a media key for use with create_local_post().",
    ),
]
