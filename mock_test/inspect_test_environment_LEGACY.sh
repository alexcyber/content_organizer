#!/bin/bash
# Inspect test environment - Shows current state of test directories

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test_media"

if [ ! -d "$TEST_DIR" ]; then
    echo "ERROR: Test environment not found at $TEST_DIR"
    echo "Run ./setup_test_environment.sh first"
    exit 1
fi

echo "============================================================================"
echo "Test Environment Inspection"
echo "============================================================================"
echo ""
echo "Base Directory: $TEST_DIR"
echo ""

# Downloads
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📥 TV_DOWNLOADS ($TEST_DIR/TV_Downloads)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -d "$TEST_DIR/TV_Downloads" ]; then
    echo "Video Files:"
    find "$TEST_DIR/TV_Downloads" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) -exec basename {} \; | sort
    echo ""
    echo "Folders:"
    find "$TEST_DIR/TV_Downloads" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort
    echo ""
    echo "Total: $(find "$TEST_DIR/TV_Downloads" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) | wc -l) video files, $(find "$TEST_DIR/TV_Downloads" -mindepth 1 -maxdepth 1 -type d | wc -l) folders"
else
    echo "Not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📺 CURRENT TV SHOWS ($TEST_DIR/TV_Shows/Current)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -d "$TEST_DIR/TV_Shows/Current" ]; then
    for dir in "$TEST_DIR/TV_Shows/Current"/*/ ; do
        if [ -d "$dir" ]; then
            folder_name=$(basename "$dir")
            file_count=$(find "$dir" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) | wc -l)
            echo "  📁 $folder_name ($file_count files)"
        fi
    done
    echo ""
    echo "Total: $(find "$TEST_DIR/TV_Shows/Current" -mindepth 1 -maxdepth 1 -type d | wc -l) shows"
else
    echo "Not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📺 CONCLUDED TV SHOWS ($TEST_DIR/TV_Shows/Concluded)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -d "$TEST_DIR/TV_Shows/Concluded" ]; then
    for dir in "$TEST_DIR/TV_Shows/Concluded"/*/ ; do
        if [ -d "$dir" ]; then
            folder_name=$(basename "$dir")
            file_count=$(find "$dir" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) | wc -l)
            echo "  📁 $folder_name ($file_count files)"
        fi
    done
    echo ""
    echo "Total: $(find "$TEST_DIR/TV_Shows/Concluded" -mindepth 1 -maxdepth 1 -type d | wc -l) shows"
else
    echo "Not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎬 MOVIES ($TEST_DIR/Movies)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -d "$TEST_DIR/Movies" ]; then
    for dir in "$TEST_DIR/Movies"/*/ ; do
        if [ -d "$dir" ]; then
            folder_name=$(basename "$dir")
            file_count=$(find "$dir" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) | wc -l)
            echo "  📁 $folder_name ($file_count files)"
        fi
    done
    echo ""
    echo "Total: $(find "$TEST_DIR/Movies" -mindepth 1 -maxdepth 1 -type d | wc -l) movies"
else
    echo "Not found"
fi

echo ""
echo "============================================================================"
echo ""
echo "Expected Fuzzy Matches:"
echo "  • 'The.Pitt.S01E10.mkv' → 'The Pitt' (exact)"
echo "  • 'Severance.S02E03.mkv' → 'Severance (2022)' (fuzzy)"
echo "  • 'The.Mandalorian.S04E01' → 'The Mandalorian' (exact)"
echo "  • 'Game.of.Thrones.S08E06' → 'Game of Thrones (2011-2019)' (fuzzy)"
echo "  • 'Breaking.Bad.S05E16' → 'Breaking Bad' (exact)"
echo "  • 'The.Matrix.1999' → 'The Matrix Collection' (fuzzy)"
echo "  • '12.Angry.Men.1957' → '12 Angry Men' (fuzzy)"
echo ""
echo "New Folders Should Be Created:"
echo "  • The Last of Us (no existing folder)"
echo "  • Squid Game (no existing folder)"
echo "  • Wednesday (no existing folder)"
echo "  • Spartacus House of Ashur (no existing folder)"
echo "  • 1917, Oppenheimer, Inception, Interstellar, etc."
echo ""
echo "============================================================================"
