from datetime import datetime, timezone

from pydantic import BaseModel, ValidationError

NAME = "get_time"
DESCRIPTION = "Returns the current UTC time. Dummy tool for testing a zero-argument call."


class GetTimeInput(BaseModel):
    pass


class GetTimeOutput(BaseModel):
    utc_time: str


def handler(event, context):
    try:
        GetTimeInput.model_validate(event or {})
    except ValidationError as e:
        return {"error": str(e)}
    return GetTimeOutput(utc_time=datetime.now(timezone.utc).isoformat()).model_dump()
