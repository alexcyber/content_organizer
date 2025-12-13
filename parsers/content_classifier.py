"""
Content classifier for determining media type and TV show status.

Uses TheTVDB API to determine if TV shows are currently airing or concluded.
Falls back to default behavior when API is unavailable.
"""

from enum import Enum
from typing import Optional
import time

import requests

import config
from utils.cache import SimpleCache
from utils.logger import get_logger

logger = get_logger()


class ShowStatus(Enum):
    """TV show airing status."""

    CURRENT = "current"
    CONCLUDED = "concluded"
    UNKNOWN = "unknown"


class TVDBClient:
    """Client for TheTVDB API v4 interactions."""

    def __init__(self, api_key: str = config.TVDB_API_KEY, quiet: bool = False):
        """
        Initialize TheTVDB client.

        Args:
            api_key: TheTVDB API key
            quiet: If True, store log messages instead of logging them
        """
        self.api_key = api_key
        self.base_url = config.TVDB_BASE_URL
        self.cache = SimpleCache()
        self.enabled = bool(api_key)
        self.token = None
        self.token_expiry = 0
        self.quiet = quiet
        # Store last log message for caller to use when quiet=True
        self.last_status_log: Optional[str] = None

        if not self.enabled:
            logger.warning("TheTVDB API key not configured - status checks disabled")
        else:
            # Get initial auth token
            self._authenticate()

    def _authenticate(self):
        """
        Authenticate with TheTVDB API and obtain bearer token.
        Token is valid for approximately 30 days.
        """
        try:
            url = f"{self.base_url}/login"
            payload = {"apikey": self.api_key}

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            data = response.json()
            self.token = data.get("data", {}).get("token")

            if self.token:
                # Token expires in ~30 days, set expiry to 29 days to be safe
                self.token_expiry = time.time() + (29 * 24 * 60 * 60)
                logger.debug("TheTVDB authentication successful")
            else:
                logger.error("TheTVDB authentication failed - no token received")
                self.enabled = False

        except requests.RequestException as e:
            logger.error(f"TheTVDB authentication error: {e}")
            self.enabled = False

    def _ensure_authenticated(self):
        """Ensure we have a valid authentication token."""
        if not self.enabled:
            return False

        # Check if token is expired or about to expire
        if not self.token or time.time() >= self.token_expiry:
            logger.info("TheTVDB token expired, re-authenticating...")
            self._authenticate()

        return self.enabled and self.token is not None

    def _get_headers(self) -> dict:
        """Get headers with bearer token for API requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_show_status(self, title: str, year: Optional[int] = None) -> ShowStatus:
        """
        Determine if a TV show is currently airing or concluded.

        Args:
            title: Show title
            year: Optional year to help with matching

        Returns:
            ShowStatus enum value
        """
        if not self._ensure_authenticated():
            logger.warning(f"TheTVDB disabled - defaulting '{title}' to CURRENT")
            return ShowStatus.CURRENT

        # Check cache first
        cache_key = f"show_status_{title}_{year or 'unknown'}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for '{title}'")
            return ShowStatus(cached)

        try:
            # Search for TV show
            show_id = self._search_tv_show(title, year)
            if show_id is None:
                logger.warning(f"Show '{title}' not found on TheTVDB - defaulting to CURRENT")
                status = ShowStatus.UNKNOWN
            else:
                # Get show details
                details = self._get_tv_show_details(show_id)
                status = self._determine_status(details)
                log_msg = f"TheTVDB: '{title}' status = {status.value.upper()}"
                self.last_status_log = log_msg

            # Cache result
            self.cache.set(cache_key, status.value)
            return status

        except requests.RequestException as e:
            logger.error(f"TheTVDB API error for '{title}': {e}")
            return ShowStatus.UNKNOWN

    def _search_tv_show(self, title: str, year: Optional[int] = None) -> Optional[int]:
        """
        Search for TV show on TheTVDB and return ID.

        Args:
            title: Show title
            year: Optional year to narrow search

        Returns:
            TheTVDB show ID or None if not found
        """
        url = f"{self.base_url}/search"
        params = {
            "query": title,
            "type": "series"
        }
        if year:
            params["year"] = year

        response = requests.get(url, params=params, headers=self._get_headers(), timeout=10)
        response.raise_for_status()

        data = response.json()
        results = data.get("data", [])

        if not results:
            return None

        # Return first result (most relevant)
        # TheTVDB returns tvdb_id as string
        series_id = results[0].get("tvdb_id")
        return int(series_id) if series_id else None

    def _get_tv_show_details(self, show_id: int) -> dict:
        """
        Get detailed information about a TV show.

        Args:
            show_id: TheTVDB show ID

        Returns:
            Show details dictionary
        """
        # Use extended endpoint for full details including status
        url = f"{self.base_url}/series/{show_id}/extended"

        response = requests.get(url, headers=self._get_headers(), timeout=10)
        response.raise_for_status()

        data = response.json()
        return data.get("data", {})

    def _determine_status(self, details: dict) -> ShowStatus:
        """
        Determine show status from TheTVDB details.

        Args:
            details: TheTVDB show details

        Returns:
            ShowStatus enum value
        """
        # TheTVDB has a status object with id and name
        status_obj = details.get("status", {})

        # Try to get status name or id
        status_name = status_obj.get("name", "").lower() if isinstance(status_obj, dict) else str(status_obj).lower()
        status_id = status_obj.get("id") if isinstance(status_obj, dict) else None

        # TheTVDB status values:
        # - "Continuing" / "Ongoing" = currently airing
        # - "Ended" = concluded
        # Status IDs: 1=Continuing, 2=Ended (based on common usage)

        if status_name in ["ended", "canceled", "cancelled"] or status_id == 2:
            return ShowStatus.CONCLUDED
        elif status_name in ["continuing", "ongoing"] or status_id == 1:
            return ShowStatus.CURRENT
        else:
            # Default to current if status is unclear
            logger.warning(f"Unknown TheTVDB status '{status_name}' (id: {status_id}) - defaulting to CURRENT")
            return ShowStatus.CURRENT


class ContentClassifier:
    """Classifier for determining content type and destination."""

    def __init__(self, quiet: bool = False):
        """
        Initialize classifier with TheTVDB client.

        Args:
            quiet: If True, store log messages instead of logging them
        """
        self.quiet = quiet
        self.tvdb_client = TVDBClient(quiet=quiet)

    @property
    def last_status_log(self) -> Optional[str]:
        """Get the last status log message from TheTVDB client."""
        return self.tvdb_client.last_status_log

    def classify_content(
        self,
        title: str,
        is_tv_show: bool,
        year: Optional[int] = None
    ) -> dict:
        """
        Classify content and determine destination directory.

        Args:
            title: Media title
            is_tv_show: Whether content is a TV show
            year: Optional year

        Returns:
            Dictionary with classification results:
            {
                "type": "movie" or "tv_show",
                "status": ShowStatus (if TV show),
                "destination": destination directory path
            }
        """
        if not is_tv_show:
            return {
                "type": "movie",
                "status": None,
                "destination": config.MOVIE_DIR
            }

        # For TV shows, determine status
        status = self.tvdb_client.get_show_status(title, year)

        # Default to CURRENT if status is unknown
        if status == ShowStatus.UNKNOWN:
            status = ShowStatus.CURRENT
            logger.warning(f"Unknown status for '{title}' - using CURRENT")

        destination = (
            config.TV_CURRENT_DIR if status == ShowStatus.CURRENT
            else config.TV_CONCLUDED_DIR
        )

        return {
            "type": "tv_show",
            "status": status,
            "destination": destination
        }
