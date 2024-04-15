
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


## Installation

Before installing, ensure you have Python 3.x installed on your system. Then, follow these steps to get your bot up and running, you can either run the bot locally or host it in the cloud (AWS, GCP):

### Linux Setup

Run the provided `setup.sh` script:

```bash
chmod +x setup.sh
./setup.sh
```
### macOS Setup

You'll need Python 3 and pip. After installing these, run:

```bash
pip3 install discord.py boto3 mcstatus mcrcon randfacts
brew install awscli
```

### Windows Setup

Ensure Python and pip are installed on your system. First, install the necessary Python packages including the AWS CLI using pip:

```bash
pip install discord.py boto3 mcstatus mcrcon randfacts awscli
pip install awscli
```


## Usage

1. **Set up your bot on Discord and obtain a bot token.**
2. **Configure AWS Credentials:**
   Before running the bot, you need to configure your AWS credentials to allow the bot to interact with your AWS EC2 instance. Open a terminal and run the following command:

   ```bash
   aws configure
   ```
   You'll be prompted to enter your AWS Access Key ID, Secret Access Key, region, and output format. Enter the appropriate details obtained from your AWS account.

3. **Create a `config.py` file in the same directory as your bot scripts and define your bot token and AWS credentials:**

   ```python
   TOKEN = 'your_discord_bot_token'
   RCON_PASSWORD = 'your_rcon_password'
   instance_id = 'your_aws_instance_id'
   port = 25565  # Default Minecraft port
   ```
4. Run the bot:
   
   ```bash
   python main.py
   ```

