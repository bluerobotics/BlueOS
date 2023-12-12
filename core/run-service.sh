#!/usr/bin/env bash

service_command=$1
memory_limit_mb=$2
memory_limit_kb=$((memory_limit_mb * 1024))
LOG_FILE="/var/logs/blueos/run-service.log"

# Continuously run the service, restarting if it stops or exceeds memory limit
while true; do
    echo "Starting service: $service_command with memory limit: $memory_limit_kb kb"
    # Set memory limit for this subshell only if memory_limit_kb is not zero
    if [ "$memory_limit_kb" -ne 0 ]; then
        ulimit -v "$memory_limit_kb"
    fi

    if ! eval "$service_command"; then
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        echo "$timestamp: Service ($service_command) exceeded memory limit or stopped. Restarting..." | tee -a "$LOG_FILE"
    else
        exit 0;
    fi

    sleep 5
    echo "Restarting service: $service_command"
done
