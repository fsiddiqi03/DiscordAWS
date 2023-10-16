import boto3
import time

class EC2Manager:
    def __init__(self, instance_id="i-0c1ded99c0ff7c3b8", region="us-east-2"):
        self.instance_id = instance_id
        self.ec2 = boto3.client("ec2", region_name=region)

    def check_ec2_status(self):
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        # will return either stopped, running, pending, or stopping
        return state
    
    def start_ec2(self):        
        self.ec2.start_instances(InstanceIds=[self.instance_id])
        status = self.check_ec2_status
        attempts = 20
        delay = 15
        while status == "pending":
            for i in range(attempts):
                status = self.check_ec2_status
                if status == "running":
                    return True
                time.sleep(delay)
            return False
        
    def stop_ec2(self):
        # stops ec2 instance 
        self.ec2.stop_instances(InstanceIds=[self.instance_id])
        status = self.check_ec2_status
        attempts = 20
        delay = 15
        if status == "stopping":
            for i in range(attempts):
                status = self.check_ec2_status
                if status == "stopped":
                    return True
                time.sleep(delay)

    #def start_server(self):
        # script to start the minecraft server 
        # should call the start ec2 method
        # when the start_ec2 instance returns running, run the script command to launch the server. 
    

    # def find_ip 
        # simple command to return to the ip of the ec2 instance 
    

    # def auto_turn_off
        # check the minecraft server to see if any players are online every 30 mins, if there is no one turn off the ec2 instance. 



ec2_manager = EC2Manager()

ec2_manager.start_ec2()









