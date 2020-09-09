FROM python:buster
COPY setup.py startup.json.default main.py /bootstrap/
RUN python3 bootstrap/setup.py install
ENTRYPOINT /bootstrap/main.py
