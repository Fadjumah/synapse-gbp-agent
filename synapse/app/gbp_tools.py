import functools
import json
import logging
import os
import requests
from typing import Any, Callable

from google.auth import default
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError, UnknownApiNameOrVersion
from google.auth.transport.requests import Request as AuthRequest

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
        self._last_account_name = None 

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

    def _make_request(self, method: str, url: str, params: dict = None, body: dict = None) -> Any:
        credentials = self._get_credentials()
        # Ensure credentials are valid
        if not credentials.valid:
            credentials.refresh(AuthRequest())
        
        headers = {'Authorization': f'Bearer {credentials.token}'}
        
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=body
        )
        response.raise_for_status()
        return response.json()

    def _build_service(self, service_name: str, version: str, discovery_service_url: str | None = None) -> Any:
        return build(service_name, version, credentials=self._get_credentials(), cache_discovery=False, discoveryServiceUrl=discovery_service_url)

    def _ensure_hierarchical_location_name(self, location_name: str) -> str:
        if location_name.startswith("accounts/"):
            return location_name
        
        if hasattr(self, '_last_account_name') and self._last_account_name:
             return f"{self._last_account_name}/{location_name}"
        
        logger.warning(f"Location name '{location_name}' is not in hierarchical format and no account context found.")
        return location_name

    @tool_exception_handler
    def list_accounts(self) -> Any:
        service = self._build_service("mybusinessaccountmanagement", "v1")
        accounts = service.accounts().list().execute()
        account_list = accounts.get("accounts", [])
        if account_list:
            self._last_account_name = account_list[0].get("name")
        return account_list

    @tool_exception_handler
    def list_locations(self, account_name: str) -> Any:
        self._last_account_name = account_name
        service = self._build_service("mybusinessbusinessinformation", "v1")
        locations = service.accounts().locations().list(parent=account_name, readMask="name,title,storeCode").execute()
        return locations.get("locations", [])

    @tool_exception_handler
    def list_reviews(self, location_name: str) -> Any:
        location_name = self._ensure_hierarchical_location_name(location_name)
        url = f"https://mybusiness.googleapis.com/v4/{location_name}/reviews"
        data = self._make_request("GET", url)
        return data.get("reviews", [])

    @tool_exception_handler
    def reply_to_review(self, review_name: str, reply_text: str) -> Any:
        url = f"https://mybusiness.googleapis.com/v4/{review_name}/reply"
        body = {"comment": reply_text}
        return self._make_request("PUT", url, body=body)

    @tool_exception_handler
    def delete_review_reply(self, review_name: str) -> Any:
        url = f"https://mybusiness.googleapis.com/v4/{review_name}/reply"
        return self._make_request("DELETE", url)

    @tool_exception_handler
    def create_local_post(self, location_name: str, summary: str, call_to_action_url: str | None = None) -> Any:
        location_name = self._ensure_hierarchical_location_name(location_name)
        url = f"https://mybusiness.googleapis.com/v4/{location_name}/localPosts"
        body = {"languageCode": "en-US", "summary": summary}
        if call_to_action_url:
            body["callToAction"] = {"actionType": "LEARN_MORE", "uri": call_to_action_url}
        return self._make_request("POST", url, body=body)

    @tool_exception_handler
    def list_local_posts(self, location_name: str) -> Any:
        location_name = self._ensure_hierarchical_location_name(location_name)
        url = f"https://mybusiness.googleapis.com/v4/{location_name}/localPosts"
        data = self._make_request("GET", url)
        return data.get("localPosts", [])

    @tool_exception_handler
    def get_performance_insights(self, location_name: str, start_day: str, end_day: str) -> Any:
        if location_name.startswith("accounts/"):
            location_id = location_name.split("/")[-1]
            perf_location_name = f"locations/{location_id}"
        else:
            perf_location_name = location_name
            
        service = self._build_service("businessprofileperformance", "v1")
        metrics = [
            "CALL_CLICKS", "WEBSITE_CLICKS", "BUSINESS_IMPRESSIONS_DESKTOP_MAPS", 
            "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", "BUSINESS_IMPRESSIONS_MOBILE_MAPS", 
            "BUSINESS_IMPRESSIONS_MOBILE_SEARCH", "BUSINESS_CONVERSATIONS", 
            "BUSINESS_BOOKINGS", "BUSINESS_FOOD_ORDERS", "BUSINESS_DIRECTION_REQUESTS"
        ]
        start_date = {"year": int(start_day[:4]), "month": int(start_day[5:7]), "day": int(start_day[8:10])}
        end_date = {"year": int(end_day[:4]), "month": int(end_day[5:7]), "day": int(end_day[8:10])}
        results = {}
        
        for metric in metrics:
            response = service.locations().getDailyMetricsTimeSeries(
                name=perf_location_name, 
                dailyMetric=metric, 
                dailyRange_startDate_year=start_date["year"], 
                dailyRange_startDate_month=start_date["month"], 
                dailyRange_startDate_day=start_date["day"], 
                dailyRange_endDate_year=end_date["year"], 
                dailyRange_endDate_month=end_date["month"], 
                dailyRange_endDate_day=end_date["day"]
            ).execute()
            
            time_series = response.get("timeSeries", {})
            dated_values = time_series.get("datedValues", [])
            sanitized_values = []
            for dv in dated_values:
                sanitized_values.append({
                    "date": dv.get("date"),
                    "value": dv.get("value", "0")
                })
            
            results[metric] = {"datedValues": sanitized_values}
            
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
        url = f"https://mybusiness.googleapis.com/v4/{post_name}"
        return self._make_request("DELETE", url)

    @tool_exception_handler
    def list_questions(self, location_name: str) -> Any:
        return {"error": "The My Business Q&A API was discontinued by Google as of November 2025 and is no longer available."}

    @tool_exception_handler
    def answer_question(self, question_name: str, answer_text: str) -> Any:
        return {"error": "The My Business Q&A API was discontinued by Google as of November 2025 and is no longer available."}

    @tool_exception_handler
    def upload_media_for_post(self, *args, **kwargs) -> Any: return {"error": "Not implemented"}

gbp_tools_instance = GBPTools()

tools = [
    gbp_tools_instance.list_accounts,
    gbp_tools_instance.list_locations,
    gbp_tools_instance.list_reviews,
    gbp_tools_instance.reply_to_review,
    gbp_tools_instance.create_local_post,
    gbp_tools_instance.get_performance_insights,
    gbp_tools_instance.upload_media_for_post,
    gbp_tools_instance.get_location_details,
    gbp_tools_instance.update_location_data,
    gbp_tools_instance.list_local_posts,
    gbp_tools_instance.delete_local_post,
    gbp_tools_instance.delete_review_reply,
]
