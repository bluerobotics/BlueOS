FROM bluerobotics/companion-base:v0.0.1

# Install necessary tools
COPY tools /home/pi/tools
RUN /home/pi/tools/mavlink_router/bootstrap.py
RUN /home/pi/tools/mavlink_camera_manager/bootstrap.sh
RUN /home/pi/tools/mavlink2rest/bootstrap.sh
RUN /home/pi/tools/linux2rest/bootstrap.sh
RUN /home/pi/tools/bridges/bootstrap.sh
RUN /home/pi/tools/ttyd/bootstrap.sh

# Install services
COPY services /home/pi/services
COPY start-companion-core /usr/bin/start-companion-core
RUN /home/pi/services/install-services.sh

# Start
ENTRYPOINT /usr/bin/start-companion-core && sleep infinity
