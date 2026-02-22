#!/usr/bin/env bash
# Launch a filebrowser Docker container to browse a local folder.
# Usage: ./scripts/browse.sh [folder] [port]
#   folder  - directory to serve (default: current directory)
#   port    - host port (default: 8080)

set -euo pipefail

FOLDER="${1:-.}"
PORT="${2:-8080}"

FOLDER="$(cd "$FOLDER" && pwd)"
CONTAINER_NAME="videospeeder-browse"

# Stop any existing instance
if docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
  echo "Stopping existing $CONTAINER_NAME container..."
  docker stop "$CONTAINER_NAME" >/dev/null
  sleep 1
fi

echo "Serving: $FOLDER"
echo "Browse:  http://localhost:$PORT"
echo "Stop:    docker stop $CONTAINER_NAME"
echo

# Run in background, grab password from logs, then attach
docker run -d --rm --name "$CONTAINER_NAME" \
  -v "$FOLDER":/srv \
  -p "$PORT":80 \
  filebrowser/filebrowser >/dev/null

# Wait for startup and extract generated password
sleep 1
PASS=$(docker logs "$CONTAINER_NAME" 2>&1 | grep -oP "password: \K.*")
echo "Login:   admin / $PASS"
echo

# Follow logs (Ctrl+C to detach; container keeps running)
docker logs -f "$CONTAINER_NAME"
