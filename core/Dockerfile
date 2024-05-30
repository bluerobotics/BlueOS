# Build frontend
FROM --platform=$BUILDPLATFORM oven/bun:1.0.3-slim AS frontendBuilder

ARG VITE_APP_GIT_DESCRIBE
ENV VITE_APP_GIT_DESCRIBE=${VITE_APP_GIT_DESCRIBE:-none/none-0-g00000000}
RUN <<-EOF
set -e

    if [ -z "$VITE_APP_GIT_DESCRIBE" ]; then
        echo "VITE_APP_GIT_DESCRIBE argument not provided."
        echo "Use: --build-arg VITE_APP_GIT_DESCRIBE=\$(git describe --long --always --dirty --all)"
        exit 1
    fi

EOF

COPY frontend /home/pi/frontend
RUN <<-EOF
set -e

    bun install --cwd /home/pi/frontend
    bun run --cwd /home/pi/frontend build

EOF

# Download binaries
FROM bluerobotics/blueos-base:v0.1.3 as downloadBinaries
COPY tools /home/pi/tools
RUN /home/pi/tools/install-static-binaries.sh

# BlueOS-docker base image
FROM bluerobotics/blueos-base:v0.1.3

# Define arguments for target platform
# These arguments are defined automatically by buildx when using `--platform`
ARG TARGETARCH
ARG TARGETVARIANT

# Ensure that the git describe exists and also is in valid format as well
# The format can be invalid if someone is build BlueOS without a tag as reference
ARG GIT_DESCRIBE_TAGS
ENV GIT_DESCRIBE_TAGS=${GIT_DESCRIBE_TAGS:-0.0.0-0-g00000000}
RUN <<-EOF
set -e

    if [ -z "$GIT_DESCRIBE_TAGS" ]; then
        echo "GIT_DESCRIBE_TAGS argument not provided."
        echo "Use: --build-arg GIT_DESCRIBE_TAGS=\$(git describe --tags --long --always)"
        exit 1
    fi

    if [[ ! $GIT_DESCRIBE_TAGS =~ -[0-9]+-g[a-f0-9]{8}$ ]]; then
        echo "Invalid format: $GIT_DESCRIBE_TAGS (E.g: <TAG>-<COMMIT_NUMBER>-g<SHORT_HASH>)"
        exit 1
    fi

EOF

# Set these arguments as environment variables
ENV TARGETARCH=${TARGETARCH}
ENV TARGETVARIANT=${TARGETVARIANT}

# Install necessary tools
COPY tools /home/pi/tools
RUN /home/pi/tools/install-system-tools.sh

# Copy overlay source in case we need to build it in runtime
COPY install/ /install

# Install custom libraries
COPY libs /home/pi/libs
RUN /home/pi/libs/install-libs.sh

# Set tmux configuration file
COPY configuration/tmux.conf /etc/tmux.conf
COPY configuration/motd /etc/motd

# Install services
COPY services /home/pi/services
RUN /home/pi/services/install-services.sh
COPY start-blueos-core /usr/bin/start-blueos-core
COPY run-service.sh /usr/bin/run-service

# Copy binaries and necessary folders from downloadBinaries to this stage
COPY --from=downloadBinaries \
    /usr/bin/blueos_startup_update.py \
    /usr/bin/bridges \
    /usr/bin/machineid-cli \
    /usr/bin/mavlink2rest \
    /usr/bin/mavlink-routerd \
    /usr/bin/mavp2p \
    /usr/bin/ttyd \
    /usr/bin/

# Copy frontend built on frontendBuild to this stage
COPY --from=frontendBuilder /home/pi/frontend/dist /home/pi/frontend

RUN <<-EOF
set -e

    # Asserts
    ## When running, the .config folder in the docker is not accessible,
    ## since it gets shadowed by the host's `.config` folder.
    ## If the folder tree contains any files during the build step, it means we put it here by mistake.
    [ -z "$(find '/root/.config' -mindepth 1 -type f)" ]

    # Update blueosrc with the necessary environment variables
    RCFILE_PATH="/etc/blueosrc"
    echo "export GIT_DESCRIBE_TAGS=$GIT_DESCRIBE_TAGS" >> $RCFILE_PATH
    echo "export HISTFILE=/etc/blueos/.bash_history" >> $RCFILE_PATH
    echo "export PATH=$(python -m site --user-base)/bin:/usr/blueos/bin:$PATH" >> $RCFILE_PATH

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

EOF

# Start
CMD /bin/bash -i /usr/bin/start-blueos-core && sleep infinity
