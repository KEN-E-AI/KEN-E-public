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

"""Locust load test: Chat sidebar polling (CH-PRD-02 AC-16).

Simulates the sidebar's 5-10 s polling cadence against the conversations list
endpoint.  Each virtual user fetches a Firebase ID token once at startup (via
``chat_load_test_auth.get_id_token()``) and then repeatedly polls
``GET /api/v1/chat/conversations?account_id=acc_load_test``.

Unlike the historical ``load_test.py`` scenario, this file treats **every
non-200 response as a failure** — including 401 — so that the stats CSV
accurately reflects the fraction of unauthenticated or error responses during
a run (CH-24 requirement).

Required environment variables
-------------------------------
FIREBASE_WEB_API_KEY
    Firebase web API key used by ``chat_load_test_auth`` to mint an ID token.
CHAT_LOADTEST_UID
    Firebase Auth UID of the pre-created load-test user.
API_BASE_URL (optional)
    Override the default staging base URL.

Local run
---------
Ensure results directory exists first::

    mkdir -p tests/load_test/.results

Then::

    locust -f tests/load_test/chat_sidebar_polling.py \\
      --headless -t 30s -u 10 -r 2 \\
      --csv=tests/load_test/.results/chat_results \\
      --html=tests/load_test/.results/chat_report.html
"""

import logging
import os
import sys

from locust import HttpUser, between, task

# Import from the sibling module.  Locust is invoked from the repo root, so
# the tests/load_test directory is added to sys.path by the -f flag resolution.
# If running from a different cwd, adjust PYTHONPATH accordingly.
sys.path.insert(0, os.path.dirname(__file__))
import chat_load_test_auth

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ChatSidebarUser(HttpUser):
    """Virtual user that polls the Chat sidebar conversations endpoint.

    The wait time of 5-10 s matches the sidebar polling cadence documented in
    CH-PRD-02 §5.2.
    """

    wait_time = between(5, 10)
    host = os.environ.get(
        "API_BASE_URL", "https://kene-api-staging-391472102753.us-central1.run.app"
    )

    def on_start(self) -> None:
        """Fetch the Firebase ID token once before this user starts polling.

        If the token cannot be obtained (missing env vars, network failure,
        etc.) the entire Locust run is stopped immediately so that hundreds of
        virtual users do not spam the API with unauthenticated requests.
        """
        try:
            self._id_token: str = chat_load_test_auth.get_id_token()
            logger.info("ChatSidebarUser: ID token acquired successfully")
        except RuntimeError as exc:
            logger.error("ChatSidebarUser: failed to acquire ID token — %s", exc)
            self.environment.runner.quit()

    @task
    def poll_conversations(self) -> None:
        """Poll the conversations list endpoint once."""
        headers = {
            "Authorization": f"Bearer {self._id_token}",
            "Content-Type": "application/json",
        }

        with self.client.get(
            "/api/v1/chat/conversations",
            params={"account_id": "acc_load_test"},
            headers=headers,
            catch_response=True,
            name="/api/v1/chat/conversations",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                logger.warning(
                    "poll_conversations: non-200 response — status=%s body=%.120s",
                    response.status_code,
                    response.text,
                )
                response.failure(
                    f"Unexpected status code: {response.status_code}"
                )
