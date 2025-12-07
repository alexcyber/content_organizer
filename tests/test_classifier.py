"""
Unit tests for content classifier.

Tests content classification and TheTVDB integration.
"""

from unittest.mock import Mock, patch

import pytest

import config
from parsers.content_classifier import (ContentClassifier, ShowStatus,
                                        TVDBClient)


class TestTVDBClient:
    """Test cases for TVDBClient."""

    @patch('parsers.content_classifier.requests.post')
    def test_client_disabled_without_api_key(self, mock_post):
        """Test that client is disabled when API key is missing."""
        client = TVDBClient(api_key="")

        assert client.enabled is False
        # Should not attempt authentication
        mock_post.assert_not_called()

    @patch('parsers.content_classifier.requests.post')
    def test_client_enabled_with_api_key(self, mock_post):
        """Test that client is enabled when API key is provided and auth succeeds."""
        # Mock auth response
        auth_response = Mock()
        auth_response.json.return_value = {
            "data": {"token": "test_bearer_token"}
        }
        auth_response.raise_for_status = Mock()
        mock_post.return_value = auth_response

        client = TVDBClient(api_key="test_key")

        assert client.enabled is True
        assert client.token == "test_bearer_token"
        # Should attempt authentication
        mock_post.assert_called_once()

    @patch('parsers.content_classifier.requests.post')
    @patch('parsers.content_classifier.requests.get')
    def test_get_show_status_ended(self, mock_get, mock_post):
        """Test status determination for ended show."""
        # Mock auth response
        auth_response = Mock()
        auth_response.json.return_value = {
            "data": {"token": "test_bearer_token"}
        }
        auth_response.raise_for_status = Mock()
        mock_post.return_value = auth_response

        # Mock search response
        search_response = Mock()
        search_response.json.return_value = {
            "data": [{"tvdb_id": "123", "name": "Breaking Bad"}]
        }
        search_response.raise_for_status = Mock()

        # Mock details response
        details_response = Mock()
        details_response.json.return_value = {
            "data": {
                "id": 123,
                "name": "Breaking Bad",
                "status": {"id": 2, "name": "Ended"}
            }
        }
        details_response.raise_for_status = Mock()

        mock_get.side_effect = [search_response, details_response]

        client = TVDBClient(api_key="test_key")
        status = client.get_show_status("Breaking Bad")

        assert status == ShowStatus.CONCLUDED

    @patch('parsers.content_classifier.requests.post')
    @patch('parsers.content_classifier.requests.get')
    def test_get_show_status_returning(self, mock_get, mock_post):
        """Test status determination for returning series."""
        # Mock auth
        auth_response = Mock()
        auth_response.json.return_value = {"data": {"token": "test_token"}}
        auth_response.raise_for_status = Mock()
        mock_post.return_value = auth_response

        search_response = Mock()
        search_response.json.return_value = {
            "data": [{"tvdb_id": "456", "name": "The Pitt"}]
        }
        search_response.raise_for_status = Mock()

        details_response = Mock()
        details_response.json.return_value = {
            "data": {
                "id": 456,
                "name": "The Pitt",
                "status": {"id": 1, "name": "Continuing"}
            }
        }
        details_response.raise_for_status = Mock()

        mock_get.side_effect = [search_response, details_response]

        client = TVDBClient(api_key="test_key")
        status = client.get_show_status("The Pitt")

        assert status == ShowStatus.CURRENT

    @patch('parsers.content_classifier.requests.post')
    @patch('parsers.content_classifier.requests.get')
    def test_get_show_status_canceled(self, mock_get, mock_post):
        """Test status determination for canceled show."""
        # Mock auth
        auth_response = Mock()
        auth_response.json.return_value = {"data": {"token": "test_token"}}
        auth_response.raise_for_status = Mock()
        mock_post.return_value = auth_response

        search_response = Mock()
        search_response.json.return_value = {
            "data": [{"tvdb_id": "789", "name": "Firefly"}]
        }
        search_response.raise_for_status = Mock()

        details_response = Mock()
        details_response.json.return_value = {
            "data": {
                "id": 789,
                "name": "Firefly",
                "status": {"id": 2, "name": "Canceled"}
            }
        }
        details_response.raise_for_status = Mock()

        mock_get.side_effect = [search_response, details_response]

        client = TVDBClient(api_key="test_key")
        status = client.get_show_status("Firefly")

        assert status == ShowStatus.CONCLUDED

    @patch('parsers.content_classifier.requests.post')
    @patch('parsers.content_classifier.requests.get')
    def test_get_show_status_not_found(self, mock_get, mock_post):
        """Test handling of show not found."""
        # Mock auth
        auth_response = Mock()
        auth_response.json.return_value = {"data": {"token": "test_token"}}
        auth_response.raise_for_status = Mock()
        mock_post.return_value = auth_response

        search_response = Mock()
        search_response.json.return_value = {"data": []}
        search_response.raise_for_status = Mock()

        mock_get.return_value = search_response

        client = TVDBClient(api_key="test_key")
        status = client.get_show_status("Nonexistent Show")

        assert status == ShowStatus.UNKNOWN

    def test_get_show_status_without_api_key(self):
        """Test that disabled client returns CURRENT status."""
        client = TVDBClient(api_key="")
        status = client.get_show_status("Any Show")

        assert status == ShowStatus.CURRENT

    @patch('parsers.content_classifier.requests.post')
    @patch('parsers.content_classifier.requests.get')
    def test_caching(self, mock_get, mock_post):
        """Test that results are cached."""
        # Mock auth
        auth_response = Mock()
        auth_response.json.return_value = {"data": {"token": "test_token"}}
        auth_response.raise_for_status = Mock()
        mock_post.return_value = auth_response

        search_response = Mock()
        search_response.json.return_value = {
            "data": [{"tvdb_id": "123", "name": "Show"}]
        }
        search_response.raise_for_status = Mock()

        details_response = Mock()
        details_response.json.return_value = {
            "data": {
                "id": 123,
                "status": {"id": 2, "name": "Ended"}
            }
        }
        details_response.raise_for_status = Mock()

        mock_get.side_effect = [search_response, details_response]

        client = TVDBClient(api_key="test_key")

        # First call should hit API
        status1 = client.get_show_status("Show")

        # Second call should use cache (no additional API calls)
        status2 = client.get_show_status("Show")

        assert status1 == status2
        assert mock_get.call_count == 2  # Only called once (search + details)


class TestContentClassifier:
    """Test cases for ContentClassifier."""

    def test_classify_movie(self):
        """Test classification of movie."""
        classifier = ContentClassifier()

        result = classifier.classify_content(
            title="The Matrix",
            is_tv_show=False,
            year=1999
        )

        assert result["type"] == "movie"
        assert result["status"] is None
        assert result["destination"] == config.MOVIE_DIR

    @patch.object(TVDBClient, 'get_show_status')
    def test_classify_current_tv_show(self, mock_status):
        """Test classification of current TV show."""
        mock_status.return_value = ShowStatus.CURRENT

        classifier = ContentClassifier()

        result = classifier.classify_content(
            title="The Pitt",
            is_tv_show=True
        )

        assert result["type"] == "tv_show"
        assert result["status"] == ShowStatus.CURRENT
        assert result["destination"] == config.TV_CURRENT_DIR

    @patch.object(TVDBClient, 'get_show_status')
    def test_classify_concluded_tv_show(self, mock_status):
        """Test classification of concluded TV show."""
        mock_status.return_value = ShowStatus.CONCLUDED

        classifier = ContentClassifier()

        result = classifier.classify_content(
            title="Breaking Bad",
            is_tv_show=True
        )

        assert result["type"] == "tv_show"
        assert result["status"] == ShowStatus.CONCLUDED
        assert result["destination"] == config.TV_CONCLUDED_DIR

    @patch.object(TVDBClient, 'get_show_status')
    def test_classify_unknown_defaults_to_current(self, mock_status):
        """Test that unknown status defaults to current."""
        mock_status.return_value = ShowStatus.UNKNOWN

        classifier = ContentClassifier()

        result = classifier.classify_content(
            title="Unknown Show",
            is_tv_show=True
        )

        assert result["type"] == "tv_show"
        assert result["status"] == ShowStatus.CURRENT
        assert result["destination"] == config.TV_CURRENT_DIR
