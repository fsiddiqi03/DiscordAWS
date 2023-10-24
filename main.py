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



@bot.tree.command(name = "start", description= "starts the minecraft server")
async def Start(interaction: discord.Interaction):
    # check if the server is already running
    await interaction.response.send_message("Checking server status...")
    if ec2.check_ec2_status() == "stopped":
        await interaction.followup.send("server is closed, starting server. Please wait until I give you the ip to join the server")
        if ec2.start_ec2():
            if ec2.start_minecraft_server():
                ip = ec2.get_ip()
                await interaction.followup.send("server has started with the ip: " + ip)
            else:
                await interaction.followup.send("server had trouble booting, please try again later")
    else:
        if ec2.check_server():
            ip = ec2.get_ip()
            await interaction.followup.send("sever is already online with the ip: " + ip)
        else:
            ec2.start_minecraft_server()
            ip = ec2.get_ip()
            await interaction.followup.send("server has started with the ip: " + ip)
 


@bot.tree.command(name = "stop", description= "stops the minecraft server")
async def Stop(interaction: discord.Interaction):
    await interaction.response.send_message("Checking server status...")
    if ec2.check_ec2_status() == "running":
        # still need to add a method to get player count to make sure server does not turn off when people are online. 
        if ec2.stop_ec2():
            await interaction.followup.send("Server has been closed")
    else:
        await interaction.followup.send("Server is already closed")
  


@bot.tree.command(name = "hello", description= "stops the minecraft server")
async def Stop(interaction: discord.Interaction):
    await interaction.response.send_message("Hello")
  







bot.run(TOKEN)


    