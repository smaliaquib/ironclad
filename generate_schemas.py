"""Regenerates schemas.generated.json from each tool's Pydantic Input model.

Run this after editing any tool's Input model, then commit the result:

    uv run python generate_schemas.py

CI re-runs this to a temp file and diffs it against the committed copy, so a
tool's published schema can never silently drift from what it actually
validates at call time.
"""

import json
from pathlib import Path

from tools.add_numbers import NAME as ADD_NUMBERS_NAME
from tools.add_numbers import AddNumbersInput
from tools.echo import NAME as ECHO_NAME
from tools.echo import EchoInput
from tools.get_time import NAME as GET_TIME_NAME
from tools.get_time import GetTimeInput

OUTPUT_PATH = Path(__file__).parent / "schemas.generated.json"


def main() -> None:
    schemas = {
        ECHO_NAME: EchoInput.model_json_schema(),
        GET_TIME_NAME: GetTimeInput.model_json_schema(),
        ADD_NUMBERS_NAME: AddNumbersInput.model_json_schema(),
    }
    OUTPUT_PATH.write_text(json.dumps(schemas, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
