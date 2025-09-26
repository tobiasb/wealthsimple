#!/bin/bash

# Script to run the Wealthsimple API command for multiple users
# Reads email addresses from WS_USERNAMES environment variable
# Sets start date to 6 months ago, leaves end date empty
# Includes error handling and retry logic for authentication failures

# Configuration
MAX_RETRIES=3
RETRY_DELAY=5

# Check if WS_USERNAMES is set
if [ -z "$WS_USERNAMES" ]; then
    echo "Error: WS_USERNAMES environment variable is not set"
    exit 1
fi

# Calculate start date (6 months ago)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    START_DATE=$(date -v-6m '+%Y-%m-%dT00:00:00.000000+00:00')
else
    # Linux
    START_DATE=$(date -d '6 months ago' '+%Y-%m-%dT00:00:00.000000+00:00')
fi

# Function to run command with retry logic
run_with_retry() {
    local username="$1"
    local attempt=1

    while [ $attempt -le $MAX_RETRIES ]; do
        echo "Attempt $attempt of $MAX_RETRIES for user: $username"

        # Capture both stdout and stderr, and capture the exit code
        if pipenv run python app.py --username="$username" --start="$START_DATE" 2>&1 | tee /tmp/ws_output_$$.log; then
            echo "✅ Successfully processed user: $username"
            rm -f /tmp/ws_output_$$.log
            return 0
        else
            local exit_code=${PIPESTATUS[0]}
            echo "❌ Command failed with exit code: $exit_code"

            # Check if it's an authentication error (401 Unauthorized)
            if grep -q "401 Client Error: Unauthorized" /tmp/ws_output_$$.log 2>/dev/null; then
                echo "🔐 Authentication failed (401 Unauthorized)"
                if [ $attempt -lt $MAX_RETRIES ]; then
                    echo "⏳ Waiting $RETRY_DELAY seconds before retry..."
                    sleep $RETRY_DELAY
                    echo "🔄 Retrying authentication..."
                else
                    echo "❌ Max retries reached for user: $username"
                    echo "💡 Please check your credentials and try again manually"
                fi
            else
                echo "❌ Non-authentication error occurred"
                echo "📋 Error details:"
                cat /tmp/ws_output_$$.log
                rm -f /tmp/ws_output_$$.log
                return $exit_code
            fi
        fi

        attempt=$((attempt + 1))
    done

    rm -f /tmp/ws_output_$$.log
    echo "❌ Failed to process user: $username after $MAX_RETRIES attempts"
    return 1
}

echo "Start date set to: $START_DATE"
echo "Running for users: $WS_USERNAMES"
echo "Max retries per user: $MAX_RETRIES"
echo "Retry delay: $RETRY_DELAY seconds"
echo "----------------------------------------"

# Split the usernames by comma and run for each
IFS=',' read -ra USERNAMES <<< "$WS_USERNAMES"

failed_users=()
successful_users=()

for username in "${USERNAMES[@]}"; do
    # Trim whitespace
    username=$(echo "$username" | xargs)

    if [ -n "$username" ]; then
        echo "Processing user: $username"
        echo "----------------------------------------"

        if run_with_retry "$username"; then
            successful_users+=("$username")
        else
            failed_users+=("$username")
        fi

        echo "----------------------------------------"
        echo ""
    fi
done

# Print summary
echo "========================================"
echo "📊 PROCESSING SUMMARY"
echo "========================================"

if [ ${#successful_users[@]} -gt 0 ]; then
    echo "✅ Successfully processed users:"
    for user in "${successful_users[@]}"; do
        echo "   - $user"
    done
fi

if [ ${#failed_users[@]} -gt 0 ]; then
    echo "❌ Failed users:"
    for user in "${failed_users[@]}"; do
        echo "   - $user"
    done
    echo ""
    echo "💡 For failed users, please check:"
    echo "   - Username and password are correct"
    echo "   - OTP is valid and not expired"
    echo "   - Network connection is stable"
    echo "   - Wealthsimple account is not locked"
    exit 1
else
    echo "🎉 All users processed successfully!"
    exit 0
fi
