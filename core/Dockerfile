# Override with --build-arg BASE_IMAGE=blueos-base:dev for local builds
ARG BASE_IMAGE=bluerobotics/blueos-base:0.2.6

# Build frontend
FROM --platform=$BUILDPLATFORM oven/bun:1.3.14-slim AS frontend-builder

COPY frontend /home/pi/frontend
ENV BUN_FEATURE_FLAG_DISABLE_STREAMING_INSTALL=1
RUN <<-EOF
set -e

    bun install --frozen-lockfile --cwd /home/pi/frontend
    NODE_OPTIONS=--max-old-space-size=8192 bun run --cwd /home/pi/frontend build

EOF

FROM ${BASE_IMAGE} AS base

# Download binaries
FROM base AS download-binaries
COPY tools /home/pi/tools
RUN apt update && apt install -y --no-install-recommends binutils
RUN /home/pi/tools/install-static-binaries.sh

# Generation of python virtual environment for our libraries and services
FROM base AS install-services-and-libs

RUN apt update && apt install -y --no-install-recommends g++

# UV installation
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# Project files. Services are virtual projects (package = false) and run from
# /home/pi/services in the final image, so only their metadata is required to
# resolve dependencies. Copying the source would rebuild this environment on
# every service edit, and the vehicle would re-download the whole virtualenv.
COPY ./uv.lock /home/pi/uv.lock
COPY ./pyproject.toml /home/pi/pyproject.toml
COPY ./.python-version /home/pi/.python-version

COPY --parents libs/*/pyproject.toml /home/pi/
COPY --parents services/*/pyproject.toml /home/pi/

# Virtual environment creation and packages installation
WORKDIR /home/pi
RUN uv venv && uv sync --frozen --no-default-groups --no-install-workspace \
    && for lib in libs/*/; do \
        name=$(basename "$lib"); \
        printf '%s\n' "/home/pi/libs/$name/src" > "/home/pi/.venv/lib/python3.11/site-packages/$name.pth"; \
    done

# Post install scripts. Kept after the sync so a tool-script edit does not
# redo the dependency install above.
COPY ./tools /home/pi/tools
RUN BLUEOS_PYTHON_ENVS="/home/pi/.venv" /home/pi/tools/install-python-libs.sh

# Reset default workdir
WORKDIR /home/pi
ENV VIRTUAL_ENV=/home/pi/.venv

# BlueOS base image.
# Least-changed layers first: tools, then services, then the frontend.
# A pulled update re-downloads a layer when its contents change, and it
# re-downloads every later layer. GIT_DESCRIBE_TAGS changes
# on every release, so it stays in the last layer.
FROM base

# Define arguments for target platform
# These arguments are defined automatically by buildx when using `--platform`
ARG TARGETARCH
ARG TARGETVARIANT

ENV TARGETARCH=${TARGETARCH}
ENV TARGETVARIANT=${TARGETVARIANT}

# Tools change least often.
COPY tools /home/pi/tools
RUN /home/pi/tools/install-system-tools.sh

# Copy binaries and necessary folders from download-binaries to this stage
COPY --from=download-binaries \
    /usr/bin/blueos_startup_update.py \
    /usr/bin/blueos-recorder \
    /usr/bin/bridges \
    /usr/bin/disktest \
    /usr/bin/linux2rest \
    /usr/bin/machineid-cli \
    /usr/bin/mavlink2rest \
    /usr/bin/mavlink-camera-manager \
    /usr/bin/mavlink-server \
    /usr/bin/mcap \
    /usr/bin/mcap-foxglove-video-extract \
    /usr/bin/zenoh \
    /usr/bin/ttyd \
    /usr/bin/

COPY --from=install-services-and-libs /home/pi/.venv /usr/blueos/venv

RUN <<-EOF
set -e

    # Asserts
    ## When running, the .config folder in the docker is not accessible,
    ## since it gets shadowed by the host's `.config` folder.
    ## If the folder tree contains any files during the build step, it means we put it here by mistake.
    [ -z "$(find '/root/.config' -mindepth 1 -type f)" ]

    # Update blueosrc with the necessary environment variables.
    # GIT_DESCRIBE_TAGS is appended in the last layer; it changes every release.
    RCFILE_PATH="/etc/blueosrc"
    echo "export HISTFILE=/etc/blueos/.bash_history" >> $RCFILE_PATH
    echo "export BLUEOS_VENV=/usr/blueos/venv" >> $RCFILE_PATH
    echo "export PATH=/usr/blueos/venv/bin:/usr/blueos/bin:$PATH" >> $RCFILE_PATH
    echo "export RUST_BACKTRACE=1" >> $RCFILE_PATH

    # Setup shortcuts
    mkdir -p /shortcuts
    ln -s /root/.config /shortcuts/configs
    ln -s /var/logs/blueos/services /shortcuts/system_logs
    ln -s /usr/blueos/userdata /shortcuts/userdata
    ln -s /usr/blueos/extensions /shortcuts/extensions
    ln -s /root/.config/ardupilot-manager /shortcuts/ardupilot_logs
    ln -s / /shortcuts/system_root

    # Setup user
    useradd -m -u 1000 -G dialout blueos

    # Remove /etc/dhcpcd.conf if it exists inside the docker
    # This is to prevent an awkward behavior where docker doesnt find the file
    # on the host system and creates a folder instead, but tries to mount the folder
    # on top of the existing file inside the docker.
    # This allows docker to actually create a folder, which we handle in networksetup.py
    rm -f /etc/dhcpcd.conf

EOF

# Services change more often than tools, less often than the frontend.
COPY libs /home/pi/libs
COPY services /home/pi/services

# The venv's .pth files point at libs/<name>/src. Fail the build if a lib uses another layout.
RUN for lib in /home/pi/libs/*/; do \
        [ -d "${lib}src" ] || { echo "${lib} has no src directory"; exit 1; }; \
    done

COPY configuration/tmux.conf /etc/tmux.conf
COPY configuration/motd /etc/motd
COPY start-blueos-core /usr/bin/start-blueos-core
COPY run-service.sh /usr/bin/run-service
COPY ./.vscode /home/pi/.vscode

# Frontend changes most often. The git description is not in this bundle; the
# next layer writes it beside these files.
COPY --from=frontend-builder /home/pi/frontend/dist /home/pi/frontend

# Version stamp. Last, because this value changes on every release and a step
# that consumes it invalidates every layer above it.
ARG GIT_DESCRIBE_TAGS
ARG GIT_COMMIT_DATE
# The fallback has a non-zero distance so a local build without the argument never counts as a tag build.
ENV GIT_DESCRIBE_TAGS=${GIT_DESCRIBE_TAGS:-0.0.0-999-g00000000}
RUN <<-EOF
set -e

    # The format can be invalid if someone builds BlueOS without a tag as reference.
    if ! echo "$GIT_DESCRIBE_TAGS" | grep -Eq -- '-[0-9]+-g[a-f0-9]{8,}$'; then
        echo "Invalid format: $GIT_DESCRIBE_TAGS (E.g: <TAG>-<COMMIT_NUMBER>-g<SHORT_HASH>)"
        exit 1
    fi

    echo "export GIT_DESCRIBE_TAGS=$GIT_DESCRIBE_TAGS" >> /etc/blueosrc
    printf '%s\n%s\n' "$GIT_DESCRIBE_TAGS" "$GIT_COMMIT_DATE" > /home/pi/frontend/blueos-version

EOF

# Start
CMD ["/bin/bash", "-i", "-c", "/usr/bin/start-blueos-core && sleep infinity"]
