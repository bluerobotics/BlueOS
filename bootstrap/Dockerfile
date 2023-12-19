FROM python:3.11.7-slim-bullseye

COPY startup.json.default bootstrap/ /bootstrap/
COPY main.py /
COPY pip.conf /etc/
RUN python3 bootstrap/setup.py install
ENTRYPOINT /main.py
