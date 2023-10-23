from mcstatus import JavaServer
from aws import EC2Manager

ec2 = EC2Manager()

def check_server():
    ip = ec2.get_ip()
    server = JavaServer.lookup(ip)
    try:
        latency = server.status().latency
        return True
    except:
        return False 
    



# function that returns true if players are online 
