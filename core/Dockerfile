# Build frontend
FROM node:16-buster-slim AS frontendBuilder

ARG VUE_APP_GIT_DESCRIBE

COPY frontend /home/pi/frontend
WORKDIR /home/pi/frontend
RUN --mount=type=cache,target=/home/pi/frontend/node_modules yarn install --network-timeout=300000
RUN --mount=type=cache,target=/home/pi/frontend/node_modules yarn build --skip-plugins @vue/cli-plugin-eslint

# Download binaries
FROM bluerobotics/companion-base:v0.0.4 as downloadBinaries
COPY tools /home/pi/tools
RUN /home/pi/tools/bridges/bootstrap.sh
RUN /home/pi/tools/mavlink2rest/bootstrap.sh
RUN /home/pi/tools/mavlink_camera_manager/bootstrap.sh
RUN /home/pi/tools/mavlink_router/bootstrap.sh
RUN /home/pi/tools/ttyd/bootstrap.sh

# Companion-docker base image
FROM bluerobotics/companion-base:v0.0.4

# Install necessary tools
COPY tools /home/pi/tools
RUN /home/pi/tools/ardupilot_tools/bootstrap.sh
RUN /home/pi/tools/dnsmasq/bootstrap.sh
RUN /home/pi/tools/filebrowser/bootstrap.sh
RUN /home/pi/tools/linux2rest/bootstrap.sh
RUN /home/pi/tools/logviewer/bootstrap.sh
RUN /home/pi/tools/nginx/bootstrap.sh

# Install custom libraries
COPY libs /home/pi/libs
RUN /home/pi/libs/install-libs.sh

# Set tmux configuration file
COPY configuration/tmux.conf /etc/tmux.conf
COPY configuration/motd /etc/motd

# Install services
COPY services /home/pi/services
RUN /home/pi/services/install-services.sh
COPY start-companion-core /usr/bin/start-companion-core

# Copy binaries from downloadBinaries to this stage
COPY --from=downloadBinaries \
    /usr/bin/bridges \
    /usr/bin/mavlink2rest \
    /usr/bin/mavlink-camera-manager \
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

# Start
ENTRYPOINT /usr/bin/start-companion-core && sleep infinity
