import boto3
import time
from botocore.exceptions import WaiterError
from mcstatus import JavaServer
from mcrcon import MCRcon 
from randfacts import get_fact
from config import RCON_PASSWORD


class EC2Manager:
    def __init__(self, instance_id="i-0c1ded99c0ff7c3b8", region="us-east-2"):
        self.instance_id = instance_id
        self.ec2 = boto3.client("ec2", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)

    def check_ec2_status(self):
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        # will return either stopped, running, pending, or stopping
        return state
    
    def start_ec2(self):
        status = self.check_ec2_status()
        if status == "stopped":       
            try:
                self.ec2.start_instances(InstanceIds=[self.instance_id])
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
                waiter = self.ec2.get_waiter("instance_stopped")
                waiter.wait(InstanceIds=[self.instance_id])
                return True
            except WaiterError:
                return False
        return True
    
    def get_ip(self):
        if self.check_ec2_status() == "running":
            response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            public_ip = instance.get("PublicIpAddress", None)
            return public_ip
    
    def check_server(self):
        if self.check_ec2_status() == "running":
            ip = self.get_ip()
            server = JavaServer.lookup(ip)
            try:
                latency = server.status().latency
                return True
            except:
                return False
        else:
            return False
        
    # use this function in the discord bot to start the server
    def start_minecraft_server(self):
        # attempt to start the minecraft server by sending it a command
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
    
    # def auto_turn_off
    # check the minecraft server to see if any players are online every 30 mins, if there is no one turn off the ec2 instance.
    def auto_check(self):
        if self.check_server():
            ip = self.get_ip()
            server = JavaServer.lookup(ip)
            player_count = server.status().players.online
            if player_count > 0:
                return False
            else:
                return True
        return False
    

    
    #
    def stop_minecraft(self):
        ip = self.get_ip()
        port = 25575
        password = RCON_PASSWORD


        command = "/stop"

        with MCRcon(ip, password, port) as mcr:
            response = mcr.command(command)
            print(response)
        
        attempts = 0
        while attempts < 15:
            if not self.check_server():
                return True
            time.sleep(5)
            attempts += 1 
        return False 
        


    def random_message(self):
        ip = self.get_ip()
        port = 25575
        password = RCON_PASSWORD

        fact = get_fact(False)
        command = f"/say {fact}"
        try:
            with MCRcon(ip, password, port) as mcr:
                response = mcr.command(command)
                print(response)
        except Exception as e:
            print(e)
        













