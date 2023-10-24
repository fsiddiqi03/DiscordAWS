import boto3
import time
from botocore.exceptions import WaiterError
from mcstatus import JavaServer



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
                waiter = self.ec2.get_waiter('instance_running')
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
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        public_ip = instance.get("PublicIpAddress", None)
        return public_ip
    


    def ssm_status(self, command_id):
        attempts = 13
        while attempts > 0:
            result = self.ssm.list_command_invocations(
                CommandId=command_id,
                InstanceId=self.instance_id,
                Details=True
            )
            status = result['CommandInvocations'][0]['Status']
            if status == "Success":
                return True
            elif status in ['Failed', 'Cancelled', 'TimedOut']:
                return False
            time.sleep(5)
            attempts -= 1
        return False
    def check_server(self):
        ip = self.get_ip()
        server = JavaServer.lookup(ip)
        try:
            latency = server.status().latency
            return True
        except:
            return False 

        
    # use this function in the discord bot to start the server
    def start_minecraft_server(self):
        # attempt to start the minecraft server by sending it a command
        # use try to catch any errors 
        try:
            response = self.ssm.send_command(
                InstanceIds=[self.instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    'commands': [
                        'cd /opt/minecraft/server && java -Xmx1024M -Xms1024M -jar server.jar nogui'
                    ]
                }
            )
            # get the command Id to check thes status of the ssm command 
            # use the ssm status method to check the status until it returns true or false
            command_id = response['Command']['CommandId']
            if self.ssm_status(command_id):
                return True
            else:
                return False
        except Exception as e:
            return False
    
    # def auto_turn_off
    # check the minecraft server to see if any players are online every 30 mins, if there is no one turn off the ec2 instance.
    def auto_check(self):
        ip = self.get_ip()
        if self.check_ec2_status == "running":
            if self.check_server(ip):
                self.stop_ec2()
                return True
            
        return False
            









#ec2_manager = EC2Manager()
#if ec2_manager.test_ssm_connection():
    #if ec2_manager.start_minecraft_server():
       # print("Minecraft server started!")
   # else:
      #  print("Failed to start Minecraft server.")
#else:
   # print("Failed to connect via SSM.")









