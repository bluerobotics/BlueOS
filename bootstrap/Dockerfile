FROM debian:buster-slim
RUN apt update && apt install -y python3 python3-setuptools python3-pip --no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
COPY startup.json.default bootstrap/ /bootstrap/
COPY main.py /
COPY blueos_aliases/.bash_aliases_blueos /etc/blueos/.bash_aliases_blueos
RUN python3 bootstrap/setup.py install
ENTRYPOINT /main.py
