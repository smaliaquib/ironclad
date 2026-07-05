from pydantic import BaseModel, ValidationError

NAME = "echo"
DESCRIPTION = "Echoes back the provided message. Dummy tool for testing the MCP gateway end-to-end."


class EchoInput(BaseModel):
    message: str


class EchoOutput(BaseModel):
    echoed: str


def handler(event, context):
    try:
        parsed = EchoInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}
    return EchoOutput(echoed=parsed.message).model_dump()
