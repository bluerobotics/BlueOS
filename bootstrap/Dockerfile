FROM python:3.11.7-slim-bullseye

# Ensure that the git describe exists and also is in valid format as well
# The format can be invalid if someone is build BlueOS without a tag as reference
ARG GIT_DESCRIBE_TAGS
ENV GIT_DESCRIBE_TAGS=${GIT_DESCRIBE_TAGS:-0.0.0-0-g00000000}
RUN <<-EOF
set -e

    if [[ ! $GIT_DESCRIBE_TAGS =~ -[0-9]+-g[a-f0-9]{8}$ ]]; then
        echo "Invalid format: $GIT_DESCRIBE_TAGS (E.g: <TAG>-<COMMIT_NUMBER>-g<SHORT_HASH>)"
        exit 1
    fi

EOF

COPY startup.json.default bootstrap/ /bootstrap/
COPY main.py /
COPY pip.conf /etc/
RUN python3 bootstrap/setup.py install
ENTRYPOINT ["/main.py"]