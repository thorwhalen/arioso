"""Base adapter class for REST API platforms."""

import time

from arioso._util import make_session


class BaseRestAdapter:
    """Base class providing common infrastructure for REST API adapters.

    Subclasses get a pre-configured ``requests.Session`` with auth
    headers and a polling helper for async generation endpoints.
    """

    def __init__(self, config: dict):
        self.config = config
        self.base_url = config.get("api", {}).get("base_url", "")
        self.session = make_session(config.get("auth", {}))

    def _poll_until_complete(
        self,
        check_url: str,
        *,
        timeout: float = 300,
        poll_interval: float = 5,
        status_key: str = "status",
        complete_value: str = "complete",
    ) -> dict:
        """Poll a status endpoint until completion or timeout.

        Args:
            check_url: URL to GET for status updates.
            timeout: Max seconds to wait.
            poll_interval: Seconds between status checks.
            status_key: JSON key containing the status value.
            complete_value: Value of status_key that means done.

        Returns:
            The final JSON response dict.

        Raises:
            TimeoutError: If generation does not complete in time.
        """
        start = time.time()
        while time.time() - start < timeout:
            response = self.session.get(check_url)
            response.raise_for_status()
            data = response.json()
            if data.get(status_key) == complete_value:
                return data
            time.sleep(poll_interval)
        raise TimeoutError(f"Generation did not complete within {timeout}s")
