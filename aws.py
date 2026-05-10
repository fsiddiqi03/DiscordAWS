import boto3
import time
import logging
from botocore.exceptions import WaiterError
from mcstatus import JavaServer
from rcon.source import Client
from randfacts import get_fact
from config import RCON_PASSWORD, instance_id, port

logger = logging.getLogger("aws")


class EC2Manager:
    def __init__(self, region="us-east-2"):
        self.instance_id = instance_id
        self.ec2 = boto3.client("ec2", region_name=region) # used to communicate with the ec2 instane (start, stop, get ip)
        self.ssm = boto3.client("ssm", region_name=region) # used to send command to the ec2 instance 
        self.RCON_PASSWORD = RCON_PASSWORD # used to send commands to minecraft server terminal 
        self.port = port # port used for sending command remotely to minecraft server terminal
        logger.info("EC2Manager initialized (region=%s, instance=%s)", region, self.instance_id)

    # checks the status of the ec2 instance 
    def check_ec2_status(self):
        logger.debug("check_ec2_status called")
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        logger.info("check_ec2_status -> %s", state)
        return state
    
    def start_ec2(self):
        logger.info("start_ec2 called")
        status = self.check_ec2_status()
        # run the start ec2 only if the ec2 instance is turned off 
        if status == "stopped":       
            try:
                logger.info("EC2 is stopped, sending start_instances request")
                self.ec2.start_instances(InstanceIds=[self.instance_id])
                # use waiter to check when the 2 initialized checks are completed 
                # instantce status must be okay for the minecraft server to be launched 
                waiter = self.ec2.get_waiter('instance_status_ok')
                logger.info("Waiting for instance_status_ok...")
                waiter.wait(InstanceIds=[self.instance_id])
                logger.info("start_ec2 -> True (instance now running)")
                return True
            except WaiterError as e:
                logger.error("start_ec2 -> False (WaiterError: %s)", e)
                return False
        else:
            logger.info("start_ec2 -> True (already in state: %s)", status)
            return True
        
    def stop_ec2(self):
        logger.info("stop_ec2 called")
        status = self.check_ec2_status()
        if status == "running":
            try:
                logger.info("EC2 is running, sending stop_instances request")
                self.ec2.stop_instances(InstanceIds=[self.instance_id])
                waiter = self.ec2.get_waiter("instance_stopped")
                logger.info("Waiting for instance_stopped...")
                waiter.wait(InstanceIds=[self.instance_id])
                logger.info("stop_ec2 -> True (instance now stopped)")
                return True
            except WaiterError as e:
                logger.error("stop_ec2 -> False (WaiterError: %s)", e)
                return False
        logger.info("stop_ec2 -> True (already in state: %s)", status)
        return True
    
    # Ip changes every time the ec2 instance is launched 
    # this function will check whether the instance is running and then return the ip of the running ec2 instance 
    # NOTE: After TCPShield setup, players connect via mc.mandeezy.com (not this IP).
    # This is now mostly informational - kept for diagnostics or future use.
    def get_ip(self):
        logger.debug("get_ip called")
        if self.check_ec2_status() == "running":
            response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            public_ip = instance.get("PublicIpAddress", None)
            logger.info("get_ip -> %s", public_ip)
            return public_ip
        logger.warning("get_ip -> None (EC2 not running)")

    # Returns the PRIVATE IP of the MC server EC2.
    # Used for ALL internal bot-to-server communication (status pings, RCON).
    # Traffic stays inside the VPC so it bypasses TCPShield's public-facing security
    # group rules. Required because port 25565/25575 on the public IP is now restricted
    # to TCPShield IPs and the bot's security group respectively.
    def get_private_ip(self):
        logger.debug("get_private_ip called")
        if self.check_ec2_status() == "running":
            response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            private_ip = instance.get("PrivateIpAddress", None)
            logger.info("get_private_ip -> %s", private_ip)
            return private_ip
        logger.warning("get_private_ip -> None (EC2 not running)")
        return None
    
    # use the mcserver python library to ping the server
    # if the server gets pinged return true, if it fails return false 
    # Uses PRIVATE IP - traffic stays in the VPC
    def check_server(self):
        logger.debug("check_server called")
        if self.check_ec2_status() == "running":
            ip = self.get_private_ip()
            if ip is None:
                logger.warning("check_server -> False (private IP is None)")
                return False
            # obtain the server varaible as server using the ec2 instacne ip and mcserver
            server = JavaServer.lookup(ip)
            try:
                latency = server.status().latency
                logger.info("check_server -> True (latency=%.1fms)", latency)
                return True 
            except Exception as e:
                logger.warning("check_server -> False (ping failed: %s)", e)
                return False
        else:
            logger.info("check_server -> False (EC2 not running)")
            return False
        
    # use this function in the discord bot to start the server
    # starts the server by sending the start command via ssm
    # need to cd into the server folder and launch the server, 
    # include screen -dmS to keep the server open, without screen the server will crash after one hour. 
    def start_minecraft_server(self):
        logger.info("start_minecraft_server called")
        try:
            logger.info("Sending SSM start command to instance")
            self.ssm.send_command(
                InstanceIds=[self.instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    'commands': [
                        'cd /opt/minecraft/server && screen -dmS minecraft java -Xmx12288M -Xms12288M -jar server.jar nogui'
                    ]
                }
            )
            # checks the server 60 times in a 5 minute window (modded servers take longer to start)
            attempts = 0
            while attempts < 60:
                if self.check_server():
                    logger.info("start_minecraft_server -> True (server responding after %d attempts)", attempts + 1)
                    return True
                time.sleep(5)
                attempts += 1 
            logger.error("start_minecraft_server -> False (server never responded after 60 attempts)")
            return False  
        except Exception as e:
            logger.error("start_minecraft_server -> False (exception: %s)", e)
            return False
    
    # get player count of the server if its running, 
    # function returns the player count, the bot will use this to determine if the server should keep running or be turned off  
    # return -1 if server is off OR unreachable.
    # Uses PRIVATE IP - traffic stays in the VPC
    def get_player_count(self):
        logger.debug("get_player_count called")
        if self.check_server():
            ip = self.get_private_ip()
            server = JavaServer.lookup(ip)
            player_count = server.status().players.online
            logger.info("get_player_count -> %d", player_count)
            return player_count
        logger.warning("get_player_count -> -1 (server not reachable)")
        return -1
    

    
    def _send_rcon(self, command_parts):
        """Send a single RCON command to the MC server using its private IP.
        Returns the server's response string, or None if the command failed."""
        ip = self.get_private_ip()
        if ip is None:
            logger.warning("RCON skipped (private IP is None)")
            return None
        try:
            with Client(ip, self.port, passwd=self.RCON_PASSWORD) as client:
                response = client.run(*command_parts)
                logger.info("RCON sent: %s -> %s", command_parts, response)
                return response
        except Exception:
            logger.exception("RCON command failed: %s", command_parts)
            return None

    # Use RCON to remotely send the /stop command to the Minecraft server.
    # This stops the server without stopping the EC2 instance.
    # Used in the /restart-server Discord command.
    # Uses PRIVATE IP - RCON port is now only accessible from inside the VPC.
    def stop_minecraft(self):
        logger.info("stop_minecraft called")
        response = self._send_rcon(("stop",))
        if response is None:
            logger.error("stop_minecraft failed - RCON command did not execute")
            return False

        attempts = 0
        while attempts < 15:
            if not self.check_server():
                logger.info("stop_minecraft confirmed server stopped after %d attempts", attempts + 1)
                return True
            time.sleep(5)
            attempts += 1 
        logger.warning("stop_minecraft timed out waiting for server to stop")
        return False
        

    # Use RCON to send a random fact to the Minecraft server chat.
    # Called every 30 minutes by the auto_stop task when players are online.
    # Uses PRIVATE IP - RCON port is now only accessible from inside the VPC.
    def random_message(self):
        logger.debug("random_message called")
        fact = get_fact(False)
        self._send_rcon(("say", fact))