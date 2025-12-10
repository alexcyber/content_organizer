"""
Filename parser for extracting metadata from media filenames.

Handles inconsistent naming conventions including:
- Dot separators (The.Pitt.S01E10)
- Space separators (The Pitt S01E10)
- Mixed case
- Release group tags
- Quality indicators
- Site prefixes/suffixes
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ParsedMedia:
    """Structured representation of parsed media filename."""

    title: str
    season: Optional[int] = None
    episode: Optional[int] = None
    year: Optional[int] = None
    quality: Optional[str] = None
    release_group: Optional[str] = None
    is_tv_show: bool = False

    def __str__(self) -> str:
        """String representation for logging."""
        if self.is_tv_show:
            if self.episode is not None:
                return f'TV Show - "{self.title}" S{self.season:02d}E{self.episode:02d}'
            elif self.season is not None:
                return f'TV Show - "{self.title}" S{self.season:02d} (Season Pack)'
            else:
                return f'TV Show - "{self.title}"'
        return f'Movie - "{self.title}"' + (f' ({self.year})' if self.year else '')


class FilenameParser:
    """Parser for extracting metadata from media filenames."""

    # Season/Episode patterns (ordered by specificity)
    SE_PATTERNS = [
        re.compile(r'[Ss](\d{1,2})[Ee](\d{1,3})'),  # S01E01, s1e1, S01E186 (supports up to 3-digit episodes)
        re.compile(r'(\d{1,2})[xX](\d{1,3})'),      # 1x01, 1X01, 1x186
        re.compile(r'[Ss]eason[\s._-]?(\d{1,2})[\s._-]?[Ee]pisode[\s._-]?(\d{1,3})'),  # Season 1 Episode 1
    ]

    # Season-only patterns (for season packs/complete series)
    # These indicate TV shows even without episode numbers
    SEASON_ONLY_PATTERNS = [
        # S01, S11 (must be followed by space, dot, dash, or end of string to avoid matching S01E01)
        re.compile(r'\b[Ss](\d{1,2})(?:\s+|[\._-]+|$)(?![Ee]\d)'),
        # S01-S05, S01-S02, S1-5, s1->s5
        re.compile(r'\b[Ss](\d{1,2})(?:[\s._-]*[-–>]+[\s._-]*[Ss]?\d{1,2})+'),
        # Season 01, Season01, Season 1
        re.compile(r'\b[Ss]eason[\s._-]?(\d{1,2})\b'),
        # Season 1-5, Season 01-05
        re.compile(r'\b[Ss]eason[\s._-]?\d{1,2}[\s._-]*-[\s._-]*\d{1,2}'),
        # Complete Series, Complete Season, Full Season
        re.compile(r'\b(?:Complete|Full|Entire)[\s._-]+(?:Series|Seasons?)\b', re.IGNORECASE),
        # S01-S02-S03 (multiple seasons)
        re.compile(r'\b[Ss]\d{1,2}(?:[\s._-]*-[\s._-]*[Ss]\d{1,2}){2,}'),
    ]

    # Year pattern (4 digits, typically 1900-2099)
    YEAR_PATTERN = re.compile(r'(?:19|20)\d{2}')

    # Quality indicators
    QUALITY_PATTERN = re.compile(
        r'(2160p|1080p|720p|480p|4K|UHD|HDR|HDR10|WEB-?DL|WEBRip|BluRay|BRrip|BDRip|DVDRip)',
        re.IGNORECASE
    )

    # Release group (typically at end in brackets or after dash)
    RELEASE_GROUP_PATTERN = re.compile(
        r'[-\[]([a-zA-Z0-9]+)(?:\]|\[.*?\])?$'
    )

    # Site prefixes/suffixes to remove
    SITE_PATTERNS = [
        re.compile(r'^www\.[a-zA-Z0-9]+\.(org|com|net)[\s._-]+', re.IGNORECASE),
        re.compile(r'^\[[a-zA-Z0-9._-]+\]', re.IGNORECASE),  # [eztv.re], [rarbg], etc.
        re.compile(r'[\s._-]+\[?[a-zA-Z0-9]*\.to\]?', re.IGNORECASE),
    ]

    # Common quality and release info to strip from title
    JUNK_PATTERNS = [
        re.compile(r'\b(HEVC|x264|x265|h\.?264|h\.?265|10[Bb]it|8[Bb]it)\b', re.IGNORECASE),
        re.compile(r'\b(DDP5\.1|DD5\.1|AAC|AC3|Atmos|TrueHD)\b', re.IGNORECASE),
        re.compile(r'\b(AMZN|NF|DSNP|HMAX|ATVP)\b', re.IGNORECASE),
    ]

    @classmethod
    def parse(cls, filename: str) -> ParsedMedia:
        """
        Parse filename and extract media metadata.

        Args:
            filename: Filename or folder name to parse

        Returns:
            ParsedMedia object with extracted information
        """
        original = filename

        # Remove file extension
        filename = re.sub(r'\.[a-zA-Z0-9]{2,4}$', '', filename)

        # Remove site prefixes/suffixes
        for pattern in cls.SITE_PATTERNS:
            filename = pattern.sub('', filename)

        # Extract season/episode
        season, episode = cls._extract_season_episode(filename)
        is_tv_show = season is not None and episode is not None

        # Check for season packs if not already identified as TV show
        if not is_tv_show:
            is_season_pack = cls._is_season_pack(filename)
            if is_season_pack:
                is_tv_show = True
                # Try to extract season from season pack patterns
                if season is None:
                    season = cls._extract_season_from_pack(filename)

        # Extract year
        year = cls._extract_year(filename)

        # Extract quality
        quality = cls._extract_quality(filename)

        # Extract release group
        release_group = cls._extract_release_group(filename)

        # Clean up filename to get title
        title = cls._extract_title(filename, season, episode, year, quality, release_group)

        return ParsedMedia(
            title=title,
            season=season,
            episode=episode,
            year=year,
            quality=quality,
            release_group=release_group,
            is_tv_show=is_tv_show
        )

    @classmethod
    def _extract_season_episode(cls, filename: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract season and episode numbers."""
        for pattern in cls.SE_PATTERNS:
            match = pattern.search(filename)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))
                return season, episode
        return None, None

    @classmethod
    def _extract_year(cls, filename: str) -> Optional[int]:
        """Extract year from filename."""
        matches = cls.YEAR_PATTERN.findall(filename)
        if not matches:
            return None

        # If there's only one year, use it
        if len(matches) == 1:
            return int(matches[0])

        # If there are multiple years, check if the first match is at the start
        # (which likely means it's part of the title, e.g., "1917")
        first_year_match = re.search(cls.YEAR_PATTERN, filename)
        if first_year_match and first_year_match.start() < 10:  # Near the beginning
            # First year is likely the title, use the second year
            return int(matches[1]) if len(matches) > 1 else int(matches[0])
        else:
            # First year is likely the release year
            return int(matches[0])

    @classmethod
    def _extract_quality(cls, filename: str) -> Optional[str]:
        """
        Extract quality indicator from filename.

        Prefers resolution indicators (1080p, 720p, etc.) over source indicators (BluRay, WEB-DL, etc.).
        """
        # Try to find all quality matches
        all_matches = cls.QUALITY_PATTERN.findall(filename)

        if not all_matches:
            return None

        # Resolution patterns to prefer (in order of preference)
        resolution_patterns = ['2160p', '4K', 'UHD', '1080p', '720p', '480p']

        # Check if any resolution patterns are present
        for resolution in resolution_patterns:
            for match in all_matches:
                if match.lower() == resolution.lower():
                    return match

        # If no resolution found, return the first quality match (source type)
        return all_matches[0]

    @classmethod
    def _extract_release_group(cls, filename: str) -> Optional[str]:
        """Extract release group from filename."""
        match = cls.RELEASE_GROUP_PATTERN.search(filename)
        if match:
            return match.group(1)
        return None

    @classmethod
    def _is_season_pack(cls, filename: str) -> bool:
        """
        Check if filename indicates a season pack or complete series.

        Args:
            filename: Filename to check

        Returns:
            True if filename matches season pack patterns
        """
        for pattern in cls.SEASON_ONLY_PATTERNS:
            if pattern.search(filename):
                return True
        return False

    @classmethod
    def _extract_season_from_pack(cls, filename: str) -> Optional[int]:
        """
        Extract season number from season pack patterns.

        Args:
            filename: Filename to extract season from

        Returns:
            Season number if found, None otherwise
        """
        # Try patterns with capture groups first
        for pattern in cls.SEASON_ONLY_PATTERNS:
            match = pattern.search(filename)
            if match:
                # Check if pattern has a capture group for season number
                try:
                    if match.groups():
                        return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None

    @classmethod
    def _extract_title(
        cls,
        filename: str,
        season: Optional[int],
        episode: Optional[int],
        year: Optional[int],
        quality: Optional[str],
        release_group: Optional[str]
    ) -> str:
        """
        Extract and clean title from filename.

        Removes season/episode patterns, quality info, release groups, etc.
        """
        title = filename

        # Remove season/episode patterns and everything after them for TV shows
        for pattern in cls.SE_PATTERNS:
            match = pattern.search(title)
            if match:
                # Keep only the part before the season/episode pattern
                title = title[:match.start()]
                break

        # If no episode pattern, check for season pack patterns
        if not (season and episode):
            # Try to find the earliest season pack pattern match
            earliest_match = None
            for pattern in cls.SEASON_ONLY_PATTERNS:
                match = pattern.search(title)
                if match:
                    if earliest_match is None or match.start() < earliest_match.start():
                        earliest_match = match

            if earliest_match:
                # Keep only the part before the season pack pattern
                title = title[:earliest_match.start()]

        # If no S/E pattern but we have year, find last year occurrence to cut title
        if not (season and episode) and year:
            # Find all year matches in title
            year_matches = list(cls.YEAR_PATTERN.finditer(title))
            if year_matches:
                # Use the last year occurrence as the cut-off point
                last_year_match = year_matches[-1]
                title = title[:last_year_match.start()]

        # Store title before year removal in case it IS a year (e.g., "1917")
        title_with_years = title

        # Remove any remaining years from the title (in case of multiple years)
        title = cls.YEAR_PATTERN.sub('', title)

        # Remove junk patterns
        for pattern in cls.JUNK_PATTERNS:
            title = pattern.sub('', title)

        # Remove quality indicators
        title = cls.QUALITY_PATTERN.sub('', title)

        # Remove common separators and clean up
        title = re.sub(r'[\._-]+', ' ', title)  # Replace dots, underscores, dashes with spaces
        title = re.sub(r'\s+', ' ', title)      # Collapse multiple spaces
        title = re.sub(r'[^\w\s\'-]', '', title)  # Remove special chars except apostrophes and hyphens
        title = title.strip()

        # If title is empty after cleanup, it means the title was a year (e.g., "1917")
        # Revert to the title with years and clean that up
        if not title:
            title = title_with_years
            title = re.sub(r'[\._-]+', ' ', title)
            title = re.sub(r'\s+', ' ', title)
            title = re.sub(r'[^\w\s\'-]', '', title)
            title = title.strip()

        # Title case for better readability
        title = title.title()

        return title

    @classmethod
    def normalize_title(cls, title: str) -> str:
        """
        Normalize title for fuzzy matching.

        Args:
            title: Title to normalize

        Returns:
            Normalized title (lowercase, no special chars, no extra spaces)
        """
        normalized = title.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)  # Replace special chars with spaces
        normalized = re.sub(r'\s+', ' ', normalized)      # Collapse spaces
        normalized = normalized.strip()
        return normalized
