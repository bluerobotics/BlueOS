# Build frontend
FROM node:16-buster-slim AS frontendBuilder

ARG VUE_APP_GIT_DESCRIBE
RUN [ -z "$VUE_APP_GIT_DESCRIBE" ] \
    && echo "VUE_APP_GIT_DESCRIBE argument not provided." \
    && echo "Use: --build-arg VUE_APP_GIT_DESCRIBE=\$(git describe --long --always --dirty --all)" \
    && exit 1 || exit 0

COPY frontend /home/pi/frontend
RUN --mount=type=cache,target=/home/pi/frontend/node_modules yarn --cwd /home/pi/frontend install --network-timeout=300000
RUN --mount=type=cache,target=/home/pi/frontend/node_modules yarn --cwd /home/pi/frontend build --skip-plugins @vue/cli-plugin-eslint

# Download binaries
FROM bluerobotics/companion-base:v0.0.6 as downloadBinaries
COPY tools /home/pi/tools
RUN /home/pi/tools/install-static-binaries.sh

# Companion-docker base image
FROM bluerobotics/companion-base:v0.0.6

# Install necessary tools
COPY tools /home/pi/tools
RUN /home/pi/tools/install-system-tools.sh

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

# Copy binaries and necessary folders from downloadBinaries to this stage
COPY --from=downloadBinaries \
    /usr/bin/blueos_startup_update \
    /usr/bin/bridges \
    /usr/bin/mavlink2rest \
    /usr/bin/mavlink-routerd \
    /usr/bin/ttyd \
    /usr/bin/

# Copy frontend built on frontendBuild to this stage
COPY --from=frontendBuilder /home/pi/frontend/dist /home/pi/frontend

# Asserts
## When running, the .config folder in the docker is not accessible,
## since it gets shadowed by the host's `.config` folder.
## If the folder exists during the build step, it means we put it here by mistake.
RUN [ ! -d "/root/.config" ]

ARG GIT_DESCRIBE_TAGS
RUN [ -z "$GIT_DESCRIBE_TAGS" ] \
    && echo "GIT_DESCRIBE_TAGS argument not provided." \
    && echo "Use: --build-arg GIT_DESCRIBE_TAGS=\$(git describe --tags --long)" \
    && exit 1 || exit 0

# Update blueosrc with the necessary environment variables
RUN RCFILE_PATH="/etc/blueosrc" \
    && echo "export GIT_DESCRIBE_TAGS=$GIT_DESCRIBE_TAGS" >> $RCFILE_PATH

# Start
CMD /bin/bash -i /usr/bin/start-blueos-core && sleep infinity
