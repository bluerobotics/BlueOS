FROM nginx
RUN apt update && apt install -y curl python3 python3-pip tmux
RUN curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
RUN `curl -fsSL https://github.com/tsl0922/ttyd/releases/download/1.6.1/ttyd_linux.$(dpkg --print-architecture | sed "s/amd64/x86_64/") -o /usr/bin/ttyd` && chmod +x /usr/bin/ttyd
COPY static /supervisor/static
COPY setup.py /supervisor/setup.py
RUN python3 /supervisor/setup.py install
COPY nginx.conf /etc/nginx/nginx.conf
RUN mkdir -p /supervisor/.config
COPY . /supervisor/
RUN chmod +x /supervisor/supervisor.py
RUN chmod +x /supervisor/start.sh
ENTRYPOINT /supervisor/start.sh && sleep infinity