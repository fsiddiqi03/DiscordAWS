import discord
from discord import app_commands
from discord.ext import tasks, commands
from config import TOKEN
from aws import EC2Manager



ec2 = EC2Manager()

bot = commands.Bot(command_prefix="!", intents = discord.Intents.all())

@bot.event
async def on_ready():
    print("Bot is on and Ready!")
    auto_stop.start()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)



@bot.tree.command(name="start-cloud", description="starts the cloud server for the minecraft server")
async def Start(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    try:
        ec2_status = ec2.check_ec2_status()
        if ec2_status == "stopped":
            await interaction.followup.send("Starting the cloud server, Once this completes you may start the minecraft server, please wait 2-3 minutes")
            if ec2.start_ec2():
                await interaction.followup.send("Cloud server started please use the Start Minecraft command")
            else:
                await interaction.followup.send("Cloud server failed please try again later or contact Faris")
        else:
            await interaction.followup.send("cloud server already active, please use the /start_minecraft command")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name="start-minecraft", description="starts the minecraft server")
async def Start(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    try:
        ec2_status = ec2.check_ec2_status()
        minecraft_status = ec2.check_server()
        ip = ec2.get_ip()
        if ec2_status == "stopped":
            await interaction.followup.send("Please start the Cloud server first, using Start Cloud command")
        if not minecraft_status:
            if ec2.start_minecraft_server():
                await interaction.followup.send("Minecraft Server Started with IP: " + ip)
            else:
                await interaction.followup.send("Minecraft Server failed try again later")
        else:
            await interaction.followup.send("Minecraft Server already On with ip: " + ip)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}. Please try again later.")


@bot.tree.command(name = "shut-down", description= "closes the cloud server and minecraft server")
async def Stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    if ec2.check_ec2_status() == "running":
        # still need to add a method to get player count to make sure server does not turn off when people are online. 
        if ec2.stop_ec2():
            await interaction.followup.send("Server has been closed")
    else:
        await interaction.followup.send("Server is already closed")
  


@bot.tree.command(name = "ip", description= "obtain server ip")
async def Ip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    if ec2.check_server():
        ip = ec2.get_ip()
        await interaction.followup.send("server ip is: " + ip)
    else:
        await interaction.followup.send("Server is closed")


@bot.tree.command(name="restart-server", description= "restarts the minecraft serer")
async def restart(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        if ec2.check_server():
            if ec2.stop_minecraft():
                if ec2.start_minecraft_server():
                  await interaction.followup.send("server restarted")
                else:
                    await interaction.followup.send("server start failed")
            else:
                await interaction.followup.send("server stop failed, try again")
        else:
            await interaction.followup.send("server not on")
    except Exception as e:
        print(e)



@tasks.loop(minutes=30)
async def auto_stop():
    ec2.random_message()
    print("checking server")
    try:
        if ec2.auto_check():
            ec2.stop_ec2()
            print("no active player, turning server off")
        else:
            print("players either online or server off")
    except Exception as e:
        print(e)
        
@auto_stop.before_loop
async def before_auto_stop():
    await bot.wait_until_ready()
  



if __name__ == "__main__":
    bot.run(TOKEN)


    