
# Discord Bot for AWS Minecraft Server 

A Discord bot that allows users to manage a modded Minecraft server hosted on AWS EC2. Users can start/stop the server, check status, and execute management tasks directly through Discord slash commands.

**Current Server:** Minecraft 1.20.1 running [Create Chronicles: Bosses and Beyond](https://www.curseforge.com/minecraft/modpacks/create-chronicles-bosses-and-beyond)

---

## Architecture Overview

```
Discord User
     │
     ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Discord    │      │   EC2       │      │  Minecraft  │
│  Bot        │ ──── │   Manager   │ ──── │  Server     │
│  (main.py)  │      │  (aws.py)   │      │  (EC2)      │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
                            ▼
                     AWS Services
                     (EC2, SSM)
```

The bot runs as a persistent process (in a screen session) and communicates with AWS to manage the EC2 instance and Minecraft server.

---

## Discord Slash Commands

| Command | Description |
|---------|-------------|
| `/status` | Check if the cloud server and Minecraft server are running |
| `/start-cloud` | Start the AWS EC2 instance (takes 3-4 minutes) |
| `/start-minecraft` | Start the Minecraft server process (takes 2-5 minutes for modded) |
| `/shut-down` | Stop both the Minecraft server and EC2 instance |
| `/restart-server` | Restart just the Minecraft server without stopping EC2 |
| `/ip` | Get the current server IP address |
| `/info` | Display server info, modpack details, and startup instructions |

### Typical User Flow

1. Run `/status` to check server state
2. If cloud is offline, run `/start-cloud` and wait 3-4 minutes
3. Run `/start-minecraft` and wait 2-5 minutes (modded servers take longer)
4. Join the server using the IP provided
5. When done, run `/shut-down` or let auto-shutdown handle it

---

## Core Components

### `main.py` - Discord Bot

The main bot file handles all Discord interactions using discord.py with slash commands.

**Key Features:**
- **Async Threading**: All EC2 operations use `asyncio.to_thread()` to prevent blocking Discord's event loop. This ensures the bot stays responsive and doesn't disconnect during long operations (EC2 startup can take several minutes).
- **Public Embeds**: Server status changes are announced publicly in the channel with rich embeds.
- **Ephemeral Responses**: Command acknowledgments are sent privately to the user who ran them.
- **Auto-Stop Task**: A background task runs every 30 minutes to check for inactive servers.

### `aws.py` - EC2Manager Class

Handles all AWS and Minecraft server interactions.

| Method | Description |
|--------|-------------|
| `check_ec2_status()` | Returns EC2 state: `stopped`, `running`, `pending`, or `stopping` |
| `start_ec2()` | Starts EC2 instance and waits for status checks to pass |
| `stop_ec2()` | Stops EC2 instance and waits for confirmation |
| `get_ip()` | Returns the current public IP of the running instance |
| `check_server()` | Pings Minecraft server using mcstatus to verify it's responding |
| `start_minecraft_server()` | Sends SSM command to start server, polls for up to 5 minutes |
| `stop_minecraft()` | Sends `/stop` via RCON to gracefully stop Minecraft |
| `get_player_count()` | Returns number of online players (used for auto-shutdown) |
| `random_message()` | Sends a random fact to players via RCON (fun feature) |

**AWS Services Used:**
- **EC2**: Virtual machine hosting the Minecraft server
- **SSM (Systems Manager)**: Sends shell commands to EC2 without SSH
- **Boto3**: Python SDK for AWS API calls

**Minecraft Integration:**
- **mcstatus**: Pings the server to check if it's online and get player count
- **mcrcon**: Connects to Minecraft's RCON console for remote commands

---

## Auto-Shutdown Feature

The bot includes an automatic shutdown feature to save costs:

- Runs every **30 minutes**
- Checks if the server is running with **0 players**
- If empty, automatically shuts down both Minecraft and EC2
- Sends a notification embed to the Discord channel
- If players are online, sends a random fact to the server chat

This reduces monthly costs from ~$75-80 to ~$15-20 for typical usage.

---

## Scripts

### `setup.sh` - Initial Setup

Run once on a fresh Ubuntu server to install all dependencies:

```bash
chmod +x setup.sh
./setup.sh
```

**What it does:**
- Updates system packages
- Installs Python 3 and pip
- Installs Python libraries: discord.py, boto3, mcstatus, mcrcon, randfacts
- Installs AWS CLI

### `start.sh` - Bot Restart Script

Used for deployments and manual restarts:

```bash
./start.sh
```

**What it does:**
- Kills any existing bot screen session
- Pulls latest code from git
- Starts the bot in a new detached screen session

---

## CI/CD - GitHub Actions

The project includes automated deployment via GitHub Actions.

**File:** `.github/workflows/deploy.yml`

**Trigger:** Push to `master` branch

**What it does:**
1. SSHs into the EC2 instance hosting the bot
2. Runs `start.sh` to pull latest code and restart the bot

---

## Libraries Used 

| Library | Purpose |
|---------|---------|
| `discord.py` | Discord bot framework with slash command support |
| `boto3` | AWS SDK for Python (EC2 and SSM operations) |
| `mcstatus` | Query Minecraft servers for status and player info |
| `mcrcon` | RCON client for sending commands to Minecraft console |
| `randfacts` | Generate random facts (sent to players every 30 min) |
| `asyncio` | Non-blocking async operations for Discord bot stability |

---

## Cost Optimization

The auto-shutdown feature is the key to cost savings:

| Scenario | Monthly Cost |
|----------|--------------|
| Server running 24/7 | ~$75-80 |
| With auto-shutdown (2-3 weeks playtime) | ~$15-20 |

The bot ensures you only pay for the hours you actually play.
