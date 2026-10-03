#!/usr/bin/env bash
# Snowflake CLI (`snow`) operations against EgleView's real Cortex Agents.
#
# Setup (one time):
#   pip install snowflake-cli
#   snow connection add --connection-name egleview \
#     --account <SNOWFLAKE_ACCOUNT> --user <SNOWFLAKE_USER> --password <SNOWFLAKE_PASSWORD> \
#     --warehouse <SNOWFLAKE_WAREHOUSE> --database <SNOWFLAKE_DATABASE> --schema PUBLIC \
#     --role <SNOWFLAKE_ROLE>
#   (values come from backend/.env)
#
# Usage:
#   ./snow_cli_tools.sh list-agents
#   ./snow_cli_tools.sh ask <AGENT_NAME> "<question>"
#
# `list-agents` shows every CREATE AGENT object deployed by setup_domain_agents.py
# (7 primary + 7 _SUB, via `SHOW AGENTS`). `ask` sends a real question straight to
# SNOWFLAKE.CORTEX.DATA_AGENT_RUN for the given agent and prints its full tool-use /
# tool-result / final-answer trace — the same call sf_lib/domain_agent.py makes,
# just triggered from the CLI instead of from the app.

set -euo pipefail

CONNECTION="${SNOW_CONNECTION:-egleview}"
DATABASE="${SNOW_DATABASE:-EGLE_VIEW}"

cmd="${1:-}"

case "$cmd" in
  list-agents)
    snow sql -c "$CONNECTION" -q "SHOW AGENTS IN DATABASE ${DATABASE};"
    ;;
  ask)
    agent="${2:?Usage: $0 ask <AGENT_NAME> \"<question>\"}"
    question="${3:?Usage: $0 ask <AGENT_NAME> \"<question>\"}"
    payload=$(python3 -c '
import json, sys
question = sys.argv[1]
payload = {
    "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
    "stream": False,
}
print(json.dumps(payload).replace("\x27", "\x27\x27"))
' "$question")
    snow sql -c "$CONNECTION" -q \
      "SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('${DATABASE}.PUBLIC.${agent}', '${payload}') AS RESP;"
    ;;
  *)
    echo "Usage: $0 {list-agents|ask <AGENT_NAME> \"<question>\"}" >&2
    exit 1
    ;;
esac
