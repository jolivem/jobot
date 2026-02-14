#!/bin/bash
set -e
cd ~/jobot
echo "Pulling latest changes..."
git pull origin main
echo "Building..."
docker compose build --quiet
echo "Restarting services..."
docker compose up -d
echo "Cleaning old images..."
docker image prune -f --filter "until=24h" > /dev/null
echo "Done!"
