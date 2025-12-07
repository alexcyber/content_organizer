"""
Unit tests for filename parser.

Tests various naming conventions and edge cases.
"""

import pytest

from parsers.filename_parser import FilenameParser, ParsedMedia


class TestFilenameParser:
    """Test cases for FilenameParser."""

    def test_tv_show_dot_separator(self):
        """Test parsing TV show with dot separators."""
        result = FilenameParser.parse("The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv")

        assert result.is_tv_show is True
        assert result.title == "The Pitt"
        assert result.season == 1
        assert result.episode == 10
        assert result.quality == "1080p"

    def test_tv_show_space_separator(self):
        """Test parsing TV show with space separators."""
        result = FilenameParser.parse("The Pitt S01E13 7 00 P M 1080p WEBRip.mkv")

        assert result.is_tv_show is True
        assert result.title == "The Pitt"
        assert result.season == 1
        assert result.episode == 13

    def test_tv_show_with_site_prefix(self):
        """Test parsing TV show with site prefix."""
        result = FilenameParser.parse(
            "www.UIndex.org    -    The Pitt S01E13 7 00 P M 1080p WEBRip HDR10 10Bit"
        )

        assert result.is_tv_show is True
        assert result.title == "The Pitt"
        assert result.season == 1
        assert result.episode == 13

    def test_tv_show_folder_structure(self):
        """Test parsing TV show from folder name."""
        result = FilenameParser.parse("Spartacus.House.of.Ashur.S01E01.1080p.WEB.H264-SYLiX")

        assert result.is_tv_show is True
        assert result.title == "Spartacus House Of Ashur"
        assert result.season == 1
        assert result.episode == 1

    def test_tv_show_alternate_pattern(self):
        """Test parsing TV show with alternate season/episode pattern."""
        result = FilenameParser.parse("Breaking.Bad.1x01.Pilot.720p.mkv")

        assert result.is_tv_show is True
        assert result.title == "Breaking Bad"
        assert result.season == 1
        assert result.episode == 1

    def test_movie_with_year(self):
        """Test parsing movie with year."""
        result = FilenameParser.parse("1917.2019.1080p.AMZN.WEB-DL.DDP5.1.H.264-TEPES.mkv")

        assert result.is_tv_show is False
        assert result.title == "1917"
        assert result.year == 2019
        assert result.quality == "1080p"

    def test_movie_simple(self):
        """Test parsing simple movie filename."""
        result = FilenameParser.parse("12.Angry.Men.1957.720p.BRrip.x264.YIFY.mp4")

        assert result.is_tv_show is False
        assert result.title == "12 Angry Men"
        assert result.year == 1957
        assert result.quality == "720p"

    def test_movie_with_multiple_years(self):
        """Test parsing movie with multiple year matches (uses first)."""
        result = FilenameParser.parse("Back.to.the.Future.1985.2015.Special.Edition.mkv")

        assert result.is_tv_show is False
        assert result.title == "Back To The Future"
        assert result.year == 1985

    def test_normalize_title(self):
        """Test title normalization for fuzzy matching."""
        title1 = "The Pitt"
        title2 = "the-pitt"
        title3 = "THE PITT!!!"

        norm1 = FilenameParser.normalize_title(title1)
        norm2 = FilenameParser.normalize_title(title2)
        norm3 = FilenameParser.normalize_title(title3)

        assert norm1 == norm2 == norm3 == "the pitt"

    def test_quality_extraction(self):
        """Test various quality formats."""
        test_cases = [
            ("Show.S01E01.2160p.mkv", "2160p"),
            ("Show.S01E01.4K.mkv", "4K"),
            ("Show.S01E01.720p.WEB-DL.mkv", "720p"),
            ("Show.S01E01.BluRay.mkv", "BluRay"),
        ]

        for filename, expected_quality in test_cases:
            result = FilenameParser.parse(filename)
            assert result.quality == expected_quality

    def test_release_group_extraction(self):
        """Test release group extraction."""
        result = FilenameParser.parse("Show.S01E01.1080p-ETHEL.mkv")
        assert result.release_group == "ETHEL"

        result2 = FilenameParser.parse("Show.S01E01.1080p[YIFY].mkv")
        assert result2.release_group == "YIFY"

    def test_complex_title_cleanup(self):
        """Test cleaning complex titles with junk patterns."""
        result = FilenameParser.parse(
            "The.Walking.Dead.S10E01.1080p.WEB.H264.AAC.DDP5.1.HEVC.10Bit-AMZN.mkv"
        )

        assert result.title == "The Walking Dead"
        assert "HEVC" not in result.title
        assert "AAC" not in result.title
        assert "AMZN" not in result.title

    def test_edge_case_single_digit_season_episode(self):
        """Test single digit season/episode numbers."""
        result = FilenameParser.parse("Show.S1E5.mkv")

        assert result.season == 1
        assert result.episode == 5

    def test_edge_case_no_extension(self):
        """Test filename without extension."""
        result = FilenameParser.parse("The.Office.S01E01.1080p")

        assert result.is_tv_show is True
        assert result.title == "The Office"

    def test_site_suffix_removal(self):
        """Test removal of site suffixes."""
        result = FilenameParser.parse("Show.S01E01[EZTVx.to].mkv")

        assert "EZTVx" not in result.title
        assert "to" not in result.title

    @pytest.mark.parametrize("filename,expected_title", [
        ("The.Mandalorian.S01E01.mkv", "The Mandalorian"),
        ("better.call.saul.s01e01.mkv", "Better Call Saul"),
        ("GAME_OF_THRONES_S01E01.mkv", "Game Of Thrones"),
        ("Mr.Robot.S01E01.mkv", "Mr Robot"),
    ])
    def test_various_separators(self, filename, expected_title):
        """Test handling of various separator styles."""
        result = FilenameParser.parse(filename)
        assert result.title == expected_title
