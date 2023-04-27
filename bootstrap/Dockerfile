FROM python:3.9-slim-bullseye
COPY startup.json.default bootstrap/ /bootstrap/
COPY main.py /
RUN python3 bootstrap/setup.py install
ENTRYPOINT /main.py
