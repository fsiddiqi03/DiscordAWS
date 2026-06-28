
# Discord Bot for AWS Minecraft Server 

A Discord bot that allows users to manage a modded Minecraft server hosted on AWS EC2. Users can start/stop the server, check status, and execute management tasks directly through Discord slash commands.


---

## Architecture Overview

```
                          Minecraft Players
                                │
                                ▼
                        ┌──────────────┐
                        │  Route 53    │
                        │  (DNS)       │
                        └──────┬───────┘
                               │ resolves to
                        ┌──────────────┐
                        │  TCPShield   │
                        │  (DDoS Proxy)│
                        └──────┬───────┘
                               │ proxied traffic
 Discord Users                 │
      │          ┌─────────────────────────────────────┐
      ▼          │         AWS VPC (us-east-2)         │
 ┌──────────┐    │                                     │
 │ Discord  │    │  ┌──────────────┐  ┌──────────────┐ │
 │ API      │◄───┼──│  Bot EC2     │  │  Server EC2  │◄┼── TCPShield
 └──────────┘    │  │              │  │              │ │
                 │  │  main.py     │  │  Minecraft   │ │
                 │  │  commands.py │  │  Server      │ │
                 │  │  ec2.py      │  │  (Java)      │ │
                 │  │  minecraft.py│  │              │ │
                 │  │  embeds.py   │  │              │ │
                 │  └──────┬───────┘  └──────────────┘ │
                 │         │                 ▲         │
                 │         │  Private IP     │         │
                 │         │  (mcstatus,     │         │
                 │         │   RCON)         │         │
                 │         └─────────────────┘         │
                 │         │                           │
                 │         ▼                           │
                 │  AWS APIs (EC2, SSM)                │
                 └─────────────────────────────────────┘
```

**Two EC2 instances** live inside the same AWS VPC:

- **Bot EC2** — Always-on, lightweight instance that runs the Discord bot in a `screen` session. Manages the Server EC2 through AWS APIs and communicates with the Minecraft process over the VPC's private network.
- **Server EC2** — Larger instance that hosts the Minecraft server. Started and stopped on demand by the bot to save costs. A **systemd service (`minecraft`)** is enabled on this instance, so the Minecraft server launches automatically every time the instance boots — the bot only needs to start the EC2 instance and the server comes up on its own.

**Route 53** handles DNS for the server's domain, resolving it to TCPShield's proxy addresses. 
**TCPShield** then sits in front of the Server EC2 as a reverse proxy, providing DDoS protection. Players connect through the domain name, but the bot bypasses both DNS and TCPShield entirely by using the server's private IP within the VPC for status pings (mcstatus) and remote commands (RCON).

---

## Discord Slash Commands

| Command | Description |
|---------|-------------|
| `/status` | Check if the cloud server and Minecraft server are running |
| `/start` | Start the EC2 instance and Minecraft server in one step (5-9 min total) |
| `/shut-down` | Stop both the Minecraft server and EC2 instance |
| `/restart-server` | Restart just the Minecraft server without stopping EC2 |
| `/ip` | Get the current server IP address |
| `/info` | Display server info, version details, and startup instructions |

> **Note:** Starting the Minecraft server is fully automated. A **systemd service** on the Server EC2 launches Minecraft automatically whenever the instance boots, so `/start` only needs to start the EC2 instance and then wait for Minecraft to come online — no separate `/start-minecraft` step is needed.

### Typical User Flow

1. Run `/status` to check server state
2. If everything is offline, run `/start` and wait 5-9 minutes — the bot will `@` you when the server is ready
3. Join the server using the IP provided
4. When done, run `/shut-down` or let auto-shutdown handle it

---

## Core Components

### `main.py` - Entry Point

Configures logging, creates the Discord bot, loads the `ServerCog`, and starts the event loop.

### `commands.py` - ServerCog (Slash Commands & Auto-Stop)

Contains all Discord slash commands and the auto-stop background task as a single `commands.Cog`.

**Key Features:**
- **Async Threading**: All EC2/Minecraft operations use `asyncio.to_thread()` to prevent blocking Discord's event loop. This ensures the bot stays responsive and doesn't disconnect during long operations (EC2 startup can take several minutes).
- **Public Embeds**: Server status changes are announced publicly in the channel with rich embeds.
- **Ephemeral Responses**: Command acknowledgments are sent privately to the user who ran them.
- **Unreachable Threshold**: Tracks consecutive failures to reach the Minecraft server. Only triggers auto-shutdown after multiple failed cycles, so transient network blips don't kill a session with active players.

### `ec2.py` - EC2Manager Class

Pure AWS-side operations for the Minecraft server's EC2 instance.

| Method | Description |
|--------|-------------|
| `check_status()` | Returns EC2 state (`running`, `stopped`, `pending`, `stopping`) |
| `start()` | Starts the EC2 instance and waits for status checks to pass |
| `stop()` | Stops the EC2 instance and waits for confirmation |
| `private_ip()` | Returns the instance's VPC-internal private IP |
| `send_ssm_command()` | Sends shell commands to the instance via SSM |

### `minecraft.py` - MinecraftServer Class

Operations that talk directly to the running Minecraft process. Uses the EC2 instance's **private IP** for all communication so traffic stays inside the VPC (bypasses TCPShield).

| Method | Description |
|--------|-------------|
| `is_running()` | Pings the Minecraft server via mcstatus to check if it's responding |
| `player_count()` | Returns number of online players, or `-1` if unreachable |
| `start()` | Runs `systemctl start minecraft` via SSM, then polls until it's responding (up to 5 min) |
| `stop()` | Runs `systemctl stop minecraft` via SSM and waits for the server to go offline |
| `poll_server_status()` | Waits up to 5 minutes for the server to start responding to status pings |
| `random_message()` | Sends a random fact to the server chat via RCON |

### `embeds.py` - Discord Embed Builders

Factory functions that return styled `discord.Embed` objects for all bot messages (`server_ready`, `shutdown`, `restart`, `status`, `info`, `auto_shutdown`).

**AWS Services Used:**
- **EC2**: Virtual machines — one for the bot, one for the Minecraft server
- **SSM (Systems Manager)**: Sends shell commands to the Server EC2 without SSH
- **Boto3**: Python SDK for AWS API calls

**Minecraft Integration:**
- **mcstatus**: Pings the server to check if it's online and get player count
- **rcon**: Connects to Minecraft's RCON console for remote commands (stop, chat messages)

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

## Server EC2 - systemd Auto-Launch

The Server EC2 runs the Minecraft server as a **systemd service** named `minecraft`. The service is enabled to start on boot, which means:

- When the bot starts the Server EC2 (via `/start`), Minecraft launches automatically as soon as the OS comes up — no separate start command is needed.
- The bot controls the running server through SSM by issuing `systemctl start minecraft` / `systemctl stop minecraft` (used by `/restart-server` and `/shut-down` flows).
- systemd's `TimeoutStopSec` is set to ~120s to give the Java process enough time to save the world and shut down cleanly.

Because of this, the `/start` command simply boots the EC2 instance and then polls (up to 5 minutes) until the Minecraft server responds to status pings.

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
- Installs Python libraries: discord.py, boto3, mcstatus, rcon, randfacts
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

The project includes two GitHub Actions workflows for managing the Bot EC2 instance.

### `deploy.yml` - Automated Deployment

**Trigger:** Push to `master` branch

**What it does:**
1. SSHs into the Bot EC2 instance
2. Runs `start.sh` to pull the latest code and restart the bot

### `start-bot.yml` - Manual Bot Start

**Trigger:** Manual run from the GitHub Actions tab (`workflow_dispatch`)

**What it does:**
1. SSHs into the Bot EC2 instance
2. Runs `start.sh` to (re)start the bot

This is useful for bringing the bot back up on demand — for example after the Bot EC2 has been rebooted — without having to push a commit.

Both workflows authenticate over SSH using the `SSH_PRIVATE_KEY`, `SSH_HOST`, and `USER_NAME` repository secrets.

---

## Libraries Used 

| Library | Purpose |
|---------|---------|
| `discord.py` | Discord bot framework with slash command support |
| `boto3` | AWS SDK for Python (EC2 and SSM operations) |
| `mcstatus` | Query Minecraft servers for status and player info |
| `rcon` | RCON client for sending commands to Minecraft console |
| `randfacts` | Generate random facts (sent to players every 30 min) |
| `asyncio` | Non-blocking async operations for Discord bot stability |

---

## Cost Optimization

The auto-shutdown feature is the key to cost savings:

| Scenario | Monthly Cost |
|----------|--------------|
| Server running 24/7 | ~$75-80 |
| With auto-shutdown (4-5 weeks playtime) | ~$15-20 |

The bot ensures you only pay for the hours you actually play.
