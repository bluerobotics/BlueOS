#!/usr/bin/env bash

SERVICES=(
    'nginx','nginx -g "daemon on;"'
    'supervisor','/supervisor/supervisor.py'
)

tmux start-server
function create_service {
    tmux new -d -s "$1" || true
    tmux send-keys -t "$1:0" "$2" C-m
}

echo "Starting services.."
for TUPLE in "${SERVICES[@]}"; do
    IFS=',' read NAME EXECUTABLE <<< ${TUPLE}
    echo "Service: $NAME: $EXECUTABLE"
    create_service $NAME "$EXECUTABLE"
done

echo "Supervisor running!"