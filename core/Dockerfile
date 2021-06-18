FROM node:current-buster-slim AS frontendBuilder

# Build frontend
COPY frontend /home/pi/frontend
RUN cd /home/pi/frontend && yarn install && yarn build --skip-plugins @vue/cli-plugin-eslint

FROM bluerobotics/companion-base:v0.0.1

# Install necessary tools
COPY tools /home/pi/tools
RUN /home/pi/tools/mavlink_router/bootstrap.py
RUN /home/pi/tools/mavlink_camera_manager/bootstrap.sh
RUN /home/pi/tools/mavlink2rest/bootstrap.sh
RUN /home/pi/tools/linux2rest/bootstrap.sh
RUN /home/pi/tools/bridges/bootstrap.sh
RUN /home/pi/tools/ttyd/bootstrap.sh
RUN /home/pi/tools/dnsmasq/bootstrap.sh
RUN /home/pi/tools/nginx/bootstrap.sh

# Install custom libraries
COPY libs /home/pi/libs
RUN /home/pi/libs/install-libs.sh

# Set tmux configuration file
COPY configuration/tmux.conf /etc/tmux.conf

# Install services
COPY services /home/pi/services
COPY start-companion-core /usr/bin/start-companion-core
RUN /home/pi/services/install-services.sh

# Copy frontend built on frontendBuild to this stage
COPY --from=frontendBuilder /home/pi/frontend/dist /home/pi/frontend

# Start
ENTRYPOINT /usr/bin/start-companion-core && sleep infinity
