#!/usr/bin/env python3
import logging
import os

from pathlib import Path

import connexion
import flask
from connexion.resolver import RestyResolver

from waitress import serve

logging.basicConfig(level=logging.INFO)

HTML_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "html")


def index():
    index = Path.joinpath(HTML_FOLDER, "index.html")
    return open(index, "r").read()


def resource(path, filename):
    path = Path.joinpath(HTML_FOLDER, f"static/{path}")
    return flask.send_from_directory(path, filename)


# Flask CORS appears to be not working anymore with connexion
# Check: https://github.com/zalando/connexion/issues/357
def set_cors_headers_on_response(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"
    response.headers["Access-Control-Allow-Methods"] = "OPTIONS"
    return response


if __name__ == "__main__":
    if os.geteuid() != 0:
        print(
            "You need to have root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting."
        )
        exit(1)

    connexion_app = connexion.FlaskApp(__name__)
    connexion_app.app.after_request(set_cors_headers_on_response)
    connexion_app.add_url_rule("/", "index", index)
    connexion_app.add_url_rule("/static/<path:path>/<path:filename>", "resource", resource)
    connexion_app.add_api(
        "swagger/cable-guy.yaml",
        arguments={"title": "Cable Guy API"},
        resolver=RestyResolver("api"),
    )
    # http://localhost:9090/v1.0/ethernet
    serve(connexion_app, host="0.0.0.0", port=9090)
