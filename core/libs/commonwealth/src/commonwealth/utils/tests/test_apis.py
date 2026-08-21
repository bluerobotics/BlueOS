from commonwealth.utils.apis import PrettyJSONResponse
from fastapi import FastAPI
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
