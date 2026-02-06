#!/usr/bin/env bash

service_name=$1
service_command=$2
memory_limit_mb=${3:-0}
cpu_limit_percent=${4:-0}
io_read_mbps=${5:-0}
io_write_mbps=${6:-0}

memory_limit_bytes=$((memory_limit_mb * 1024 * 1024))
LOG_FILE="/var/logs/blueos/run-service.log"

# Assuming cgroups v2
CHILD_CGROUP="/sys/fs/cgroup/$DOCKER_CGROUP/$service_name"
# Create a new cgroup for the service
mkdir -p "$CHILD_CGROUP"

# Set memory limit for the cgroup (0 = no limit)
if [ "$memory_limit_bytes" -gt 0 ]; then
    echo "$memory_limit_bytes" > "$CHILD_CGROUP/memory.max"
fi

# Set CPU limit for the cgroup (0 = no limit)
# cpu.max format: "QUOTA PERIOD" in microseconds
# Example: "50000 100000" means 50% of one CPU core
if [ "$cpu_limit_percent" -gt 0 ]; then
    CPU_PERIOD=100000
    CPU_QUOTA=$((cpu_limit_percent * CPU_PERIOD / 100))
    echo "$CPU_QUOTA $CPU_PERIOD" > "$CHILD_CGROUP/cpu.max"
fi

# Set I/O limits for the cgroup (0 = no limit)
# io.max format: "MAJOR:MINOR rbps=BYTES wbps=BYTES"
if [ "$io_read_mbps" -gt 0 ] || [ "$io_write_mbps" -gt 0 ]; then
    # Get the major:minor of the actual block device
    # In Docker containers with overlay fs, we need to find the underlying block device
    # Note: cgroups v2 I/O limiting works on whole block devices, not partitions
    # So we use mmcblk0 (not mmcblk0p2), sda (not sda1), etc.
    ROOT_MAJOR=""
    ROOT_MINOR=""
    
    # Scan for whole block devices (not partitions)
    # Glob patterns match whole disks only: mmcblk0 (not mmcblk0p1), sda (not sda1), etc.
    # Order: embedded (mmcblk), common (sd), NVMe, virtual (vd, xvd)
    for DEV in /dev/mmcblk[0-9] /dev/sd[a-z] /dev/nvme[0-9]n[0-9] /dev/vd[a-z] /dev/xvd[a-z]; do
        if [ -b "$DEV" ]; then
            ROOT_MAJOR=$(stat -c '%t' "$DEV" 2>/dev/null)
            ROOT_MINOR=$(stat -c '%T' "$DEV" 2>/dev/null)
            if [ -n "$ROOT_MAJOR" ] && [ -n "$ROOT_MINOR" ]; then
                # Convert from hex to decimal
                ROOT_MAJOR=$((16#$ROOT_MAJOR))
                ROOT_MINOR=$((16#$ROOT_MINOR))
                break
            fi
        fi
    done
    
    # Skip I/O limiting if no valid block device found
    if [ -z "$ROOT_MAJOR" ] || [ -z "$ROOT_MINOR" ]; then
        echo "Warning: Could not find block device for I/O limiting"
    else
        IO_LIMIT_STR="$ROOT_MAJOR:$ROOT_MINOR"
        if [ "$io_read_mbps" -gt 0 ]; then
            IO_READ_BPS=$((io_read_mbps * 1024 * 1024))
            IO_LIMIT_STR="$IO_LIMIT_STR rbps=$IO_READ_BPS"
        fi
        if [ "$io_write_mbps" -gt 0 ]; then
            IO_WRITE_BPS=$((io_write_mbps * 1024 * 1024))
            IO_LIMIT_STR="$IO_LIMIT_STR wbps=$IO_WRITE_BPS"
        fi
        echo "$IO_LIMIT_STR" > "$CHILD_CGROUP/io.max"
    fi
fi

# Check if any resource limit is enabled
has_any_limit() {
  [ "$memory_limit_bytes" -gt 0 ] || [ "$cpu_limit_percent" -gt 0 ] || \
  [ "$io_read_mbps" -gt 0 ] || [ "$io_write_mbps" -gt 0 ]
}

# find PIDs for all children of a given process
findpids() {
  local pid=$1
  local pid_list="$pid "
  for cpid in $(pgrep -P $pid); do
    pid_list="$pid_list$(findpids $cpid) "
  done
  echo "$pid_list" | tr ' ' '\n' | sort -u | tr '\n' ' '
}

add_to_cgroup() {
  local pid=$1
  # Check if the process exists and any limit is set
  if ! ps -p $pid > /dev/null || ! has_any_limit; then
    # process doesn't exist or no limits set
    return
  fi
  echo $pid > $CHILD_CGROUP/cgroup.procs
}

# Add current shell to cgroup FIRST so all children inherit limits
add_to_cgroup $$

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

# Function to start the service and add its PIDs to the cgroup
start_service() {
  # Start the service in the background
  eval "$service_command" &
  service_pid=$!

  add_to_cgroup $service_pid
  add_child_processes_to_cgroup $service_pid

  # Wait for the process to complete and capture its exit code
  wait $service_pid
  return $?
}

# Build limits description for logging
get_limits_description() {
  local desc=""
  [ "$memory_limit_mb" -gt 0 ] && desc="${desc}mem=${memory_limit_mb}MB "
  [ "$cpu_limit_percent" -gt 0 ] && desc="${desc}cpu=${cpu_limit_percent}% "
  [ "$io_read_mbps" -gt 0 ] && desc="${desc}io_r=${io_read_mbps}MB/s "
  [ "$io_write_mbps" -gt 0 ] && desc="${desc}io_w=${io_write_mbps}MB/s "
  [ -z "$desc" ] && desc="none"
  echo "$desc"
}

# Continuously run the service, restarting if it stops or exceeds resource limits
while true; do
  echo "Starting service: $service_command with limits: $(get_limits_description)"
  if ! start_service; then
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$timestamp: Service ($service_command) exceeded resource limit or stopped. Restarting..." | tee -a "$LOG_FILE"
  else
    echo "Service ($service_command) completed successfully."
    break
  fi

  sleep 5
  echo "Restarting service: $service_command"
done
