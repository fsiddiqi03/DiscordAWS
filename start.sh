#!/bin/bash

cd /home/ubuntu/DiscordAWS

# Kill existing screen session if it exists
screen -S discordbot -X quit 2>/dev/null

# Pull latest changes
git pull origin master

# Start bot in a new screen session
screen -dmS discordbot python3 main.py

echo "Bot restarted successfully!"