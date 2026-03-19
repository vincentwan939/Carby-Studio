#!/bin/bash
# Spawn a sprint agent using openclaw sessions_spawn
#
# Usage: spawn-sprint-agent.sh <agent_type> <sprint_id> <gate> <prompt_file> [work_item_id]

set -e

AGENT_TYPE="$1"
SPRINT_ID="$2"
GATE="$3"
PROMPT_FILE="$4"
WORK_ITEM_ID="${5:-}"

if [[ -z "$AGENT_TYPE" || -z "$SPRINT_ID" || -z "$GATE" || -z "$PROMPT_FILE" ]]; then
    echo "Usage: $0 <agent_type> <sprint_id> <gate> <prompt_file> [work_item_id]"
    exit 1
fi

# Read the processed prompt
PROMPT=$(cat "$PROMPT_FILE")

# Build label
if [[ -n "$WORK_ITEM_ID" ]]; then
    LABEL="sprint-${SPRINT_ID}-${AGENT_TYPE}-${WORK_ITEM_ID}"
else
    LABEL="sprint-${SPRINT_ID}-${AGENT_TYPE}"
fi

echo "Spawning ${AGENT_TYPE} agent for sprint ${SPRINT_ID} (Gate ${GATE})..."

# Spawn the agent using openclaw CLI
# Note: This requires openclaw to be installed and configured
openclaw sessions spawn \
    --task "$PROMPT" \
    --runtime subagent \
    --mode run \
    --label "$LABEL" \
    --timeout 3600

echo "Agent ${AGENT_TYPE} spawned successfully with label: ${LABEL}"
