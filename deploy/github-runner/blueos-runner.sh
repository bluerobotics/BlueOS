#!/usr/bin/env bash
# This script should run on a raspberry
# To check the necessary token permissions:
#   https://github.com/myoung34/docker-github-actions-runner#create-github-personal-access-token

if [ -z "$1" ]; then
    echo "Please specify a GitHub token as argument."
    exit 1
fi

NAME=blueos-runner
ORG=bluerobotics
WORKDIR="/tmp/github-runner-${NAME}"
sudo docker rm -f "${NAME}"
sudo docker run -d --restart=always \
    --privileged \
    -e LABELS="blueos" \
    -e ORG_NAME="${ORG}" \
    -e ACCESS_TOKEN="$1" \
    -e RUNNER_NAME="${NAME}" \
    -e RUNNER_WORKDIR="${WORKDIR}" \
    -e RUNNER_GROUP="Default" \
    -e RUNNER_SCOPE="org" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v ${WORKDIR}:${WORKDIR} \
    --name ${NAME} myoung34/github-runner:ubuntu-bionic