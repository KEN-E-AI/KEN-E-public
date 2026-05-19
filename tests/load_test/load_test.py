# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
import time

from locust import HttpUser, between, task

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get API endpoint from environment or use default
api_base_url = os.environ.get(
    "API_BASE_URL", "https://kene-api-staging-391472102753.us-central1.run.app"
)
logger.info("Using API base URL: %s", api_base_url)


class ChatStreamUser(HttpUser):
    """Simulates a user interacting with the KEN-E API chat endpoints."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    host = api_base_url  # Set the base host URL for Locust

    @task
    def health_check(self) -> None:
        """Check the health endpoint."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"Health check failed with status {response.status_code}"
                )

    @task(3)  # Weight of 3 - this task is 3x more likely to run
    def chat_completion(self) -> None:
        """Simulates a chat completion request."""
        headers = {"Content-Type": "application/json"}

        # Use the auth token if available, otherwise skip auth for public endpoints
        if "_AUTH_TOKEN" in os.environ:
            headers["Authorization"] = f"Bearer {os.environ['_AUTH_TOKEN']}"

        data = {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, how can you help me today?",
                    "timestamp": "2025-01-01T00:00:00Z",
                }
            ],
            "stream": False,
        }

        start_time = time.time()
        with self.client.post(
            "/api/v1/chat/completions",
            headers=headers,
            json=data,
            catch_response=True,
            name="/api/v1/chat/completions",
        ) as response:
            if response.status_code == 200:
                try:
                    result = response.json()
                    # Verify we got a valid response
                    if "content" in result or "role" in result:
                        response.success()
                    else:
                        response.failure("Invalid response format")
                except json.JSONDecodeError:
                    response.failure("Failed to parse JSON response")
            elif response.status_code == 401:
                # Auth failure is expected if no token is provided
                logger.warning("Authentication required for chat endpoint")
                response.success()  # Don't fail the load test for auth issues
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(2)  # Weight of 2
    def list_conversations(self) -> None:
        """Simulates listing conversations."""
        headers = {"Content-Type": "application/json"}

        # Use the auth token if available
        if "_AUTH_TOKEN" in os.environ:
            headers["Authorization"] = f"Bearer {os.environ['_AUTH_TOKEN']}"

        with self.client.get(
            "/api/v1/chat/conversations",
            headers=headers,
            catch_response=True,
            name="/api/v1/chat/conversations",
        ) as response:
            if response.status_code == 200:
                try:
                    result = response.json()
                    # Verify we got a valid response
                    if "conversations" in result or isinstance(result, list):
                        response.success()
                    else:
                        response.failure("Invalid response format")
                except json.JSONDecodeError:
                    response.failure("Failed to parse JSON response")
            elif response.status_code == 401:
                # Auth failure is expected if no token is provided
                logger.warning("Authentication required for conversations endpoint")
                response.success()  # Don't fail the load test for auth issues
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task
    def chat_health(self) -> None:
        """Check the chat health endpoint."""
        with self.client.get(
            "/api/v1/chat/health",
            catch_response=True,
            name="/api/v1/chat/health",
        ) as response:
            if response.status_code == 200:
                try:
                    result = response.json()
                    if "status" in result:
                        response.success()
                    else:
                        response.failure("Invalid health response format")
                except json.JSONDecodeError:
                    response.failure("Failed to parse JSON response")
            else:
                response.failure(
                    f"Chat health check failed with status {response.status_code}"
                )
