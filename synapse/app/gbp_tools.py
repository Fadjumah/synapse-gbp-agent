from datetime import datetime
import functools
import json
import logging
import os
from typing import Any, Callable

from google.auth import default
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError, UnknownApiNameOrVersion

logger = logging.getLogger(__name__)


def _format_tool_error(
    tool_name: str, e: Exception, args: tuple, kwargs: dict, api_response: str | None = None
) -> str:
    """Formats a tool error into a detailed string for the LLM."""
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
        "instructions_for_llm: Analyze this traceback. If you passed invalid parameters, please correct your arguments and call the tool again. If this is a deprecated API error, do not call this tool again and look for an alternative."
    )
    return "\n".join(error_details)


def tool_exception_handler(func: Callable) -> Callable:
    """Decorator to handle exceptions and format them for the LLM."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tool_name = func.__name__
        try:
            return func(*args, **kwargs)
        except (HttpError, UnknownApiNameOrVersion) as e:
            logger.error(f"API Error in {tool_name}: {e}")
            api_response_str = None
            if isinstance(e, HttpError):
                try:
                    api_response_obj = json.loads(e.content.decode("utf-8"))
                    api_response_str = json.dumps(api_response_obj)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    api_response_str = e.content.decode("utf-8", errors="ignore")
            
            return _format_tool_error(
                tool_name, e, args, kwargs, api_response=api_response_str
            )
        except Exception as e:
            logger.error(f"Unexpected Error in {tool_name}: {e}")
            return _format_tool_error(tool_name, e, args, kwargs)

    return wrapper


class Tool:
    """Represents a tool for the agent."""
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
    """Get GBP credentials for Google Business Profile API."""
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
    """Tools to interact with the Google Business Profile API."""

    _PERFORMANCE_METRICS = [
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

    def _build_gbp_service(self, service_name: str, version: str) -> Any:
        """Build a Google API service object with deprecation checks."""
        if service_name == "mybusiness" and version == "v4":
             raise UnknownApiNameOrVersion(
                "The 'mybusiness' v4 API is deprecated. "
                "Use v1 APIs: 'mybusinessbusinessinformation', 'mybusinessreviews', etc."
            )
        
        credentials = get_gbp_credentials()
        return build(service_name, version, credentials=credentials, cache_discovery=False)

    @tool_exception_handler
    def list_accounts(self) -> list[dict[str, Any]]:
        """Lists all Google Business Profile accounts."""
        service = self._build_gbp_service("mybusinessaccountmanagement", "v1")
        accounts = service.accounts().list().execute()
        return accounts.get("accounts", [])

    @tool_exception_handler
    def list_locations(self, account_name: str) -> list[dict[str, Any]]:
        """Lists all locations for an account."""
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
        """Lists reviews for a location."""
        service = self._build_gbp_service("mybusinessreviews", "v1")
        reviews = (
            service.accounts().locations().reviews().list(parent=location_name).execute()
        )
        return reviews.get("reviews", [])

    @tool_exception_handler
    def reply_to_review(self, review_name: str, reply_text: str) -> dict[str, Any]:
        """Replies to a review."""
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
        """Creates a local post."""
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
        """Gets performance insights with fixed flat parameter schema."""
        if location_name.startswith("accounts/"):
            location_id = location_name.split("/")[-1]
            perf_location_name = f"locations/{location_id}"
        else:
            perf_location_name = location_name

        service = self._build_gbp_service("businessprofileperformance", "v1")

        start_dt = datetime.strptime(start_day, "%Y-%m-%d")
        end_dt = datetime.strptime(end_day, "%Y-%m-%d")

        if start_dt > end_dt:
            raise ValueError("start_day cannot be after end_day")

        # FIX: Pass flat arguments instead of dictionary to comply with discovery schema
        results = {}
        for metric in self._PERFORMANCE_METRICS:
            response = (
                service.locations()
                .getDailyMetricsTimeSeries(
                    name=perf_location_name,
                    dailyMetric=metric,
                    dailyRange_startDate_year=start_dt.year,
                    dailyRange_startDate_month=start_dt.month,
                    dailyRange_startDate_day=start_dt.day,
                    dailyRange_endDate_year=end_dt.year,
                    dailyRange_endDate_month=end_dt.month,
                    dailyRange_endDate_day=end_dt.day,
                )
                .execute()
            )
            results[metric] = response.get("timeSeries", {})

        return results

    @tool_exception_handler
    def search_google_for_business_id(
        self, business_name: str, address: str
    ) -> dict[str, Any]:
        """Searches for a business Place ID."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set.")

        service = build("places", "v1", developerKey=api_key, cache_discovery=False)
        response = (
            service.places()
            .findPlaceFromText(
                body={"text": f"{business_name}, {address}"},
                fields="places.id,places.displayName,places.formattedAddress",
            )
            .execute()
        )

        candidates = response.get("places", [])
        if not candidates:
            return {"error": "No business found."}

        first = candidates[0]
        return {
            "place_id": first.get("id"),
            "name": first.get("displayName", {}).get("text"),
            "formatted_address": first.get("formattedAddress"),
        }

    @tool_exception_handler
    def upload_media_for_post(self, location_name: str, media_url: str) -> str:
        """Uploads media for a post."""
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        body = {"mediaFormat": "PHOTO", "sourceUrl": media_url}
        response = (
            service.locations()
            .media()
            .create(parent=location_name, body=body)
            .execute()
        )
        return response.get("name", "")

    @tool_exception_handler
    def get_location_details(self, location_name: str, read_mask: str) -> dict[str, Any]:
        """Gets location details."""
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        return service.locations().get(name=location_name, readMask=read_mask).execute()

    @tool_exception_handler
    def update_location_data(self, location_name: str, update_data: dict[str, Any]) -> dict[str, Any]:
        """Updates location data."""
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        update_mask = ",".join(update_data.keys())
        return service.locations().patch(name=location_name, updateMask=update_mask, body=update_data).execute()

    @tool_exception_handler
    def list_local_posts(self, location_name: str) -> list[dict[str, Any]]:
        """Lists local posts."""
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        response = service.accounts().locations().localPosts().list(parent=location_name).execute()
        return response.get("localPosts", [])

    @tool_exception_handler
    def delete_local_post(self, post_name: str) -> dict[str, Any]:
        """Deletes a local post."""
        service = self._build_gbp_service("mybusinessbusinessinformation", "v1")
        return service.accounts().locations().localPosts().delete(name=post_name).execute()

    @tool_exception_handler
    def delete_review_reply(self, review_name: str) -> dict[str, Any]:
        """Deletes a review reply."""
        service = self._build_gbp_service("mybusinessreviews", "v1")
        return service.accounts().locations().reviews().deleteReply(name=review_name).execute()

    @tool_exception_handler
    def list_questions(self, location_name: str) -> list[dict[str, Any]]:
        """Lists questions."""
        if location_name.startswith("accounts/"):
            location_id = location_name.split("/")[-1]
            qna_location_name = f"locations/{location_id}"
        else:
            qna_location_name = location_name
        service = self._build_gbp_service("mybusinessqanda", "v1")
        response = service.locations().questions().list(parent=qna_location_name).execute()
        return response.get("questions", [])

    @tool_exception_handler
    def answer_question(self, question_name: str, answer_text: str) -> dict[str, Any]:
        """Answers a question."""
        service = self._build_gbp_service("mybusinessqanda", "v1")
        body = {"text": answer_text}
        return service.locations().questions().answers().upsert(parent=question_name, body=body).execute()


gbp_tools_instance = GBPTools()

def __getattr__(name):
    if hasattr(gbp_tools_instance, name):
        return getattr(gbp_tools_instance, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")

tools = [
    Tool(function=gbp_tools_instance.list_accounts, name="list_accounts", description="Lists all accessible Google Business Profile accounts, returning their names and account IDs."),
    Tool(function=gbp_tools_instance.list_locations, name="list_locations", description="Lists all business locations for a given Google Business Profile account ID."),
    Tool(function=gbp_tools_instance.list_reviews, name="list_reviews", description="Lists all reviews for a specific business location, including review content and author."),
    Tool(function=gbp_tools_instance.reply_to_review, name="reply_to_review", description="Posts a public reply to a specific customer review."),
    Tool(function=gbp_tools_instance.create_local_post, name="create_local_post", description="Creates a new local post on a business's Google Business Profile. Can optionally include a call-to-action URL and an image."),
    Tool(function=gbp_tools_instance.get_performance_insights, name="get_performance_insights", description="Retrieves performance metrics (e.g., views, clicks) for a business location over a specified date range. Dates should be in 'YYYY-MM-DD' format."),
    Tool(function=gbp_tools_instance.search_google_for_business_id, name="search_google_for_business_id", description="Searches Google for a business by name and address to find its unique Place ID."),
    Tool(function=gbp_tools_instance.upload_media_for_post, name="upload_media_for_post", description="Uploads an image from a URL to a Google Business Profile location and returns a media key to be used with create_local_post."),
    Tool(function=gbp_tools_instance.get_location_details, name="get_location_details", description="Gets detailed business information for a specific location, such as address, phone number, and opening hours."),
    Tool(function=gbp_tools_instance.update_location_data, name="update_location_data", description="Updates core business information for a specific location. Can update fields like website, hours, and phone number."),
    Tool(function=gbp_tools_instance.list_local_posts, name="list_local_posts", description="Lists all historical local posts for a business location."),
    Tool(function=gbp_tools_instance.delete_local_post, name="delete_local_post", description="Deletes a specific local post from a business's profile."),
    Tool(function=gbp_tools_instance.delete_review_reply, name="delete_review_reply", description="Deletes a previously posted reply to a customer review."),
    Tool(function=gbp_tools_instance.list_questions, name="list_questions", description="Lists all customer questions for a business location."),
    Tool(function=gbp_tools_instance.answer_question, name="answer_question", description="Posts an answer to a customer's question on the business profile."),
]
