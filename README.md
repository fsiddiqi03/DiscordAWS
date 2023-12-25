
# Discord Bot for AWS Minecraft Server 

This Discord bot allows users to manage a Minecraft server hosted on an AWS EC2 instance. Users can start and stop the server, retrieve the server's IP address, and execute other management tasks directly through Discord commands. 


## Discord Command and Features

- /start-cloud 
- /start-minecraft
- /restart-server
- /ip
- /shut-down
- /status
- Auto-Check Server

User use the bot by first running the /status command in discord to check if the cloud or minecraft server are turned on. If the the cloud server is off the user will use the
/start-cloud command to get the cloud server started. Once the cloud server started which takes 2-3 minutes the user will be asked to start the minecraft server using the /star-minecraft command. Once the server is launched the user will be told the server has started and will give them the ip to join the server. 
The discord bot runs a check every 30 minutes, where it will the ping the server to see if its active without any players, if thats the case the discord bot will close the server and the AWS ec2 instance to save money and resources. The simple function brings down cost from $75-80 to rougly $15-20 for 2-3 weeks of play time. There is also a manual shut down feature using the command /shut-down, which shuts down the server and ec2 instance even if players are active on the server. 


## Libraries Used 

- boto3 [used to communicate with the AWS ec2 instance]
- time [used during while loops to check for server status]
- mcstatus [used obtain server status and player count]
- mcron [used to send command remotely to the minecraft server console]
- discord.py [library used to build the disord bot]
- randomfacts [used to send a random fact to the user playing on the server every 30 minutes]


