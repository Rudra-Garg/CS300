#!/bin/sh
# proxy/entrypoint.sh

echo "Gateway Entrypoint: Starting setup..."
echo "DEBUG: ENABLE_LATENCY is set to: [$ENABLE_LATENCY]"
echo "DEBUG: LATENCY_PROXY_TO_CLOUD is set to: [$LATENCY_PROXY_TO_CLOUD]"

# Apply tc rules if enabled and variable is set
if [ "$ENABLE_LATENCY" = "true" ] && [ -n "$LATENCY_PROXY_TO_CLOUD" ]; then
  echo "Gateway Entrypoint: Applying $LATENCY_PROXY_TO_CLOUD delay to eth0 (towards Proxy/Mobiles)"
  
  # Build the tc command based on which parameters are set
  TC_CMD="tc qdisc replace dev eth0 root netem delay ${LATENCY_PROXY_TO_CLOUD:-0ms}"
  
  # Add jitter parameter only if it's set
  if [ -n "$JITTER_PROXY_TO_CLOUD" ]; then
    TC_CMD="$TC_CMD $JITTER_PROXY_TO_CLOUD"
  fi
  
  # Add loss parameter only if it's set
  if [ -n "$LOSS_PROXY_TO_CLOUD" ]; then
    TC_CMD="$TC_CMD loss $LOSS_PROXY_TO_CLOUD"
  fi
  
  # Execute the assembled command
  echo "Executing: $TC_CMD"
  eval $TC_CMD
  
  # Verify (optional)
  tc qdisc show dev eth0
else
  echo "Gateway Entrypoint: Latency disabled or LATENCY_PROXY_TO_CLOUD not set."
fi

echo "Gateway Entrypoint: Setup complete. Starting application..."
# Execute the main command passed to the script (CMD from Dockerfile or command from compose)
exec "$@"