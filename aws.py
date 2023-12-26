import boto3
import time
from botocore.exceptions import WaiterError
from mcstatus import JavaServer
from mcrcon import MCRcon 
from randfacts import get_fact
from config import RCON_PASSWORD, instance_id, port



class EC2Manager:
    def __init__(self, region="us-east-2"):
        self.instance_id = instance_id
        self.ec2 = boto3.client("ec2", region_name=region) # used to communicate with the ec2 instane (start, stop, get ip)
        self.ssm = boto3.client("ssm", region_name=region) # used to send command to the ec2 instance 
        self.RCON_PASSWORD = RCON_PASSWORD # used to send commands to minecraft server terminal 
        self.port = port # port used for sending command remotely to minecraft server terminal

    # checks the status of the ec2 instance 
    def check_ec2_status(self):
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        # will return either stopped, running, pending, or stopping
        return state
    
    def start_ec2(self):
        status = self.check_ec2_status()
        # run the start ec2 only if the ec2 instance is turned off 
        if status == "stopped":       
            try:
                self.ec2.start_instances(InstanceIds=[self.instance_id])
                # use waiter to check when the 2 initialized checks are completed 
                # instantce status must be okay for the minecraft server to be launched 
                waiter = self.ec2.get_waiter('instance_status_ok')
                waiter.wait(InstanceIds=[self.instance_id])
                return True
            except WaiterError:
                return False
        else:
            return True
        
    def stop_ec2(self):
        # stops ec2 instance 
        status = self.check_ec2_status()
        if status == "running":
            try:
                self.ec2.stop_instances(InstanceIds=[self.instance_id])
                # use wait to check when the instance is stopped then return True 
                waiter = self.ec2.get_waiter("instance_stopped")
                waiter.wait(InstanceIds=[self.instance_id])
                return True
            except WaiterError:
                return False
        return True
    
    # Ip changes every time the ec2 instance is launched 
    # this function will check whether the instance is running and then return the ip of the running ec2 instance 
    def get_ip(self):
        if self.check_ec2_status() == "running":
            response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            public_ip = instance.get("PublicIpAddress", None)
            return public_ip
    
    # use the mcserver python library to ping the server
    # if the server gets pinged return true, if it fails return false 
    def check_server(self):
        if self.check_ec2_status() == "running":
            ip = self.get_ip()
            # obtain the server varaible as server using the ec2 instacne ip and mcserver
            server = JavaServer.lookup(ip)
            try:
                latency = server.status().latency
                return True 
            except:
                return False
        else:
            return False
        
    # use this function in the discord bot to start the server
    # starts the server by sending the start command via ssm
    # need to cd into the server folder and launch the server, 
    # include screen -dmS to keep the server open, without screen the server will crash after one hour. 
    def start_minecraft_server(self):
        # attempt to start the minecraft server by sending it the start command
        # use try to catch any errors 
        try:
            self.ssm.send_command(
                InstanceIds=[self.instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    'commands': [
                        'cd /opt/minecraft/server && screen -dmS minecraft java -Xmx12288M -Xms12288M -jar server.jar nogui' 
                    ]
                }
            )
            # use while to check the status of the minecraft server after sending the command 
            # checks the server 15 times in a 75 second window 
            attempts = 0
            while attempts < 15:
                if self.check_server():
                    return True
                time.sleep(5)
                attempts += 1 
            return False  
        except Exception as e:
            print(e)
            return False
    
    # get player count of the server if its running, 
    # function returns the player count, the bot will use this to determine if the server should keep running or be turned off  
    # return -1 if server is off. 
    def get_player_count(self):
        if self.check_server():
            ip = self.get_ip()
            server = JavaServer.lookup(ip)
            player_count = server.status().players.online
            return player_count
        return -1
    

    
    # use RCON to remotely connect into the minecraft server terminal and run the command /stop
    # this stops the server without stoping the ec2 instance
    # used in the restart-server function in discord bot 
    # runs a 75 seconds timer to check when the server is turned off, returning true  
    def stop_minecraft(self):
        ip = self.get_ip()

        command = "/stop"
        
        with MCRcon(ip, self.RCON_PASSWORD, self.port) as mcr:
            response = mcr.command(command)
            print(response)
        
        attempts = 0
        while attempts < 15:
            if not self.check_server():
                return True
            time.sleep(5)
            attempts += 1 
        return False 
        

    # use RCON to remotely send a random fact using the random fact python library. 
    def random_message(self):
        ip = self.get_ip()

        fact = get_fact(False)
        command = f"/say {fact}"
        try:
            with MCRcon(ip, self.RCON_PASSWORD, self.port) as mcr:
                response = mcr.command(command)
                print(response)
        except Exception as e:
            print(e)
        












