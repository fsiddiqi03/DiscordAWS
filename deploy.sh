#!/bin/bash
set -e

# Go to repo directory (the one containing this script)
cd "$(dirname "$0")"

# Stop existing screen session if running
screen -S discordbot -X quit || true

# Pull latest code
git pull

# Start new screen session running the bot
screen -dmS discordbot python3 bot.py
