refactor: Overhaul GBP tool framework for robustness and resilience

This commit completes a comprehensive refactoring of the Google Business
Profile (GBP) tool framework to enhance its robustness, error handling,
and maintainability.

Key improvements include:
- A centralized exception handling decorator (`@tool_exception_handler`) now
  wraps all tools. It prevents unhandled exceptions from crashing the
  container and provides a detailed, structured error feedback loop to the
  LLM with actionable instructions.

- All calls to the deprecated `mybusiness` v4 API have been replaced with
  modern v1 equivalents, and a guard has been added to prevent future use.

- The tool implementation has been modernized with `Tool` and `GBPTools`
  classes for better encapsulation and organization.

- New tools have been added to expand capabilities:
  - `search_google_for_business_id`: Uses the Places API to find a business.
  - `upload_media_for_post`: Uploads media for use in posts.

- Existing tools have been improved:
  - `create_local_post` now supports media attachments.
  - `get_performance_insights` has been updated to use the correct API
    parameter schema and includes date validation.

- Type annotations and docstrings have been enhanced across all tools to
  ensure flawless schema generation for the ADK and improve code clarity.
