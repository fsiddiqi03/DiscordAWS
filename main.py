import discord
from discord import app_commands
from discord.ext import commands
from server_status import check_server
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
    server_status = check_server()
    if server_status:
        await interaction.followup.send("Server is already online!!!")
    else:
        await interaction.followup.send("Starting server...")
        # this where we would pass the ec2 command to launch the miencraft server 


@bot.tree.command(name = "stop", description= "stops the minecraft server")
async def Stop(interaction: discord.Interaction):
    await interaction.response.send_message("Checking server status...")
    server_status = check_server()
    if server_status:
        await interaction.followup.send("Server is closing..")
        # add function to close server 
    else:
        await interaction.followup.send("Server is already off! Use /start to open server")


@bot.tree.command(name = "hello", description= "stops the minecraft server")
async def Stop(interaction: discord.Interaction):
    await interaction.response.send_message("Hello")
  







bot.run(TOKEN)


    