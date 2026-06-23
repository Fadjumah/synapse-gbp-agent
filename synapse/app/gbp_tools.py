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
    error_details.append("instructions_for_llm: Analyze this traceback. If you passed invalid parameters, please correct your arguments and call the tool again. If this is a deprecated API error, do not call this tool again and look for an alternative.")
    return "\n".join(error_details)

def tool_exception_handler(func: Callable) -> Callable:
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
            return _format_tool_error(tool_name, e, args, kwargs, api_response=api_response_str)
        except Exception as e:
            logger.error(f"Unexpected Error in {tool_name}: {e}")
            return _format_tool_error(tool_name, e, args, kwargs)
    return wrapper

class GBPTools:
    def __init__(self):
        self.scopes = ["https://www.googleapis.com/auth/business.manage"]

    def _get_credentials(self):
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        client_id = os.getenv("GBP_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if refresh_token and client_id and client_secret:
            logger.info("Using Credentials from environment variables.")
            return Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=self.scopes
            )
        
        logger.warning("Environment credentials missing, falling back to default credentials.")
        credentials, _ = default(scopes=self.scopes)
        return credentials

    def _build_service(self, service_name: str, version: str, discovery_service_url: str | None = None) -> Any:
        return build(service_name, version, credentials=self._get_credentials(), cache_discovery=False, discoveryServiceUrl=discovery_service_url)

    @tool_exception_handler
    def list_accounts(self) -> Any:
        service = self._build_service("mybusinessaccountmanagement", "v1")
        accounts = service.accounts().list().execute()
        return accounts.get("accounts", [])

    @tool_exception_handler
    def list_locations(self, account_name: str) -> Any:
        service = self._build_service("mybusinessbusinessinformation", "v1")
        locations = service.accounts().locations().list(parent=account_name, readMask="name,title,storeCode").execute()
        return locations.get("locations", [])

    @tool_exception_handler
    def list_reviews(self, location_name: str) -> Any:
        # Reviews still primarily use the v4 endpoint
        discovery_url = "https://mybusiness.googleapis.com/$discovery/rest?version=v4"
        service = self._build_service("mybusiness", "v4", discovery_service_url=discovery_url)
        reviews = service.accounts().locations().reviews().list(parent=location_name).execute()
        return reviews.get("reviews", [])

    @tool_exception_handler
    def reply_to_review(self, review_name: str, reply_text: str) -> Any:
        discovery_url = "https://mybusiness.googleapis.com/$discovery/rest?version=v4"
        service = self._build_service("mybusiness", "v4", discovery_service_url=discovery_url)
        body = {"comment": reply_text}
        return service.accounts().locations().reviews().updateReply(name=review_name, body=body).execute()

    @tool_exception_handler
    def create_local_post(self, location_name: str, summary: str, call_to_action_url: str | None = None) -> Any:
        discovery_url = "https://mybusiness.googleapis.com/$discovery/rest?version=v4"
        service = self._build_service("mybusiness", "v4", discovery_service_url=discovery_url)
        body = {"languageCode": "en-US", "summary": summary}
        if call_to_action_url:
            body["callToAction"] = {"actionType": "LEARN_MORE", "uri": call_to_action_url}
        return service.accounts().locations().localPosts().create(parent=location_name, body=body).execute()

    @tool_exception_handler
    def list_local_posts(self, location_name: str) -> Any:
        discovery_url = "https://mybusiness.googleapis.com/$discovery/rest?version=v4"
        service = self._build_service("mybusiness", "v4", discovery_service_url=discovery_url)
        posts = service.accounts().locations().localPosts().list(parent=location_name).execute()
        return posts.get("localPosts", [])

    @tool_exception_handler
    def get_performance_insights(self, location_name: str, start_day: str, end_day: str) -> Any:
        if location_name.startswith("accounts/"):
            location_id = location_name.split("/")[-1]
            perf_location_name = f"locations/{location_id}"
        else:
            perf_location_name = location_name
        service = self._build_service("businessprofileperformance", "v1")
        metrics = ["CALL_CLICKS", "WEBSITE_CLICKS", "BUSINESS_IMPRESSIONS_DESKTOP_MAPS", "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", "BUSINESS_IMPRESSIONS_MOBILE_MAPS", "BUSINESS_IMPRESSIONS_MOBILE_SEARCH", "BUSINESS_CONVERSATIONS", "BUSINESS_BOOKINGS", "BUSINESS_FOOD_ORDERS", "BUSINESS_DIRECTION_REQUESTS"]
        start_date = {"year": int(start_day[:4]), "month": int(start_day[5:7]), "day": int(start_day[8:10])}
        end_date = {"year": int(end_day[:4]), "month": int(end_day[5:7]), "day": int(end_day[8:10])}
        results = {}
        for metric in metrics:
            response = service.locations().getDailyMetricsTimeSeries(name=perf_location_name, dailyMetric=metric, dailyRange_startDate_year=start_date["year"], dailyRange_startDate_month=start_date["month"], dailyRange_startDate_day=start_date["day"], dailyRange_endDate_year=end_date["year"], dailyRange_endDate_month=end_date["month"], dailyRange_endDate_day=end_date["day"]).execute()
            results[metric] = response.get("timeSeries", {})
        return results

    @tool_exception_handler
    def get_location_details(self, location_name: str) -> Any:
        service = self._build_service("mybusinessbusinessinformation", "v1")
        return service.locations().get(
            name=location_name, 
            readMask="name,title,phoneNumbers,regularHours,websiteUri,profile,serviceArea,labels,adWordsLocationExtensions,latlng,openInfo,metadata"
        ).execute()

    @tool_exception_handler
    def update_location_data(self, location_name: str, update_mask: str, body: dict) -> Any:
        service = self._build_service("mybusinessbusinessinformation", "v1")
        return service.locations().patch(name=location_name, updateMask=update_mask, body=body).execute()

    @tool_exception_handler
    def delete_local_post(self, post_name: str) -> Any:
        discovery_url = "https://mybusiness.googleapis.com/$discovery/rest?version=v4"
        service = self._build_service("mybusiness", "v4", discovery_service_url=discovery_url)
        return service.accounts().locations().localPosts().delete(name=post_name).execute()

    @tool_exception_handler
    def list_questions(self, location_name: str) -> Any:
        service = self._build_service("mybusinessqanda", "v1")
        questions = service.locations().questions().list(parent=location_name).execute()
        return questions.get("questions", [])

    @tool_exception_handler
    def answer_question(self, question_name: str, answer_text: str) -> Any:
        service = self._build_service("mybusinessqanda", "v1")
        body = {"answer": {"text": answer_text}}
        return service.locations().questions().answers().upsert(parent=question_name, body=body).execute()

    @tool_exception_handler
    def search_google_for_business_id(self, *args, **kwargs) -> Any: return {"error": "Not implemented"}
    @tool_exception_handler
    def upload_media_for_post(self, *args, **kwargs) -> Any: return {"error": "Not implemented"}
    @tool_exception_handler
    def delete_review_reply(self, *args, **kwargs) -> Any: return {"error": "Not implemented"}

gbp_tools_instance = GBPTools()

tools = [
    gbp_tools_instance.list_accounts,
    gbp_tools_instance.list_locations,
    gbp_tools_instance.list_reviews,
    gbp_tools_instance.reply_to_review,
    gbp_tools_instance.create_local_post,
    gbp_tools_instance.get_performance_insights,
    gbp_tools_instance.search_google_for_business_id,
    gbp_tools_instance.upload_media_for_post,
    gbp_tools_instance.get_location_details,
    gbp_tools_instance.update_location_data,
    gbp_tools_instance.list_local_posts,
    gbp_tools_instance.delete_local_post,
    gbp_tools_instance.delete_review_reply,
    gbp_tools_instance.list_questions,
    gbp_tools_instance.answer_question,
]
