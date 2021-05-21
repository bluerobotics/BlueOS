FROM python:3.9-slim-buster

# Create default user folder
RUN mkdir -p /home/pi

# Install gstreamer
COPY install_gst.sh /install_gst.sh
RUN GST_VERSION=1.17.2 ./install_gst.sh && rm /install_gst.sh

# Install necessary tools for basic usage
RUN apt install -y file locate tmux unzip nano htop iputils-ping watch wget iproute2

# Install necessary tools
COPY tools /home/pi/tools
RUN /home/pi/tools/mavlink_router/bootstrap.py
RUN /home/pi/tools/mavlink_camera_manager/bootstrap.sh
RUN /home/pi/tools/linux2rest/bootstrap.sh
RUN /home/pi/tools/bridges/bootstrap.sh

# Install services
COPY services /home/pi/services
COPY start-companion-core /usr/bin/start-companion-core
RUN /home/pi/services/install-services.sh

# Start
ENTRYPOINT /usr/bin/start-companion-core && sleep infinity
