FROM debian:buster-slim

# Create default user folder
RUN mkdir -p /home/pi

# Install gstreamer
COPY install_gst.sh /install_gst.sh
RUN GST_VERSION=1.17.2 ./install_gst.sh && rm /install_gst.sh

# Install python3 and pip as default
RUN apt install -y --no-install-recommends python3
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install Mavlink Router
COPY tools /home/pi/tools
RUN /home/pi/tools/mavlink_router/bootstrap.py

# Install necessary tools for basic usage
RUN apt install -y file locate tmux unzip nano htop iputils-ping watch wget iproute2

# Install services
COPY services /home/pi/services
COPY start-companion-core /usr/bin/start-companion-core
RUN /home/pi/services/install-services.sh

# Start
ENTRYPOINT /usr/bin/start-companion-core && sleep infinity
