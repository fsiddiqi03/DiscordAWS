import discord
import asyncio
from discord.ext import tasks, commands
from config import TOKEN, CHANNEL_ID, IP
from aws import EC2Manager

ec2 = EC2Manager()
FIRST_CHECK = True

bot = commands.Bot(command_prefix="!", intents = discord.Intents.all())

@bot.event
async def on_ready():
    print("Bot is on and Ready!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        auto_stop.start()
    except Exception as e:
        print(e)


async def send_public_message(interaction: discord.Interaction, message: str, embed: discord.Embed = None):
    """Helper function to send a public message to the channel where the command was used"""
    try:
        if embed:
            await interaction.channel.send(embed=embed)
        else:
            await interaction.channel.send(message)
    except Exception as e:
        print(f"Error sending public message: {e}")


@bot.tree.command(name="start-cloud", description="starts the cloud server for the minecraft server")
async def Start(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    try:
        ec2_status = await asyncio.to_thread(ec2.check_ec2_status)
        if ec2_status == "stopped":
            await interaction.followup.send("Starting the cloud server, please wait 3-4 minutes. I'll @ you when it's ready!")
            if await asyncio.to_thread(ec2.start_ec2):
                global FIRST_CHECK
                FIRST_CHECK = True
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
                await interaction.followup.send("Cloud server failed please try again later or contact Faris")
        else:
            await interaction.followup.send("Cloud server already active, please use the /start-minecraft command")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name="start-minecraft", description="starts the minecraft server")
async def Start_Minecraft(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    try:
        ec2_status = await asyncio.to_thread(ec2.check_ec2_status)
        minecraft_status = await asyncio.to_thread(ec2.check_server)
        if ec2_status == "stopped":
            await interaction.followup.send("Please start the Cloud server first, using Start Cloud command")
        elif not minecraft_status:
            await interaction.followup.send("Starting Minecraft server, this may take 2-5 minutes for a modded server. I'll @ you when it's ready!")
            if await asyncio.to_thread(ec2.start_minecraft_server):
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
                await interaction.followup.send("Minecraft Server failed try again later")
        else:
            await interaction.followup.send("Minecraft Server already On with ip: " + IP)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name = "shut-down", description= "closes the cloud server and minecraft server")
async def Stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    try:
        if await asyncio.to_thread(ec2.check_ec2_status) == "running":
            if await asyncio.to_thread(ec2.get_player_count) == 0:
                if await asyncio.to_thread(ec2.stop_ec2):
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
                    await interaction.followup.send("Failed to stop the server")
            else:
                await interaction.followup.send("Can't close server while people are on!")
        else:
            await interaction.followup.send("Server is already closed")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name = "ip", description= "obtain server ip")
async def Ip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    if await asyncio.to_thread(ec2.check_server):
        await interaction.followup.send("Server ip is: " + IP)
    else:
        await interaction.followup.send("Server is closed")


@bot.tree.command(name="restart-server", description= "restarts the minecraft serer")
async def restart(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        if await asyncio.to_thread(ec2.check_server):
            await interaction.followup.send("Restarting server, this may take a few minutes...")
            if await asyncio.to_thread(ec2.stop_minecraft):
                if await asyncio.to_thread(ec2.start_minecraft_server):
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
                    await interaction.followup.send("server start failed")
            else:
                await interaction.followup.send("server stop failed, try again")
        else:
            await interaction.followup.send("server not on")
    except Exception as e:
        print(e)
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name="status", description= "obtain the status of the cloud and minecraft server")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        cloud_status = await asyncio.to_thread(ec2.check_ec2_status)
        mc_status = await asyncio.to_thread(ec2.check_server)
        
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
        print(e)
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name="info", description="Get information about the Minecraft server")
async def info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="📋 Server Information",
        description="Here's everything you need to know about our Minecraft server!",
        color=discord.Color.blue()
    )
    embed.add_field(name="🌐 Server IP", value=f"`{IP}`", inline=False)
    embed.add_field(name="🎮 Minecraft Version", value="1.20.1", inline=True)
    embed.add_field(name="📦 Modpack", value="Prominence II: Hasturian Era", inline=True)
    embed.add_field(
        name="🔗 Modpack Link", 
        value="[Download on CurseForge](https://www.curseforge.com/minecraft/modpacks/prominence-2-hasturian-era)", 
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
    global FIRST_CHECK
    if FIRST_CHECK:
        FIRST_CHECK = False
        print("Skipping first auto_stop check")
        return

    try:
        if await asyncio.to_thread(ec2.check_ec2_status) != "running":
            print("server offline")
            return

        player_count = await asyncio.to_thread(ec2.get_player_count)
        print("checking server")

        if player_count > 0:
            await asyncio.to_thread(ec2.random_message)
            print(f"server online with {player_count} players!")
            return

        # Shut down if no players (0) or Minecraft server isn't running (-1)
        if player_count == 0:
            reason = "Server automatically shut down due to inactivity (0 players for 30 minutes)"
            print("no active players, turning server off")
        else:
            reason = "Server automatically shut down (EC2 was running but Minecraft server was not active)"
            print("EC2 was on but Minecraft server was off, turning everything off")

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
        print(e)


@auto_stop.before_loop
async def before_auto_stop():
    await bot.wait_until_ready()


if __name__ == "__main__":
    bot.run(TOKEN)
