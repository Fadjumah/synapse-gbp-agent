# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Stage 1: Builder
# Using a slim bookworm image as the base for the builder
FROM python:3.12-slim-bookworm AS builder

# Install uv for fast, reliable dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory to /app
WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Copy only dependency manifests to leverage Docker layer caching
# This ensures that dependencies are only re-installed if these files change
COPY pyproject.toml uv.lock ./

# Install strictly production dependencies (no dev dependencies)
# We use a cache mount for uv to speed up subsequent builds in the same environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Production
# Using the same slim bookworm base for the final production image
FROM python:3.12-slim-bookworm

# Install uv in the final image to support 'uv run' if needed, though we use the venv directly
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables for a robust production environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080

# Set the working directory to /app
WORKDIR /app

# Copy the pre-installed virtual environment from the builder stage
# This keeps the production image lightweight by excluding build tools and caches
COPY --from=builder /app/.venv /app/.venv

# Copy only the necessary application source code
COPY app ./app
COPY README.md ./

# Optional: Metadata arguments passed during the build process
ARG COMMIT_SHA=""
ENV COMMIT_SHA=${COMMIT_SHA}
ARG AGENT_VERSION=0.0.0
ENV AGENT_VERSION=${AGENT_VERSION}

# Expose port 8080 as required by Google Cloud Run
EXPOSE 8080

# Launch the application using uvicorn
# We bind to 0.0.0.0 to be accessible within the container and use port 8080
CMD ["uvicorn", "app.fast_api_app:app", "--host", "0.0.0.0", "--port", "8080"]
