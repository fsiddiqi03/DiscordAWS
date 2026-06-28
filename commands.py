import asyncio
import logging

import discord
from discord.ext import tasks, commands

from config import CHANNEL_ID, IP
from ec2 import EC2Manager
from minecraft import MinecraftServer
import embeds

logger = logging.getLogger("bot")

UNREACHABLE_THRESHOLD = 2


class ServerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ec2 = EC2Manager()
        self.mc = MinecraftServer(self.ec2)
        self.first_check = True
        # Track consecutive failures to reach the Minecraft server.
        # Used to distinguish transient network issues from actual server crashes,
        # so we don't auto-shutdown when there are players online but a temporary blip.
        self.unreachable_count = 0

    async def cog_load(self):
        self.auto_stop.start()

    async def cog_unload(self):
        self.auto_stop.cancel()

    async def send_public_message(self, interaction: discord.Interaction, embed: discord.Embed):
        try:
            await interaction.channel.send(embed=embed)
        except Exception as e:
            logger.error("send_public_message failed: %s", e)

    # ── Slash Commands ──────────────────────────────────────────────

    @discord.app_commands.command(name="start", description="Start the cloud and Minecraft server (5-9 min total)")
    async def start(self, interaction: discord.Interaction):
        logger.info("/start invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            ec2_status = await asyncio.to_thread(self.ec2.check_status)
            mc_status = await asyncio.to_thread(self.mc.is_running)
            if ec2_status == "running" and mc_status:
                logger.info("/start: everything already running")
                await interaction.followup.send(f"Server is already up! IP: `{IP}`")
                return
            if ec2_status in ("pending", "stopping"):
                logger.info("/start: EC2 currently '%s', wait and retry", ec2_status)
                await interaction.followup.send(f"Server is currently {ec2_status}. Please wait a minute and try again.")
                return
            await interaction.followup.send(
                "Starting everything up — this may take 4-5 minutes. I'll @ you when it's ready!"
            )
            # Start the EC2. systemd auto-launches Minecraft on EC2 boot.
            if not await asyncio.to_thread(self.ec2.start):
                logger.error("/start: EC2 failed to start")
                await interaction.followup.send("Cloud server failed to start. Please try again or contact Faris.")
                return
            # Reset the auto-check timer skip the first check 
            self.first_check = True
            self.auto_stop.restart()
            logger.info("/start: EC2 ready, waiting for MC to come online")
            # Poll until MC responds
            if not await asyncio.to_thread(self.mc.poll_server_status):
                logger.error("/start: MC never came up after 5 minutes")
                await interaction.followup.send("Cloud is up but Minecraft didn't respond. Contact Faris.")
                return
            logger.info("/start: MC ready")
            await self.send_public_message(interaction, embeds.server_ready(interaction.user.mention, IP))
        except Exception as e:
            logger.error("/start error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")

    @discord.app_commands.command(name="shut-down", description="closes the cloud server and minecraft server")
    async def shut_down(self, interaction: discord.Interaction):
        logger.info("/shut-down invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            # Case if EC2 is offline 
            ec2_status = await asyncio.to_thread(self.ec2.check_status)
            if ec2_status != "running":
                logger.info("/shut-down: EC2 already stopped")
                await interaction.followup.send("Server is already closed")
                return
            # Case if players are online
            player_count = await asyncio.to_thread(self.mc.player_count)
            if player_count > 0:
                logger.info("/shut-down: blocked, %d players still online", player_count)
                await interaction.followup.send("Can't close server while people are on!")
                return
            await interaction.followup.send("Closing server, this may take a few minutes...")
            # Attempt to close EC2
            if not await asyncio.to_thread(self.ec2.stop):
                logger.error("/shut-down: EC2 stop failed")
                await interaction.followup.send("Failed to stop the server, please try again later")
                return
            logger.info("/shut-down: EC2 stopped successfully")
            await self.send_public_message(interaction, embeds.shutdown(interaction.user.mention))
        except Exception as e:
            logger.error("/shut-down error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")

    @discord.app_commands.command(name="restart-server", description="restarts the minecraft server")
    async def restart_server(self, interaction: discord.Interaction):
        logger.info("/restart-server invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            ec2_status = await asyncio.to_thread(self.ec2.check_status)
            if ec2_status != "running":
                logger.info("/restart-server: ec2 is turned off")
                await interaction.followup.send(f"Can't restart server when cloud is off, run /start ")
                return
            player_count = await asyncio.to_thread(self.mc.player_count)
            if player_count > 0:
                logger.info("/restart-server: blocked, %d players still online", player_count)
                await interaction.followup.send("Can't restart server while people are on!")
                return
            await interaction.followup.send("Restarting server, this may take a few minutes...")
            # If MC is reachable, gracefully stop for a clean save first.
            # If it's already crashed/unreachable, skip straight to systemctl start.
            if await asyncio.to_thread(self.mc.is_running):
                logger.info("/restart-server: minecraft server on, closing server")
                await asyncio.to_thread(self.mc.stop)   
            # Bring MC back up via systemd
            logger.info("/restart-server: starting MC via systemctl")
            if not await asyncio.to_thread(self.mc.start):
                logger.error("/restart-server: MC never came back after 5 minutes")
                await interaction.followup.send("Restart failed — MC didn't come back. Contact Faris.")
                return
            logger.info("/restart-server: MC restarted successfully")
            await self.send_public_message(interaction, embeds.restart(interaction.user.mention, IP))
        except Exception as e:
            logger.error("/restart-server error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")
    
    @discord.app_commands.command(name="ip", description="obtain server ip")
    async def ip(self, interaction: discord.Interaction):
        logger.info("/ip invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        if await asyncio.to_thread(self.mc.is_running):
            logger.info("/ip: server online, returning IP")
            await interaction.followup.send("Server ip is: " + IP)
        else:
            logger.info("/ip: server offline")
            await interaction.followup.send("Server is closed")

    @discord.app_commands.command(name="status", description="obtain the status of the cloud and minecraft server")
    async def status(self, interaction: discord.Interaction):
        logger.info("/status invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            cloud_status = await asyncio.to_thread(self.ec2.check_status)
            mc_status = await asyncio.to_thread(self.mc.is_running)
            logger.info("/status: cloud=%s, minecraft=%s", cloud_status, mc_status)
            await interaction.followup.send(embed=embeds.status(cloud_status, mc_status, IP))
        except Exception as e:
            logger.error("/status error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")

    @discord.app_commands.command(name="info", description="Get information about the Minecraft server")
    async def info(self, interaction: discord.Interaction):
        logger.info("/info invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(embed=embeds.info(IP))

    # ── Auto-Stop Background Task ──────────────────────────────────

    @tasks.loop(minutes=10)
    async def auto_stop(self):
        logger.info("auto_stop cycle started")
        if self.first_check:
            self.first_check = False
            logger.info("auto_stop: skipping first check")
            return

        try:
            ec2_status = await asyncio.to_thread(self.ec2.check_status)
            if ec2_status != "running":
                logger.info("auto_stop: EC2 offline (%s), nothing to do", ec2_status)
                self.unreachable_count = 0
                return

            player_count = await asyncio.to_thread(self.mc.player_count)
            logger.info("auto_stop: player_count=%d, unreachable_count=%d", player_count, self.unreachable_count)

            if player_count > 0:
                self.unreachable_count = 0
                await asyncio.to_thread(self.mc.random_message)
                logger.info("auto_stop: %d players online, sent random message", player_count)
                return

            if player_count == 0:
                self.unreachable_count = 0
                reason = "Server automatically shut down due to inactivity (0 players for 30 minutes)"
                logger.info("auto_stop: 0 players, shutting down EC2")
                await asyncio.to_thread(self.ec2.stop)
                channel = self.bot.get_channel(CHANNEL_ID)
                if channel:
                    await channel.send(embed=embeds.auto_shutdown(reason))
                return

            # player_count == -1: can't reach Minecraft server
            self.unreachable_count += 1
            logger.warning("auto_stop: MC unreachable (%d/%d consecutive failures)", self.unreachable_count, UNREACHABLE_THRESHOLD)

            if self.unreachable_count >= UNREACHABLE_THRESHOLD:
                self.unreachable_count = 0
                reason = f"Server automatically shut down (Minecraft server unreachable for {UNREACHABLE_THRESHOLD} consecutive cycles - likely crashed)"
                logger.warning("auto_stop: threshold reached, shutting down EC2 — %s", reason)
                await asyncio.to_thread(self.ec2.stop)
                channel = self.bot.get_channel(CHANNEL_ID)
                if channel:
                    await channel.send(embed=embeds.auto_shutdown(reason))

        except Exception as e:
            logger.error("auto_stop error: %s", e, exc_info=True)

    @auto_stop.before_loop
    async def before_auto_stop(self):
        await self.bot.wait_until_ready()
