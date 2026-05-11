import discord


def cloud_online(user_mention: str) -> discord.Embed:
    embed = discord.Embed(
        title="☁️ Cloud Server Online!",
        description=f"{user_mention} The cloud server is now ready!",
        color=discord.Color.green(),
    )
    embed.add_field(name="Next Step", value="Use `/start-minecraft` to start the Minecraft server", inline=False)
    embed.add_field(name="Status", value="✅ Online", inline=True)
    return embed


def minecraft_started(user_mention: str, ip: str) -> discord.Embed:
    embed = discord.Embed(
        title="🎮 Minecraft Server Started!",
        description=f"Server has been started by {user_mention}",
        color=discord.Color.green(),
    )
    embed.add_field(name="Server IP", value=f"`{ip}`", inline=False)
    embed.add_field(name="Status", value="✅ Online", inline=True)
    embed.set_footer(text="Happy mining!")
    return embed


def shutdown(user_mention: str) -> discord.Embed:
    embed = discord.Embed(
        title="🔴 Server Shutdown",
        description=f"The Minecraft and cloud servers have been shut down by {user_mention}",
        color=discord.Color.red(),
    )
    embed.add_field(name="Status", value="❌ Offline", inline=True)
    embed.set_footer(text="Thank you for playing!")
    return embed


def restart(user_mention: str, ip: str) -> discord.Embed:
    embed = discord.Embed(
        title="🔄 Server Restarted",
        description=f"The Minecraft server has been restarted by {user_mention}",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Server IP", value=f"`{ip}`", inline=False)
    embed.add_field(name="Status", value="✅ Online", inline=True)
    return embed


def status(cloud_status: str, mc_status: bool, ip: str) -> discord.Embed:
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
        color=color,
    )
    embed.add_field(name="☁️ Cloud Server", value=cloud_display, inline=True)
    embed.add_field(name="🎮 Minecraft Server", value=mc_display, inline=True)

    if mc_status:
        embed.add_field(name="🌐 Server IP", value=f"`{ip}`", inline=False)

    embed.set_footer(text="Use /info for modpack details")
    return embed


def info(ip: str) -> discord.Embed:
    embed = discord.Embed(
        title="📋 Server Information",
        description="Here's everything you need to know about our Minecraft server!",
        color=discord.Color.blue(),
    )
    embed.add_field(name="🌐 Server IP", value=f"`{ip}`", inline=False)
    embed.add_field(name="🎮 Minecraft Version", value="Java Edition 26.1", inline=True)
    embed.add_field(name="📦 Server Type", value="Vanilla", inline=True)
    embed.add_field(
        name="🔒 Whitelist",
        value="This server is whitelisted. Message an admin to get added!",
        inline=False,
    )
    embed.add_field(
        name="🚀 How to Start the Server",
        value=(
            "1️⃣ Use `/status` to check if servers are running\n"
            "2️⃣ Use `/start-cloud` if the cloud server is offline\n"
            "3️⃣ Use `/start-minecraft` to launch the Minecraft server"
        ),
        inline=False,
    )
    embed.set_footer(text="Make sure you're whitelisted before trying to join!")
    return embed


def auto_shutdown(reason: str) -> discord.Embed:
    return discord.Embed(
        title="⏰ Auto-Shutdown",
        description=reason,
        color=discord.Color.yellow(),
    )
