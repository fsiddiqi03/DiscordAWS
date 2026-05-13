import logging

import boto3
from botocore.exceptions import WaiterError

from config import instance_id

logger = logging.getLogger("ec2")


class EC2Manager:
    """Pure AWS-side operations for the Minecraft server's EC2 instance."""

    def __init__(self, region: str = "us-east-2"):
        self.instance_id = instance_id
        self.ec2 = boto3.client("ec2", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)
        logger.info("EC2Manager initialized (region=%s, instance=%s)", region, self.instance_id)

    def check_status(self) -> str:
        """Return the EC2 instance state (e.g. 'running', 'stopped')."""
        logger.debug("check_status called")
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
        logger.info("check_status -> %s", state)
        return state

    def start(self) -> bool:
        """Start the EC2 instance and wait until status checks pass."""
        logger.info("start called")
        status = self.check_status()
        if status != "stopped":
            logger.info("start -> True (already in state: %s)", status)
            return True
        try:
            logger.info("EC2 is stopped, sending start_instances request")
            self.ec2.start_instances(InstanceIds=[self.instance_id])
            # Instance status must be okay before the Minecraft server can be launched
            waiter = self.ec2.get_waiter("instance_status_ok")
            logger.info("Waiting for instance_status_ok...")
            waiter.wait(InstanceIds=[self.instance_id])
            logger.info("start -> True (instance now running)")
            return True
        except WaiterError as e:
            logger.error("start -> False (WaiterError: %s)", e)
            return False

    def stop(self) -> bool:
        """Stop the EC2 instance and wait until it's fully stopped."""
        logger.info("stop called")
        status = self.check_status()
        if status != "running":
            logger.info("stop -> True (already in state: %s)", status)
            return True
        try:
            logger.info("EC2 is running, sending stop_instances request")
            self.ec2.stop_instances(InstanceIds=[self.instance_id])
            waiter = self.ec2.get_waiter("instance_stopped")
            logger.info("Waiting for instance_stopped...")
            waiter.wait(InstanceIds=[self.instance_id])
            logger.info("stop -> True (instance now stopped)")
            return True
        except WaiterError as e:
            logger.error("stop -> False (WaiterError: %s)", e)
            return False

    # Used for ALL internal bot-to-server communication (status pings, RCON).
    def private_ip(self) -> str | None:
        """Return the instance's private (VPC-internal) IP, or None if not running."""
        logger.debug("private_ip called")
        if self.check_status() != "running":
            logger.warning("private_ip -> None (EC2 not running)")
            return None
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        ip = instance.get("PrivateIpAddress")
        logger.info("private_ip -> %s", ip)
        return ip

    def send_ssm_command(self, commands: list[str]) -> bool:
        """Send a shell command to the EC2 instance via SSM."""
        logger.info("send_ssm_command called")
        try:
            self.ssm.send_command(
                InstanceIds=[self.instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": commands},
            )
            return True
        except Exception as e:
            logger.error("send_ssm_command -> False (exception: %s)", e)
            return False
