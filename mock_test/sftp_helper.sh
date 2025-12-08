#!/bin/bash
# SFTP Helper Script for Mock Testing
# Provides functions to create/delete/verify files on remote SFTP server

# Load SFTP configuration from .env.test
load_sftp_config() {
    if [ -f "$(dirname "${BASH_SOURCE[0]}")/.env.test" ]; then
        export $(cat "$(dirname "${BASH_SOURCE[0]}")/.env.test" | grep -E '^SFTP_' | xargs)
    fi
}

# Check if SFTP is configured
is_sftp_enabled() {
    load_sftp_config
    if [ -n "$SFTP_HOST" ] && [ -n "$SFTP_USER" ] && [ -n "$SFTP_PASSWORD" ]; then
        return 0
    else
        return 1
    fi
}

# Create a file on remote SFTP server
# Usage: sftp_create_file <remote_path> [size_in_kb]
# Note: Assumes SFTP_REMOTE_DIR exists, creates subdirectories as needed
sftp_create_file() {
    local remote_path="$1"
    local size_kb="${2:-100}"  # Default 100KB

    # Remove leading ./ from path
    remote_path="${remote_path#./}"

    # Get directory path (relative to SFTP_REMOTE_DIR)
    local dir_path=$(dirname "$remote_path")

    # Create temporary file locally
    local temp_file=$(mktemp)
    dd if=/dev/urandom of="$temp_file" bs=1024 count="$size_kb" 2>/dev/null

    # Upload file, creating parent directories as needed
    # Create directories recursively on remote server
    local create_dirs_cmd=""
    if [ "$dir_path" != "." ]; then
        # Create each directory in the path
        local current_path=""
        IFS='/' read -ra DIRS <<< "$dir_path"
        for dir in "${DIRS[@]}"; do
            if [ -n "$dir" ]; then
                if [ -z "$current_path" ]; then
                    current_path="$dir"
                else
                    current_path="$current_path/$dir"
                fi
                create_dirs_cmd="${create_dirs_cmd}mkdir -f \"$current_path\""$'\n'
            fi
        done
    fi

    lftp -u "${SFTP_USER},${SFTP_PASSWORD}" "sftp://${SFTP_HOST}:${SFTP_PORT}" 2>/dev/null <<EOF
set sftp:auto-confirm yes
set ssl:verify-certificate no
cd "${SFTP_REMOTE_DIR}" || exit 1
$create_dirs_cmd
put "$temp_file" -o "$remote_path"
quit
EOF

    local result=$?
    rm -f "$temp_file"
    return $result
}

# Create a directory on remote SFTP server
# Usage: sftp_create_directory <remote_path>
# Note: Assumes SFTP_REMOTE_DIR exists, creates subdirectories as needed
sftp_create_directory() {
    local remote_path="$1"

    # Remove leading ./ and trailing /
    remote_path="${remote_path#./}"
    remote_path="${remote_path%/}"

    # Create each directory in the path recursively
    local create_dirs_cmd=""
    local current_path=""
    IFS='/' read -ra DIRS <<< "$remote_path"
    for dir in "${DIRS[@]}"; do
        if [ -n "$dir" ]; then
            if [ -z "$current_path" ]; then
                current_path="$dir"
            else
                current_path="$current_path/$dir"
            fi
            create_dirs_cmd="${create_dirs_cmd}mkdir -f \"$current_path\""$'\n'
        fi
    done

    lftp -u "${SFTP_USER},${SFTP_PASSWORD}" "sftp://${SFTP_HOST}:${SFTP_PORT}" 2>/dev/null <<EOF
set sftp:auto-confirm yes
set ssl:verify-certificate no
cd "${SFTP_REMOTE_DIR}" || exit 1
$create_dirs_cmd
quit
EOF

    return $?
}

# Check if a file/directory exists on remote SFTP server
# Usage: sftp_exists <remote_path>
sftp_exists() {
    local remote_path="$1"
    local remote_full_path="${SFTP_REMOTE_DIR}${remote_path}"

    # Remove leading ./
    remote_full_path="${remote_full_path#./}"

    lftp -u "${SFTP_USER},${SFTP_PASSWORD}" "sftp://${SFTP_HOST}:${SFTP_PORT}" <<EOF 2>/dev/null
set sftp:auto-confirm yes
set ssl:verify-certificate no
ls "$remote_full_path"
quit
EOF

    return $?
}

# Delete a file/directory from remote SFTP server
# Usage: sftp_delete <remote_path>
sftp_delete() {
    local remote_path="$1"
    local remote_full_path="${SFTP_REMOTE_DIR}${remote_path}"

    # Remove leading ./
    remote_full_path="${remote_full_path#./}"

    lftp -u "${SFTP_USER},${SFTP_PASSWORD}" "sftp://${SFTP_HOST}:${SFTP_PORT}" <<EOF 2>/dev/null
set sftp:auto-confirm yes
set ssl:verify-certificate no
rm -r "$remote_full_path"
quit
EOF

    return $?
}

# Clean up all test files from remote SFTP server
# Usage: sftp_cleanup_all
# Note: Assumes SFTP_REMOTE_DIR already exists and just cleans its contents
sftp_cleanup_all() {
    if [ -z "$SFTP_REMOTE_DIR" ]; then
        echo "ERROR: SFTP_REMOTE_DIR not set"
        return 1
    fi

    echo "Cleaning up remote SFTP directory: $SFTP_REMOTE_DIR"

    # Remove all contents of the directory (not the directory itself)
    lftp -u "${SFTP_USER},${SFTP_PASSWORD}" "sftp://${SFTP_HOST}:${SFTP_PORT}" <<EOF
set sftp:auto-confirm yes
set ssl:verify-certificate no
cd "${SFTP_REMOTE_DIR}" || exit 1
rm -rf *
quit
EOF

    local result=$?

    if [ $result -eq 0 ]; then
        echo "✓ Remote directory cleaned: ${SFTP_REMOTE_DIR}"
    else
        echo "✗ Failed to clean remote directory (does it exist?): ${SFTP_REMOTE_DIR}"
    fi

    return $result
}

# Test SFTP connection
# Usage: sftp_test_connection
sftp_test_connection() {
    echo "Testing SFTP connection..."
    echo "  Host: $SFTP_HOST:$SFTP_PORT"
    echo "  User: $SFTP_USER"
    echo "  Remote Dir: $SFTP_REMOTE_DIR"

    lftp -u "${SFTP_USER},${SFTP_PASSWORD}" "sftp://${SFTP_HOST}:${SFTP_PORT}" <<EOF
set sftp:auto-confirm yes
set ssl:verify-certificate no
ls
quit
EOF

    if [ $? -eq 0 ]; then
        echo "✓ SFTP connection successful"
        return 0
    else
        echo "✗ SFTP connection failed"
        return 1
    fi
}

# Initialize - load config when sourced
load_sftp_config
