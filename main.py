import discord
import asyncio
import logging
from discord.ext import tasks, commands
from config import TOKEN, CHANNEL_ID, IP
from aws import EC2Manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

ec2 = EC2Manager()

FIRST_CHECK = True
# Track consecutive failures to reach the Minecraft server.
# Used to distinguish transient network issues from actual server crashes,
# so we don't auto-shutdown when there are players online but a temporary blip.
unreachable_count = 0
UNREACHABLE_THRESHOLD = 2  # Shut down after 2 consecutive failures (~1 hour of unreachability)

bot = commands.Bot(command_prefix="!", intents = discord.Intents.all())

@bot.event
async def on_ready():
    logger.info("Bot is on and Ready!")
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d command(s)", len(synced))
        auto_stop.start()
    except Exception as e:
        logger.error("on_ready failed: %s", e)


async def send_public_message(interaction: discord.Interaction, message: str, embed: discord.Embed = None):
    """Helper function to send a public message to the channel where the command was used"""
    try:
        if embed:
            await interaction.channel.send(embed=embed)
        else:
            await interaction.channel.send(message)
    except Exception as e:
        logger.error("send_public_message failed: %s", e)


@bot.tree.command(name="start-cloud", description="starts the cloud server for the minecraft server")
async def Start(interaction: discord.Interaction):
    logger.info("/start-cloud invoked by %s", interaction.user)
    await interaction.response.defer(ephemeral = True)
    try:
        ec2_status = await asyncio.to_thread(ec2.check_ec2_status)
        if ec2_status == "stopped":
            await interaction.followup.send("Starting the cloud server, please wait 3-4 minutes. I'll @ you when it's ready!")
            if await asyncio.to_thread(ec2.start_ec2):
                global FIRST_CHECK
                FIRST_CHECK = True
                logger.info("/start-cloud: EC2 started successfully")
                # Send public embed announcing cloud is ready
                embed = discord.Embed(
                    title="☁️ Cloud Server Online!",
                    description=f"{interaction.user.mention} The cloud server is now ready!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Next Step", value="Use `/start-minecraft` to start the Minecraft server", inline=False)
                embed.add_field(name="Status", value="✅ Online", inline=True)
                await send_public_message(interaction, "", embed=embed)
            else:
                logger.error("/start-cloud: EC2 failed to start")
                await interaction.followup.send("Cloud server failed please try again later or contact Faris")
        else:
            logger.info("/start-cloud: EC2 already in state '%s'", ec2_status)
            await interaction.followup.send("Cloud server already active, please use the /start-minecraft command")
    except Exception as e:
        logger.error("/start-cloud error: %s", e, exc_info=True)
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name="start-minecraft", description="starts the minecraft server")
async def Start_Minecraft(interaction: discord.Interaction):
    logger.info("/start-minecraft invoked by %s", interaction.user)
    await interaction.response.defer(ephemeral = True)
    try:
        ec2_status = await asyncio.to_thread(ec2.check_ec2_status)
        minecraft_status = await asyncio.to_thread(ec2.check_server)
        if ec2_status == "stopped":
            logger.info("/start-minecraft: EC2 is stopped, cannot start MC")
            await interaction.followup.send("Please start the Cloud server first, using Start Cloud command")
        elif not minecraft_status:
            await interaction.followup.send("Starting Minecraft server, this may take 2-5 minutes for a modded server. I'll @ you when it's ready!")
            if await asyncio.to_thread(ec2.start_minecraft_server):
                logger.info("/start-minecraft: MC server started successfully")
                # Send public message with server info
                embed = discord.Embed(
                    title="🎮 Minecraft Server Started!",
                    description=f"Server has been started by {interaction.user.mention}",
                    color=discord.Color.green()
                )
                embed.add_field(name="Server IP", value=f"`{IP}`", inline=False)
                embed.add_field(name="Status", value="✅ Online", inline=True)
                embed.set_footer(text="Happy mining!")
                await send_public_message(interaction, "", embed=embed)
            else:
                logger.error("/start-minecraft: MC server failed to start")
                await interaction.followup.send("Minecraft Server failed try again later")
        else:
            logger.info("/start-minecraft: MC server already running")
            await interaction.followup.send("Minecraft Server already On with ip: " + IP)
    except Exception as e:
        logger.error("/start-minecraft error: %s", e, exc_info=True)
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name = "shut-down", description= "closes the cloud server and minecraft server")
async def Stop(interaction: discord.Interaction):
    logger.info("/shut-down invoked by %s", interaction.user)
    await interaction.response.defer(ephemeral = True)
    try:
        if await asyncio.to_thread(ec2.check_ec2_status) == "running":
            player_count = await asyncio.to_thread(ec2.get_player_count)
            if player_count < 1:
                logger.info("/shut-down: no players (%d), stopping EC2", player_count)
                if await asyncio.to_thread(ec2.stop_ec2):
                    logger.info("/shut-down: EC2 stopped successfully")
                    # Send public message about shutdown
                    embed = discord.Embed(
                        title="🔴 Server Shutdown",
                        description=f"The Minecraft and cloud servers have been shut down by {interaction.user.mention}",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Status", value="❌ Offline", inline=True)
                    embed.set_footer(text="Thank you for playing!")
                    await send_public_message(interaction, "", embed=embed)
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


@bot.tree.command(name = "ip", description= "obtain server ip")
async def Ip(interaction: discord.Interaction):
    logger.info("/ip invoked by %s", interaction.user)
    await interaction.response.defer(ephemeral = True)
    if await asyncio.to_thread(ec2.check_server):
        logger.info("/ip: server online, returning IP")
        await interaction.followup.send("Server ip is: " + IP)
    else:
        logger.info("/ip: server offline")
        await interaction.followup.send("Server is closed")


@bot.tree.command(name="restart-server", description= "restarts the minecraft serer")
async def restart(interaction: discord.Interaction):
    logger.info("/restart-server invoked by %s", interaction.user)
    await interaction.response.defer(ephemeral=True)
    try:
        if await asyncio.to_thread(ec2.check_server):
            await interaction.followup.send("Restarting server, this may take a few minutes...")
            if await asyncio.to_thread(ec2.stop_minecraft):
                logger.info("/restart-server: MC stopped, starting again")
                if await asyncio.to_thread(ec2.start_minecraft_server):
                    logger.info("/restart-server: MC restarted successfully")
                    # Send public message about restart
                    embed = discord.Embed(
                        title="🔄 Server Restarted",
                        description=f"The Minecraft server has been restarted by {interaction.user.mention}",
                        color=discord.Color.orange()
                    )
                    ip = await asyncio.to_thread(ec2.get_ip)
                    embed.add_field(name="Server IP", value=f"`{ip}`", inline=False)
                    embed.add_field(name="Status", value="✅ Online", inline=True)
                    await send_public_message(interaction, "", embed=embed)
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


@bot.tree.command(name="status", description= "obtain the status of the cloud and minecraft server")
async def status(interaction: discord.Interaction):
    logger.info("/status invoked by %s", interaction.user)
    await interaction.response.defer(ephemeral=True)
    try:
        cloud_status = await asyncio.to_thread(ec2.check_ec2_status)
        mc_status = await asyncio.to_thread(ec2.check_server)
        logger.info("/status: cloud=%s, minecraft=%s", cloud_status, mc_status)
        
        # Determine colors and status text
        if cloud_status == "running" and mc_status:
            color = discord.Color.green()
            cloud_display = "✅ Online"
            mc_display = "✅ Online"
        elif cloud_status == "running":
            color = discord.Color.orange()
            cloud_display = "✅ Online"
            mc_display = "❌ Offline"
        else:
            color = discord.Color.red()
            cloud_display = "❌ Offline"
            mc_display = "❌ Offline"
        
        embed = discord.Embed(
            title="📊 Server Status",
            description="Current status of all servers",
            color=color
        )
        embed.add_field(name="☁️ Cloud Server", value=cloud_display, inline=True)
        embed.add_field(name="🎮 Minecraft Server", value=mc_display, inline=True)
        
        # Add IP if server is running
        if mc_status:
            embed.add_field(name="🌐 Server IP", value=f"`{IP}`", inline=False)
        
        embed.set_footer(text="Use /info for modpack details")
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error("/status error: %s", e, exc_info=True)
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name="info", description="Get information about the Minecraft server")
async def info(interaction: discord.Interaction):
    logger.info("/info invoked by %s", interaction.user)
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="📋 Server Information",
        description="Here's everything you need to know about our Minecraft server!",
        color=discord.Color.blue()
    )
    embed.add_field(name="🌐 Server IP", value=f"`{IP}`", inline=False)
    embed.add_field(name="🎮 Minecraft Version", value="1.20.1", inline=True)
    embed.add_field(name="📦 Modpack", value="DeceasedCraft - Urban Zombie Apocalypse", inline=True)
    embed.add_field(
        name="🔗 Modpack Link", 
        value="[Download on CurseForge](https://www.curseforge.com/minecraft/modpacks/deceasedcraft)", 
        inline=False
    )
    embed.add_field(
        name="🚀 How to Start the Server",
        value=(
            "1️⃣ Use `/status` to check if servers are running\n"
            "2️⃣ Use `/start-cloud` if the cloud server is offline\n"
            "3️⃣ Use `/start-minecraft` to launch the Minecraft server\n\n"
            "⏳ **Note:** Since this is a modded server, startup can take **2-5 minutes**. Be patient!"
        ),
        inline=False
    )
    embed.set_footer(text="Make sure to install the modpack before joining!")
    
    await interaction.followup.send(embed=embed)


@tasks.loop(minutes=30)
async def auto_stop():
    global FIRST_CHECK, unreachable_count
    logger.info("auto_stop cycle started")
    if FIRST_CHECK:
        FIRST_CHECK = False
        logger.info("auto_stop: skipping first check")
        return

    try:
        ec2_status = await asyncio.to_thread(ec2.check_ec2_status)
        if ec2_status != "running":
            logger.info("auto_stop: EC2 offline (%s), nothing to do", ec2_status)
            unreachable_count = 0
            return

        player_count = await asyncio.to_thread(ec2.get_player_count)
        logger.info("auto_stop: player_count=%d, unreachable_count=%d", player_count, unreachable_count)

        if player_count > 0:
            unreachable_count = 0
            await asyncio.to_thread(ec2.random_message)
            logger.info("auto_stop: %d players online, sent random message", player_count)
            return

        if player_count == 0:
            unreachable_count = 0
            reason = "Server automatically shut down due to inactivity (0 players for 30 minutes)"
            logger.info("auto_stop: 0 players, shutting down EC2")
            await asyncio.to_thread(ec2.stop_ec2)
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="⏰ Auto-Shutdown",
                    description=reason,
                    color=discord.Color.yellow()
                )
                await channel.send(embed=embed)
            return

        # player_count == -1: can't reach Minecraft server
        unreachable_count += 1
        logger.warning("auto_stop: MC unreachable (%d/%d consecutive failures)", unreachable_count, UNREACHABLE_THRESHOLD)

        if unreachable_count >= UNREACHABLE_THRESHOLD:
            unreachable_count = 0
            reason = f"Server automatically shut down (Minecraft server unreachable for {UNREACHABLE_THRESHOLD} consecutive cycles - likely crashed)"
            logger.warning("auto_stop: threshold reached, shutting down EC2 — %s", reason)
            await asyncio.to_thread(ec2.stop_ec2)
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="⏰ Auto-Shutdown",
                    description=reason,
                    color=discord.Color.yellow()
                )
                await channel.send(embed=embed)

    except Exception as e:
        logger.error("auto_stop error: %s", e, exc_info=True)


@auto_stop.before_loop
async def before_auto_stop():
    await bot.wait_until_ready()


if __name__ == "__main__":
    bot.run(TOKEN)
