#!/usr/bin/env bash

service_name=$1
service_command=$2
memory_limit_mb=$3
memory_limit_bytes=$((memory_limit_mb * 1024 * 1024))
LOG_FILE="/var/logs/blueos/run-service.log"

# Assuming cgroups v2
CHILD_CGROUP="/sys/fs/cgroup/$DOCKER_CGROUP/$service_name"
# Create a new cgroup for the service
mkdir -p "$CHILD_CGROUP"

# Set memory limit for the cgroup
echo "$memory_limit_bytes" > "$CHILD_CGROUP/memory.max"

# find PIDs for all children of a given process
findpids() {
  local pid=$1
  local pid_list="$pid "
  for cpid in $(pgrep -P $pid); do
    pid_list="$pid_list$(findpids $cpid) "
  done
  echo "$pid_list" | tr ' ' '\n' | sort -u | tr '\n' ' '
}

# Function to start the service and add its PIDs to the cgroup
start_service() {
  # Start the service in the background
  eval "$service_command" &
  service_pid=$!

  add_to_cgroup() {
    local pid=$1
    # Check if the process exists and memory limit is set
    if ! ps -p $pid > /dev/null || [ $memory_limit_bytes -eq 0 ]; then
      # process doesn't exist. presume it is already dead
      return
    fi
    echo $pid > $CHILD_CGROUP/cgroup.procs
  }

  # Recursive function to find and add child processes to the cgroup
  add_child_processes_to_cgroup() {
    local parent_pid=$1
    # Find all child processes of the parent PID
    child_pids=$(findpids $parent_pid)
    # Add each child process to the cgroup
    for pid in $child_pids; do
      echo "Adding child process $pid to cgroup $service_name"
      add_to_cgroup $pid
    done
  }

  add_to_cgroup $service_pid
  add_to_cgroup $$ # this is the PID of the current process
  add_child_processes_to_cgroup $service_pid

  # Wait for the process to complete and capture its exit code
  wait $service_pid
  return $?
}

# Continuously run the service, restarting if it stops or exceeds memory limit
while true; do
  echo "Starting service: $service_command with memory limit: $memory_limit_bytes bytes "
  if ! start_service; then
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$timestamp: Service ($service_command) exceeded memory limit or stopped. Restarting..." | tee -a "$LOG_FILE"
  else
    echo "Service ($service_command) completed successfully."
    break
  fi

  sleep 5
  echo "Restarting service: $service_command"
done
