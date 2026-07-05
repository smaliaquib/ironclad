from pydantic import BaseModel, ValidationError

NAME = "add_numbers"
DESCRIPTION = "Adds two numbers together. Dummy tool for testing a multi-field input schema."


class AddNumbersInput(BaseModel):
    a: float
    b: float


class AddNumbersOutput(BaseModel):
    result: float


def handler(event, context):
    try:
        parsed = AddNumbersInput.model_validate(event)
    except ValidationError as e:
        return {"error": str(e)}
    return AddNumbersOutput(result=parsed.a + parsed.b).model_dump()
