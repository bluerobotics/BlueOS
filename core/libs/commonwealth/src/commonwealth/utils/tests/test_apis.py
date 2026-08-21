from commonwealth.utils.apis import (
    GenericErrorHandlingRoute,
    PrettyJSONResponse,
    StackedHTTPException,
)
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel


class Payload(BaseModel):
    value: str


def test_pretty_json_response_uses_response_model_in_openapi_schema() -> None:
    app = FastAPI(default_response_class=PrettyJSONResponse)

    @app.get("/payload", response_model=Payload)
    def get_payload() -> Payload:
        return Payload(value="test")

    response_schema = app.openapi()["paths"]["/payload"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert response_schema == {"$ref": "#/components/schemas/Payload"}


def test_pretty_json_response_render_indents_body() -> None:
    body = PrettyJSONResponse({"a": 1, "b": 2}).body
    assert body == b'{\n  "a": 1, \n  "b": 2\n}'


def test_generic_error_handling_route_reraises_http_400() -> None:
    app = FastAPI()
    app.router.route_class = GenericErrorHandlingRoute

    @app.get("/bad-request")
    def bad_request() -> None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad")

    response = TestClient(app).get("/bad-request")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "bad"


def test_generic_error_handling_route_keeps_http_500() -> None:
    app = FastAPI()
    app.router.route_class = GenericErrorHandlingRoute

    @app.get("/server-error")
    def server_error() -> None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="boom")

    response = TestClient(app).get("/server-error")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "boom"


def test_generic_error_handling_route_wraps_unhandled_exception() -> None:
    app = FastAPI()
    app.router.route_class = GenericErrorHandlingRoute

    @app.get("/unhandled")
    def unhandled() -> None:
        raise RuntimeError("unexpected")

    response = TestClient(app).get("/unhandled")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "unexpected" in response.json()["detail"]


def test_stacked_http_exception_includes_cause_message() -> None:
    exception = StackedHTTPException(status_code=status.HTTP_404_NOT_FOUND, error=RuntimeError("missing"))
    assert exception.status_code == status.HTTP_404_NOT_FOUND
    assert "missing" in exception.detail
