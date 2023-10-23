import boto3
import time
from botocore.exceptions import WaiterError


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
        

    #def start_server(self):
        # script to start the minecraft server 
        # should check if the ec2 instance is on, if not should call the start ec2 method
        # when the start_ec2 instance returns running, run the script command to launch the server. 
    
    
    def test_ssm_connection(self):
        try:
            response = self.ssm.send_command(
                InstanceIds=[self.instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    'commands': ['echo "Connection Test Successful!"']
                }
            )

            command_id = response['Command']['CommandId']
            time.sleep(5)  # Sleep for 5 seconds

            result = self.ssm.list_command_invocations(
                CommandId=command_id,
                InstanceId=self.instance_id,
                Details=True
            )

            # Check if the command succeeded
            if result['CommandInvocations'][0]['Status'] == 'Success':
                output = result['CommandInvocations'][0]['CommandPlugins'][0]['Output']
                print(output)
                return True
            else:
                print("Failed to connect via SSM.")
                return False
        except Exception as e:
            print(f"Error during SSM connection test: {e}")
            return False

    # Your other methods for starting the server and automatic turn-off...

ec2_manager = EC2Manager()

if ec2_manager.test_ssm_connection():
     print("SSM connection successful!")
     # Here you can call your method to start the Minecraft server
else:
    print("Failed to connect via SSM.")
 
    

    # def auto_turn_off
        # check the minecraft server to see if any players are online every 30 mins, if there is no one turn off the ec2 instance. 


















