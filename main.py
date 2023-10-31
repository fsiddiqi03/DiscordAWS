import discord
from discord import app_commands
from discord.ext import commands
from config import TOKEN
from aws import EC2Manager



ec2 = EC2Manager()

bot = commands.Bot(command_prefix="!", intents = discord.Intents.all())

@bot.event
async def on_ready():
    print("Bot is on and Ready!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)



@bot.tree.command(name="start", description="starts the minecraft server")
async def Start(interaction: discord.Interaction):
    await interaction.response.send_message("Checking server status...")
    try:
        ec2_status = ec2.check_ec2_status()
        minecraft_status = ec2.check_server()

        # If EC2 is off, turn it on.
        if ec2_status == "stopped":
            await interaction.followup.send("Starting server. Please wait until I give you the ip to join the server, this may take 1-2 minutes.")
            if not ec2.start_ec2():
                await interaction.followup.send("Failed to start EC2 instance. Please try again later.")
                return

        # At this point, EC2 should be on. If Minecraft is off, turn it on.
        if not minecraft_status:
            if not ec2.start_minecraft_server():
                await interaction.followup.send("server had trouble booting, please try again later")
                return

        # At this point, both EC2 and Minecraft should be on. Fetch the IP.
        ip = ec2.get_ip()
        if ip:
            await interaction.followup.send("server has started with the ip: " + ip)
        else:
            await interaction.followup.send("Failed to retrieve server IP. Please check the server status.")
            
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


 


@bot.tree.command(name = "stop", description= "stops the minecraft server")
async def Stop(interaction: discord.Interaction):
    await interaction.response.send_message("Checking server status...")
    if ec2.check_ec2_status() == "running":
        # still need to add a method to get player count to make sure server does not turn off when people are online. 
        if ec2.stop_ec2():
            await interaction.followup.send("Server has been closed")
    else:
        await interaction.followup.send("Server is already closed")
  


@bot.tree.command(name = "ip", description= "obtain server ip")
async def Ip(interaction: discord.Interaction):
    if ec2.check_server():
        ip = ec2.get_ip()
        await interaction.response.send_message("server ip is: " + ip)
    else:
        await interaction.response.send_message("Server is closed")

  







bot.run(TOKEN)


    