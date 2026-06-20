import logging
import os
from typing import Any

from google.auth import default
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


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


def get_mybusiness_v4_service():
    """Get the Google My Business v4 service (for reviews and posts)."""
    credentials = get_gbp_credentials()
    return build("mybusiness", "v4", credentials=credentials)


def get_business_information_service():
    """Get the Business Information v1 service."""
    credentials = get_gbp_credentials()
    return build("mybusinessbusinessinformation", "v1", credentials=credentials)


def get_performance_service():
    """Get the Business Profile Performance v1 service."""
    credentials = get_gbp_credentials()
    return build("businessprofileperformance", "v1", credentials=credentials)


def list_accounts() -> list[dict[str, Any]]:
    """List all Google Business Profile accounts accessible to the authenticated user/service account."""
    try:
        # Note: Account management is still in v4 for some features or v1 for others.
        # Let's try v4 first as it's common for accounts.
        service = get_mybusiness_v4_service()
        accounts = service.accounts().list().execute()
        return accounts.get("accounts", [])
    except HttpError as e:
        logger.error(f"Error listing accounts: {e}")
        return []


def list_locations(account_name: str) -> list[dict[str, Any]]:
    """
    List all locations for a specific Google Business Profile account.

    Args:
        account_name: The resource name of the account, e.g., 'accounts/{accountId}'
    """
    try:
        service = get_business_information_service()
        locations = (
            service.accounts()
            .locations()
            .list(parent=account_name, readMask="name,title,storeCode")
            .execute()
        )
        return locations.get("locations", [])
    except HttpError as e:
        logger.error(f"Error listing locations: {e}")
        return []


def list_reviews(location_name: str) -> list[dict[str, Any]]:
    """
    List reviews for a specific Google Business Profile location.

    Args:
        location_name: The resource name of the location, e.g., 'accounts/{accountId}/locations/{locationId}'
    """
    try:
        service = get_mybusiness_v4_service()
        reviews = (
            service.accounts().locations().reviews().list(parent=location_name).execute()
        )
        return reviews.get("reviews", [])
    except HttpError as e:
        logger.error(f"Error listing reviews: {e}")
        return []


def reply_to_review(review_name: str, reply_text: str) -> dict[str, Any]:
    """
    Reply to a Google Business Profile review.

    Args:
        review_name: The resource name of the review, e.g., 'accounts/{accountId}/locations/{locationId}/reviews/{reviewId}'
        reply_text: The text of the reply.
    """
    try:
        service = get_mybusiness_v4_service()
        body = {"comment": reply_text}
        response = (
            service.accounts()
            .locations()
            .reviews()
            .updateReply(name=review_name, body=body)
            .execute()
        )
        return response
    except HttpError as e:
        logger.error(f"Error replying to review: {e}")
        return {"error": str(e)}


def create_local_post(
    location_name: str, summary: str, call_to_action_url: str | None = None
) -> dict[str, Any]:
    """
    Create a local post (Update) on Google Business Profile.

    Args:
        location_name: The resource name of the location, e.g., 'accounts/{accountId}/locations/{locationId}'
        summary: The content of the post.
        call_to_action_url: Optional URL for a 'LEARN_MORE' button.
    """
    try:
        service = get_mybusiness_v4_service()
        body = {"languageCode": "en-US", "summary": summary, "topicType": "STANDARD"}
        if call_to_action_url:
            body["callToAction"] = {
                "actionType": "LEARN_MORE",
                "url": call_to_action_url,
            }

        response = (
            service.accounts()
            .locations()
            .localPosts()
            .create(parent=location_name, body=body)
            .execute()
        )
        return response
    except HttpError as e:
        logger.error(f"Error creating post: {e}")
        return {"error": str(e)}


def get_performance_insights(
    location_name: str, start_day: str, end_day: str
) -> dict[str, Any]:
    """
    Get performance insights for a location.

    Args:
        location_name: The resource name of the location, e.g., 'locations/{locationId}'
        start_day: Start day in YYYY-MM-DD format.
        end_day: End day in YYYY-MM-DD format.
    """
    try:
        # Note: businessprofileperformance uses a different location name format: 'locations/{locationId}'
        # If location_name is 'accounts/{acc}/locations/{loc}', we need to strip the accounts part.
        if location_name.startswith("accounts/"):
            location_id = location_name.split("/")[-1]
            perf_location_name = f"locations/{location_id}"
        else:
            perf_location_name = location_name

        service = get_performance_service()

        # Example metrics
        metrics = [
            "CALLS",
            "WEBSITE_CLICKS",
            "DIRECTION_REQUESTS",
            "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
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
                    dailyRange_startDate=start_date,
                    dailyRange_endDate=end_date,
                )
                .execute()
            )
            results[metric] = response.get("timeSeries", {})

        return results
    except HttpError as e:
        logger.error(f"Error getting performance insights: {e}")
        return {"error": str(e)}
