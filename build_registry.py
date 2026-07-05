"""Rebuilds registry.json from the current Pydantic-generated schemas and
each tool's real, just-deployed Lambda ARN.

Run by buildspecs/buildspec-cd.yml's post_build phase, after
generate_schemas.py and after every tool's Lambda code has been deployed.
Kept as a standalone script (not an inline heredoc in the buildspec) because
CodeBuild's buildspec YAML validator misparses embedded Python containing
"key": value patterns even inside a literal block scalar.
"""

import json
import os
import subprocess

TOOLS = [
    "echo",
    "get_time",
    "add_numbers",
    "slack_post_message",
    "slack_read_history",
    "slack_list_channels",
    "gmail_search",
    "gmail_read",
    "gmail_send",
    "gmail_reply",
    "brave_web_search",
    "brave_news_search",
]


def main() -> None:
    descriptions = {}
    for tool in TOOLS:
        mod = __import__(f"tools.{tool}", fromlist=["NAME", "DESCRIPTION"])
        descriptions[mod.NAME] = mod.DESCRIPTION

    schemas = json.load(open("schemas.generated.json"))
    name_prefix = os.environ["NAME_PREFIX"]
    region = os.environ["AWS_DEFAULT_REGION"]

    registry = []
    for tool in TOOLS:
        function_name = f"{name_prefix}-mcp-tool-{tool}"
        arn = (
            subprocess.check_output(
                [
                    "aws",
                    "lambda",
                    "get-function",
                    "--function-name",
                    function_name,
                    "--region",
                    region,
                    "--query",
                    "Configuration.FunctionArn",
                    "--output",
                    "text",
                ]
            )
            .decode()
            .strip()
        )
        registry.append(
            {
                "name": tool,
                "description": descriptions[tool],
                "input_schema": schemas[tool],
                "lambda_arn": arn,
            }
        )

    with open("registry.json", "w") as f:
        json.dump(registry, f)


if __name__ == "__main__":
    main()
