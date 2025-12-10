"""
Unit tests for filename parser.

Tests various naming conventions and edge cases.
"""

import pytest

from parsers.filename_parser import FilenameParser


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


class TestSeasonPackParsing:
    """Test cases for season pack and complete series parsing."""

    def test_single_season_with_space(self):
        """Test S01 format with space."""
        result = FilenameParser.parse("Firefly S01 1080p DSNP WEB-DL H264 wSubsAudio")

        assert result.is_tv_show is True
        assert result.title == "Firefly"
        assert result.season == 1
        assert result.episode is None
        assert result.quality == "1080p"

    def test_single_season_two_digits(self):
        """Test S11 format (two-digit season)."""
        result = FilenameParser.parse("The Simpsons S11 1080p Web-DL x264-OFT")

        assert result.is_tv_show is True
        assert result.title == "The Simpsons"
        assert result.season == 11
        assert result.episode is None
        assert result.quality == "1080p"

    def test_season_range_standard(self):
        """Test S01-S05 format (season range)."""
        result = FilenameParser.parse(
            "Keeping Up Appearances (1990) S01-S05 + Specials (576p DVD x265 HEVC 10bit AAC 2 0 Ghost)"
        )

        assert result.is_tv_show is True
        assert result.title == "Keeping Up Appearances"
        assert result.season == 1  # Extract first season from range
        assert result.episode is None
        assert result.year == 1990

    def test_season_range_abbreviated(self):
        """Test S1-5 format (abbreviated range)."""
        result = FilenameParser.parse("Breaking Bad S1-5 Complete 1080p BluRay x264")

        assert result.is_tv_show is True
        assert result.title == "Breaking Bad"
        assert result.season == 1
        assert result.episode is None

    def test_season_range_arrow(self):
        """Test s1->s5 format (arrow range)."""
        result = FilenameParser.parse("The Wire s1->s5 Complete Series 720p")

        assert result.is_tv_show is True
        assert result.title == "The Wire"
        assert result.season == 1
        assert result.episode is None

    def test_season_with_dots(self):
        """Test S01 with dot separators."""
        result = FilenameParser.parse("Firefly.S01.1080p.BluRay.x264-ROVERS")

        assert result.is_tv_show is True
        assert result.title == "Firefly"
        assert result.season == 1
        assert result.episode is None

    def test_season_word_format(self):
        """Test 'Season 01' written out."""
        result = FilenameParser.parse("Game of Thrones Season 01 1080p BluRay")

        assert result.is_tv_show is True
        assert result.title == "Game Of Thrones"
        assert result.season == 1
        assert result.episode is None

    def test_season_word_no_space(self):
        """Test 'Season01' without space."""
        result = FilenameParser.parse("The Office Season01 Complete 720p")

        assert result.is_tv_show is True
        assert result.title == "The Office"
        assert result.season == 1
        assert result.episode is None

    def test_season_word_single_digit(self):
        """Test 'Season 1' single digit."""
        result = FilenameParser.parse("Friends Season 1 1080p WEB-DL")

        assert result.is_tv_show is True
        assert result.title == "Friends"
        assert result.season == 1
        assert result.episode is None

    def test_season_word_range(self):
        """Test 'Season 1-5' range format."""
        result = FilenameParser.parse("The Sopranos Season 1-6 Complete 1080p")

        assert result.is_tv_show is True
        assert result.title == "The Sopranos"
        assert result.episode is None

    def test_complete_series(self):
        """Test 'Complete Series' keyword."""
        result = FilenameParser.parse("Breaking Bad Complete Series 1080p BluRay x264")

        assert result.is_tv_show is True
        assert result.title == "Breaking Bad"
        assert result.episode is None

    def test_full_season(self):
        """Test 'Full Season' keyword."""
        result = FilenameParser.parse("The Walking Dead Full Season 720p WEB-DL")

        assert result.is_tv_show is True
        assert result.title == "The Walking Dead"
        assert result.episode is None

    def test_entire_series(self):
        """Test 'Entire Series' keyword."""
        result = FilenameParser.parse("Firefly Entire Series 1080p BluRay")

        assert result.is_tv_show is True
        assert result.title == "Firefly"
        assert result.episode is None

    def test_multiple_season_dash(self):
        """Test S01-S02-S03 format (multiple seasons)."""
        result = FilenameParser.parse("The Mandalorian S01-S02-S03 Complete 2160p")

        assert result.is_tv_show is True
        assert result.title == "The Mandalorian"
        assert result.season == 1
        assert result.episode is None

    def test_season_pack_with_year(self):
        """Test season pack with year in title."""
        result = FilenameParser.parse("Doctor Who (2005) S01 1080p BluRay x264")

        assert result.is_tv_show is True
        assert result.title == "Doctor Who"
        assert result.season == 1
        assert result.episode is None
        assert result.year == 2005

    def test_season_pack_lowercase(self):
        """Test lowercase s01 format."""
        result = FilenameParser.parse("battlestar.galactica.s01.1080p.bluray.x264")

        assert result.is_tv_show is True
        assert result.title == "Battlestar Galactica"
        assert result.season == 1
        assert result.episode is None

    def test_season_pack_with_extras(self):
        """Test season pack with extras mentioned."""
        result = FilenameParser.parse("The Office S02 Complete + Extras 720p WEB-DL")

        assert result.is_tv_show is True
        assert result.title == "The Office"
        assert result.season == 2
        assert result.episode is None

    def test_not_confused_with_episodes(self):
        """Test that S01E01 is still detected as episode, not season pack."""
        result = FilenameParser.parse("The Pitt S01E10 1080p WEB h264-ETHEL.mkv")

        assert result.is_tv_show is True
        assert result.title == "The Pitt"
        assert result.season == 1
        assert result.episode == 10  # Should have episode number

    def test_season_at_end(self):
        """Test season identifier at end of filename."""
        result = FilenameParser.parse("1080p BluRay x264 Firefly S01")

        assert result.is_tv_show is True
        assert result.season == 1
        assert result.episode is None

    @pytest.mark.parametrize("filename,expected_season,expected_title", [
        ("Firefly S01 1080p", 1, "Firefly"),
        ("The Simpsons S11 720p", 11, "The Simpsons"),
        ("Breaking Bad S1-5 Complete", 1, "Breaking Bad"),
        ("The Wire s1->s5", 1, "The Wire"),
        ("Game of Thrones Season 01", 1, "Game Of Thrones"),
        ("Friends Season01", 1, "Friends"),
        ("The Office Season 1", 1, "The Office"),
        ("The Sopranos Season 1-6", None, "The Sopranos"),  # Range without capture
        ("Battlestar Galactica Complete Series", None, "Battlestar Galactica"),
        ("Doctor Who Full Season", None, "Doctor Who"),
        ("Firefly Entire Series", None, "Firefly"),
        ("The Mandalorian S01-S02-S03", 1, "The Mandalorian"),
    ])
    def test_season_pack_variations(self, filename, expected_season, expected_title):
        """Test various season pack naming conventions."""
        result = FilenameParser.parse(filename)
        assert result.is_tv_show is True
        assert result.episode is None
        if expected_season is not None:
            assert result.season == expected_season
        assert result.title == expected_title


class TestRealWorldTorrentNames:
    """Test cases for real-world torrent names from private trackers."""

    def test_episode_with_episode_title(self):
        """Test episode with episode title in filename."""
        result = FilenameParser.parse(
            "7 Little Johnstons S16E08 What the Duck 1080p HMax WEB-DL DDP2 0 H 265-STC"
        )

        assert result.is_tv_show is True
        assert result.title == "7 Little Johnstons"
        assert result.season == 16
        assert result.episode == 8
        assert result.quality == "1080p"

    def test_high_season_number(self):
        """Test TV show with very high season number."""
        result = FilenameParser.parse(
            "The Young and the Restless S53E44 1080p WEB h264-DiRT"
        )

        assert result.is_tv_show is True
        assert result.title == "The Young And The Restless"
        assert result.season == 53
        assert result.episode == 44
        assert result.quality == "1080p"

    def test_high_episode_number(self):
        """Test episode with 3-digit episode number."""
        result = FilenameParser.parse(
            "Beyond the Gates S01E186 720p WEB h264-NoRBiT"
        )

        assert result.is_tv_show is True
        assert result.title == "Beyond The Gates"
        assert result.season == 1
        assert result.episode == 186
        assert result.quality == "720p"

    def test_special_episode_s00(self):
        """Test special episode (S00) notation."""
        result = FilenameParser.parse(
            "Better Call Saul S00E11 1080p AMZN WEB-DL DD+ 2 0 H 264-WELP"
        )

        assert result.is_tv_show is True
        assert result.title == "Better Call Saul"
        assert result.season == 0
        assert result.episode == 11
        assert result.quality == "1080p"

    def test_season_pack_with_year_in_title(self):
        """Test season pack with year in show title."""
        result = FilenameParser.parse(
            "Doctor Who 2005 S07 1080p HMAX WEB-DL DD 5 1 H 264-SLiGNOME"
        )

        assert result.is_tv_show is True
        assert result.title == "Doctor Who"
        assert result.season == 7
        assert result.episode is None
        assert result.year == 2005
        assert result.quality == "1080p"

    def test_season_pack_with_repack(self):
        """Test season pack with REPACK tag."""
        result = FilenameParser.parse(
            "The Secret Lives of Mormon Wives S03 REPACK 1080p DSNP WEB-DL DD+ 5 1 H 264-BLOOM"
        )

        assert result.is_tv_show is True
        assert result.title == "The Secret Lives Of Mormon Wives"
        assert result.season == 3
        assert result.episode is None
        assert result.quality == "1080p"

    def test_season_pack_high_season(self):
        """Test season pack with high season number."""
        result = FilenameParser.parse(
            "Law and Order S24 1080p x265-ELiTE"
        )

        assert result.is_tv_show is True
        assert result.title == "Law And Order"
        assert result.season == 24
        assert result.episode is None
        assert result.quality == "1080p"

    def test_season_pack_with_year_parentheses(self):
        """Test season pack with year in parentheses."""
        result = FilenameParser.parse(
            "The Boulet Brothers Dragula Titans (2022) S02 1080p WEB x265"
        )

        assert result.is_tv_show is True
        assert result.title == "The Boulet Brothers Dragula Titans"
        assert result.season == 2
        assert result.episode is None
        assert result.year == 2022
        assert result.quality == "1080p"

    def test_season_pack_with_region(self):
        """Test season pack with region tag (NORDiC)."""
        result = FilenameParser.parse(
            "A Confession 2019 S01 NORDiC 1080p WEB-DL H 264-BlowMe"
        )

        assert result.is_tv_show is True
        assert result.title == "A Confession"
        assert result.season == 1
        assert result.episode is None
        assert result.year == 2019
        assert result.quality == "1080p"

    def test_season_pack_complex_release_info(self):
        """Test season pack with complex release group info."""
        result = FilenameParser.parse(
            "American Dad (2005) S15 (1080p DSNP Webrip x265 10bit EAC3 5 1 - Goki)[TAoE]"
        )

        assert result.is_tv_show is True
        assert result.title == "American Dad"
        assert result.season == 15
        assert result.episode is None
        assert result.year == 2005
        assert result.quality == "1080p"

    def test_movie_recent_year(self):
        """Test movie with recent year (2025)."""
        result = FilenameParser.parse(
            "Rabbit Trap 2025 1080p BluRay H264-RiSEHD"
        )

        assert result.is_tv_show is False
        assert result.title == "Rabbit Trap"
        assert result.year == 2025
        assert result.quality == "1080p"
        assert result.season is None
        assert result.episode is None

    def test_movie_with_remux(self):
        """Test movie with REMUX in filename."""
        result = FilenameParser.parse(
            "The House with a Clock in Its Walls 2018 1080p BluRay REMUX AVC TrueHD 7 1 Atmos-PmP"
        )

        assert result.is_tv_show is False
        assert result.title == "The House With A Clock In Its Walls"
        assert result.year == 2018
        assert result.quality == "1080p"

    def test_movie_old_year(self):
        """Test movie with old year (1970s)."""
        result = FilenameParser.parse(
            "The Honeymoon Killers 1970 Criterion 1080p BluRay REMUX AVC LPCM 1 0-UBits"
        )

        assert result.is_tv_show is False
        assert result.title == "The Honeymoon Killers"
        assert result.year == 1970
        assert result.quality == "1080p"

    def test_movie_with_parentheses_year(self):
        """Test movie with year in parentheses."""
        result = FilenameParser.parse(
            "Blown Away (1994) BluRay 1080p REMUX AVC DTS-HD MA 5 1"
        )

        assert result.is_tv_show is False
        assert result.title == "Blown Away"
        assert result.year == 1994
        assert result.quality == "1080p"

    def test_movie_title_ending_with_movie(self):
        """Test movie with 'Movie' in title."""
        result = FilenameParser.parse(
            "Mrs Browns Boys D Movie 2014 1080p BluRay H264-RMX"
        )

        assert result.is_tv_show is False
        assert result.title == "Mrs Browns Boys D Movie"
        assert result.year == 2014
        assert result.quality == "1080p"

    def test_date_based_show_not_episode(self):
        """Test date-based show (should not be detected as TV episode)."""
        result = FilenameParser.parse(
            "The Price Is Right 2025 12 09 1080p WEB h264-DiRT"
        )

        # Date format (2025 12 09) doesn't match S##E## pattern
        # The year 2025 might be detected as a year
        assert result.is_tv_show is False
        assert result.season is None
        assert result.episode is None

    def test_date_based_show_lets_make_deal(self):
        """Test another date-based show."""
        result = FilenameParser.parse(
            "Lets Make A Deal 2025 12 09 720p WEB h264-DiRT"
        )

        assert result.is_tv_show is False
        assert result.season is None
        assert result.episode is None
        assert result.quality == "720p"

    def test_4k_quality_detection(self):
        """Test 2160p (4K) quality detection."""
        result = FilenameParser.parse(
            "The Secret Lives of Mormon Wives S03 REPACK 2160p DSNP WEB-DL DD+ 5 1 H 265-BLOOM"
        )

        assert result.is_tv_show is True
        assert result.season == 3
        assert result.quality == "2160p"

    def test_movie_with_number_in_title(self):
        """Test movie with number in title (Sing 2)."""
        result = FilenameParser.parse(
            "Sing 2 2021 BluRay 1080p DDP Atmos 5 1 x264-hallowed"
        )

        assert result.is_tv_show is False
        assert result.title == "Sing 2"
        assert result.year == 2021
        assert result.quality == "1080p"
        assert result.season is None
        assert result.episode is None

    def test_movie_very_old_1929(self):
        """Test very old movie from 1929."""
        result = FilenameParser.parse(
            "The Cocoanuts 1929 1080p BluRay x264-OFT"
        )

        assert result.is_tv_show is False
        assert result.title == "The Cocoanuts"
        assert result.year == 1929
        assert result.quality == "1080p"

    def test_movie_with_exclamation_mark(self):
        """Test movie with special character (exclamation mark) in title."""
        result = FilenameParser.parse(
            "The Naked Gun From the Files of Police Squad! 1988 1080p CAN Blu-ray AVC DTS-HD MA 5 1-nukmasta"
        )

        assert result.is_tv_show is False
        assert result.title == "The Naked Gun From The Files Of Police Squad"
        assert result.year == 1988
        assert result.quality == "1080p"

    def test_movie_complete_bluray_tag(self):
        """Test movie with COMPLETE BLURAY tag."""
        result = FilenameParser.parse(
            "The Prestige 2006 COMPLETE BLURAY iNTERNAL-OLDHAM"
        )

        assert result.is_tv_show is False
        assert result.title == "The Prestige"
        assert result.year == 2006
        assert result.season is None
        assert result.episode is None

    def test_movie_internal_tag(self):
        """Test movie with iNTERNAL tag."""
        result = FilenameParser.parse(
            "Morvern Callar 2002 iNTERNAL BDRip x264-MANiC"
        )

        assert result.is_tv_show is False
        assert result.title == "Morvern Callar"
        assert result.year == 2002

    def test_movie_2160p_hdr(self):
        """Test 2160p (4K) movie with HDR."""
        result = FilenameParser.parse(
            "The House with a Clock in Its Walls 2018 2160p MA WEB-DL DD+ 5 1 HDR H 265-HHWEB"
        )

        assert result.is_tv_show is False
        assert result.title == "The House With A Clock In Its Walls"
        assert result.year == 2018
        assert result.quality == "2160p"

    def test_movie_with_distributor_kino(self):
        """Test movie with distributor name (Kino) in filename."""
        result = FilenameParser.parse(
            "The Cold Blue 2018 Kino 1080p BluRay x264-OFT"
        )

        assert result.is_tv_show is False
        assert result.title == "The Cold Blue"
        assert result.year == 2018
        assert result.quality == "1080p"

    def test_movie_long_title(self):
        """Test movie with long, complex title."""
        result = FilenameParser.parse(
            "The Theory of Everything 2014 1080p TWN Blu-ray AVC DTS-HD MA 5 1-nLiBRA"
        )

        assert result.is_tv_show is False
        assert result.title == "The Theory Of Everything"
        assert result.year == 2014
        assert result.quality == "1080p"

    def test_movie_uhd_bluray(self):
        """Test movie with UHD BluRay tag (UHD takes precedence over 1080p)."""
        result = FilenameParser.parse(
            "The Monkey 2025 1080p UHD BluRay DD+ 5 1 HDR x265-ORBiT"
        )

        assert result.is_tv_show is False
        assert result.title == "The Monkey"
        assert result.year == 2025
        assert result.quality == "UHD"  # UHD has higher priority than 1080p in quality detection

    @pytest.mark.parametrize("filename,expected_is_tv,expected_season,expected_episode,expected_title", [
        # Episodes
        ("7 Little Johnstons S16E08 What the Duck 1080p", True, 16, 8, "7 Little Johnstons"),
        ("The Young and the Restless S53E44 720p WEB", True, 53, 44, "The Young And The Restless"),
        ("The Bold and the Beautiful S39E60 1080p WEB", True, 39, 60, "The Bold And The Beautiful"),
        ("Beyond the Gates S01E186 720p WEB", True, 1, 186, "Beyond The Gates"),
        ("Better Call Saul S00E11 1080p AMZN", True, 0, 11, "Better Call Saul"),
        # Season Packs
        ("The Simpsons S11 1080p Web-DL x264-OFT", True, 11, None, "The Simpsons"),
        ("Doctor Who 2005 S07 1080p HMAX", True, 7, None, "Doctor Who"),
        ("Doctor Who 2005 S01 1080p HMAX", True, 1, None, "Doctor Who"),
        ("Doctor Who 2005 S04 1080p HMAX", True, 4, None, "Doctor Who"),
        ("Law and Order S24 1080p x265", True, 24, None, "Law And Order"),
        ("Law and Order S24 720p x265", True, 24, None, "Law And Order"),
        ("The Boulet Brothers Dragula Titans (2022) S02", True, 2, None, "The Boulet Brothers Dragula Titans"),
        ("A Confession 2019 S01 NORDiC 1080p", True, 1, None, "A Confession"),
        ("American Dad (2005) S15 (1080p DSNP", True, 15, None, "American Dad"),
        # Movies - Original
        ("Native Son 2019 1080p AMZN", False, None, None, "Native Son"),
        ("Rabbit Trap 2025 1080p BluRay", False, None, None, "Rabbit Trap"),
        ("The Shrine 2010 1080p BluRay", False, None, None, "The Shrine"),
        ("Blown Away (1994) BluRay 1080p", False, None, None, "Blown Away"),
        ("The Honeymoon Killers 1970 Criterion", False, None, None, "The Honeymoon Killers"),
        # Movies - Additional variations
        ("Rabbit Trap 2025 720p BluRay x264-KNiVES", False, None, None, "Rabbit Trap"),
        ("Rabbit Trap 2025 1080p BluRay x264-KNiVES", False, None, None, "Rabbit Trap"),
        ("The Revenant 2015 1080p BRA Blu-ray AVC DTS-HD MA 7 1-BAKED", False, None, None, "The Revenant"),
        ("Inconceivable 2017 1080p BluRay REMUX AVC DTS-HD MA 5 1-FraMeSToR", False, None, None, "Inconceivable"),
        ("The Colony 2013 1080p BluRay x264-OFT", False, None, None, "The Colony"),
        ("The Collection 2012 1080p BluRay x264-OFT", False, None, None, "The Collection"),
        ("The Cold Light of Day 2012 1080p BluRay x264-OFT", False, None, None, "The Cold Light Of Day"),
        ("The Cockleshell Heroes 1955 1080p BluRay x264-OFT", False, None, None, "The Cockleshell Heroes"),
        ("The Client 1994 1080p BluRay x264-OFT", False, None, None, "The Client"),
        ("The Clearing 2004 1080p BluRay x264-OFT", False, None, None, "The Clearing"),
        ("The Cleansing Hour 2019 1080p BluRay x264-OFT", False, None, None, "The Cleansing Hour"),
        ("The Cleansing 2019 1080p BluRay x264-OFT", False, None, None, "The Cleansing"),
        ("The Clapper 2017 1080p BluRay x264-OFT", False, None, None, "The Clapper"),
        ("The Cincinnati Kid 1965 1080p BluRay x264-OFT", False, None, None, "The Cincinnati Kid"),
        ("The Cider House Rules 1999 1080p BluRay x264-OFT", False, None, None, "The Cider House Rules"),
        ("The Church 1989 1080p BluRay x264-OFT", False, None, None, "The Church"),
        # Date-based (not episodes)
        ("The Price Is Right 2025 12 09 1080p", False, None, None, "The Price Is Right"),
        ("Lets Make A Deal 2025 12 09 720p", False, None, None, "Lets Make A Deal"),
    ])
    def test_real_world_variations(self, filename, expected_is_tv, expected_season, expected_episode, expected_title):
        """Test batch of real-world torrent naming conventions."""
        result = FilenameParser.parse(filename)
        assert result.is_tv_show == expected_is_tv
        assert result.season == expected_season
        assert result.episode == expected_episode
        assert result.title == expected_title
