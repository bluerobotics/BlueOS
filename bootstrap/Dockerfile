FROM python:buster
RUN pip3 install docker
COPY dockers.json.default /
COPY run.py /run.py
RUN chmod +x /run.py
ENTRYPOINT /run.py
