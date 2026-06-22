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


gbp_tools_instance = GBPTools()

def __getattr__(name):
    if hasattr(gbp_tools_instance, name):
        return getattr(gbp_tools_instance, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")

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
