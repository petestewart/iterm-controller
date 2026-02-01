#!/bin/bash

PLAN_FILE="PLAN.md"

while grep -q '^- \[ \]' "$PLAN_FILE"; do
  echo "=== Running next task ==="

  if command -v jq >/dev/null 2>&1; then
    claude -p "$(cat prompt.md)" \
      --output-format=stream-json \
      --include-partial-messages \
      --verbose \
      --dangerously-skip-permissions \
      | jq -rj '
        if .type == "stream_event" then
          if .event.type == "content_block_start" and .event.content_block.type == "text" then
            "\u001b[97m🤖 "
          elif .event.type == "content_block_delta" and .event.delta.type == "text_delta" then
            .event.delta.text
          elif .event.type == "content_block_stop" then
            "\u001b[0m\n"
          else empty end
        elif .type == "user" and .tool_use_result then
          "\u001b[90m➜ " + ((.tool_use_result.stdout // .content // "result") | tostring)[0:200] + "\u001b[0m\n"
        elif .type == "assistant" and .message.usage then
          "\u001b[90m   [" + (((.message.usage.input_tokens // 0) + (.message.usage.cache_read_input_tokens // 0) + (.message.usage.cache_creation_input_tokens // 0)) | tostring) + " tokens]\u001b[0m\n"
        else empty end
      '
    exit_code=${PIPESTATUS[0]}
    echo ""
  else
    stdbuf -oL -eL claude -p "$(cat prompt.md)" --output-format=stream-json \
      --include-partial-messages \
      --verbose \
      --dangerously-skip-permissions
    exit_code=$?
  fi

  if [ $exit_code -ne 0 ]; then
    echo ""
    echo "Claude exited with error (exit code: $exit_code). Waiting 15 minutes before retry..."
    for ((i=15; i>0; i--)); do
      printf "\rTime remaining: %02d:00" $i
      sleep 60
    done
    echo ""
  fi
done

echo "All tasks complete!"