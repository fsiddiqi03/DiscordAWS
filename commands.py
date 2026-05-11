import asyncio
import logging

import discord
from discord.ext import tasks, commands

from config import CHANNEL_ID, IP
from aws import EC2Manager
import embeds

logger = logging.getLogger("bot")

UNREACHABLE_THRESHOLD = 2


class ServerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ec2 = EC2Manager()
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

    @discord.app_commands.command(name="start-cloud", description="starts the cloud server for the minecraft server")
    async def start_cloud(self, interaction: discord.Interaction):
        logger.info("/start-cloud invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            ec2_status = await asyncio.to_thread(self.ec2.check_ec2_status)
            if ec2_status == "stopped":
                await interaction.followup.send("Starting the cloud server, please wait 3-4 minutes. I'll @ you when it's ready!")
                if await asyncio.to_thread(self.ec2.start_ec2):
                    self.first_check = True
                    logger.info("/start-cloud: EC2 started successfully")
                    await self.send_public_message(interaction, embeds.cloud_online(interaction.user.mention))
                else:
                    logger.error("/start-cloud: EC2 failed to start")
                    await interaction.followup.send("Cloud server failed please try again later or contact Faris")
            else:
                logger.info("/start-cloud: EC2 already in state '%s'", ec2_status)
                await interaction.followup.send("Cloud server already active, please use the /start-minecraft command")
        except Exception as e:
            logger.error("/start-cloud error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")

    @discord.app_commands.command(name="start-minecraft", description="starts the minecraft server")
    async def start_minecraft(self, interaction: discord.Interaction):
        logger.info("/start-minecraft invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            ec2_status = await asyncio.to_thread(self.ec2.check_ec2_status)
            minecraft_status = await asyncio.to_thread(self.ec2.check_server)
            if ec2_status == "stopped":
                logger.info("/start-minecraft: EC2 is stopped, cannot start MC")
                await interaction.followup.send("Please start the Cloud server first, using Start Cloud command")
            elif not minecraft_status:
                await interaction.followup.send("Starting Minecraft server, this may take 2-5 minutes for a modded server. I'll @ you when it's ready!")
                if await asyncio.to_thread(self.ec2.start_minecraft_server):
                    logger.info("/start-minecraft: MC server started successfully")
                    await self.send_public_message(interaction, embeds.minecraft_started(interaction.user.mention, IP))
                else:
                    logger.error("/start-minecraft: MC server failed to start")
                    await interaction.followup.send("Minecraft Server failed try again later")
            else:
                logger.info("/start-minecraft: MC server already running")
                await interaction.followup.send("Minecraft Server already On with ip: " + IP)
        except Exception as e:
            logger.error("/start-minecraft error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")

    @discord.app_commands.command(name="shut-down", description="closes the cloud server and minecraft server")
    async def shut_down(self, interaction: discord.Interaction):
        logger.info("/shut-down invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            if await asyncio.to_thread(self.ec2.check_ec2_status) == "running":
                player_count = await asyncio.to_thread(self.ec2.get_player_count)
                if player_count < 1:
                    logger.info("/shut-down: no players (%d), stopping EC2", player_count)
                    if await asyncio.to_thread(self.ec2.stop_ec2):
                        logger.info("/shut-down: EC2 stopped successfully")
                        await self.send_public_message(interaction, embeds.shutdown(interaction.user.mention))
                    else:
                        logger.error("/shut-down: EC2 stop failed")
                        await interaction.followup.send("Failed to stop the server")
                else:
                    logger.info("/shut-down: blocked, %d players still online", player_count)
                    await interaction.followup.send("Can't close server while people are on!")
            else:
                logger.info("/shut-down: EC2 already stopped")
                await interaction.followup.send("Server is already closed")
        except Exception as e:
            logger.error("/shut-down error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")

    @discord.app_commands.command(name="ip", description="obtain server ip")
    async def ip(self, interaction: discord.Interaction):
        logger.info("/ip invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        if await asyncio.to_thread(self.ec2.check_server):
            logger.info("/ip: server online, returning IP")
            await interaction.followup.send("Server ip is: " + IP)
        else:
            logger.info("/ip: server offline")
            await interaction.followup.send("Server is closed")

    @discord.app_commands.command(name="restart-server", description="restarts the minecraft server")
    async def restart_server(self, interaction: discord.Interaction):
        logger.info("/restart-server invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            if await asyncio.to_thread(self.ec2.check_server):
                await interaction.followup.send("Restarting server, this may take a few minutes...")
                if await asyncio.to_thread(self.ec2.stop_minecraft):
                    logger.info("/restart-server: MC stopped, starting again")
                    if await asyncio.to_thread(self.ec2.start_minecraft_server):
                        logger.info("/restart-server: MC restarted successfully")
                        ip = await asyncio.to_thread(self.ec2.get_ip)
                        await self.send_public_message(interaction, embeds.restart(interaction.user.mention, ip))
                    else:
                        logger.error("/restart-server: MC start failed after stop")
                        await interaction.followup.send("server start failed")
                else:
                    logger.error("/restart-server: MC stop failed")
                    await interaction.followup.send("server stop failed, try again")
            else:
                logger.info("/restart-server: server not running")
                await interaction.followup.send("server not on")
        except Exception as e:
            logger.error("/restart-server error: %s", e, exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}. Please try again later.")

    @discord.app_commands.command(name="status", description="obtain the status of the cloud and minecraft server")
    async def status(self, interaction: discord.Interaction):
        logger.info("/status invoked by %s", interaction.user)
        await interaction.response.defer(ephemeral=True)
        try:
            cloud_status = await asyncio.to_thread(self.ec2.check_ec2_status)
            mc_status = await asyncio.to_thread(self.ec2.check_server)
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

    @tasks.loop(minutes=30)
    async def auto_stop(self):
        logger.info("auto_stop cycle started")
        if self.first_check:
            self.first_check = False
            logger.info("auto_stop: skipping first check")
            return

        try:
            ec2_status = await asyncio.to_thread(self.ec2.check_ec2_status)
            if ec2_status != "running":
                logger.info("auto_stop: EC2 offline (%s), nothing to do", ec2_status)
                self.unreachable_count = 0
                return

            player_count = await asyncio.to_thread(self.ec2.get_player_count)
            logger.info("auto_stop: player_count=%d, unreachable_count=%d", player_count, self.unreachable_count)

            if player_count > 0:
                self.unreachable_count = 0
                await asyncio.to_thread(self.ec2.random_message)
                logger.info("auto_stop: %d players online, sent random message", player_count)
                return

            if player_count == 0:
                self.unreachable_count = 0
                reason = "Server automatically shut down due to inactivity (0 players for 30 minutes)"
                logger.info("auto_stop: 0 players, shutting down EC2")
                await asyncio.to_thread(self.ec2.stop_ec2)
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
                await asyncio.to_thread(self.ec2.stop_ec2)
                channel = self.bot.get_channel(CHANNEL_ID)
                if channel:
                    await channel.send(embed=embeds.auto_shutdown(reason))

        except Exception as e:
            logger.error("auto_stop error: %s", e, exc_info=True)

    @auto_stop.before_loop
    async def before_auto_stop(self):
        await self.bot.wait_until_ready()
