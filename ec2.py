import logging
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import WaiterError

from config import instance_id, BACKUP_BUCKET

logger = logging.getLogger("ec2")

SERVER_DIR = "/opt/minecraft/server"
BACKUP_PREFIX = "backups/"
DOWNLOAD_URL_EXPIRY = 3600  # seconds


class EC2Manager:
    """Pure AWS-side operations for the Minecraft server's EC2 instance."""

    def __init__(self, region: str = "us-east-2"):
        self.instance_id = instance_id
        self.ec2 = boto3.client("ec2", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)
        # Regional virtual-host URLs, so presigned links don't hit a signature-breaking redirect
        self.s3 = boto3.client(
            "s3", region_name=region, config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
        )
        logger.info("EC2Manager initialized (region=%s, instance=%s)", region, self.instance_id)

    def check_status(self) -> str:
        """Return the EC2 instance state (e.g. 'running', 'stopped')."""
        logger.debug("check_status called")
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
        logger.info("check_status -> %s", state)
        return state

    def start(self) -> bool:
        """Start the EC2 instance and wait until it's running."""
        logger.info("start called")
        status = self.check_status()
        if status != "stopped":
            logger.info("start -> True (already in state: %s)", status)
            return True
        try:
            logger.info("EC2 is stopped, sending start_instances request")
            self.ec2.start_instances(InstanceIds=[self.instance_id])
            waiter = self.ec2.get_waiter("instance_running")
            logger.info("Waiting for instance_running...")
            waiter.wait(InstanceIds=[self.instance_id])
            logger.info("start -> True (instance now running)")
            return True
        except WaiterError as e:
            logger.error("start -> False (WaiterError: %s)", e)
            return False

    def stop(self) -> tuple[bool, bool]:
        """Back up the world, then stop the EC2 instance and wait until it's fully stopped.

        Returns (stopped, backup_ok). A failed backup never blocks the shutdown.
        """
        logger.info("stop called")
        status = self.check_status()
        if status != "running":
            logger.info("stop -> True (already in state: %s)", status)
            return True, True
        backup_ok = self.backup_world()
        try:
            logger.info("EC2 is running, sending stop_instances request")
            self.ec2.stop_instances(InstanceIds=[self.instance_id])
            waiter = self.ec2.get_waiter("instance_stopped")
            logger.info("Waiting for instance_stopped...")
            waiter.wait(InstanceIds=[self.instance_id])
            logger.info("stop -> True (instance now stopped)")
            return True, backup_ok
        except WaiterError as e:
            logger.error("stop -> False (WaiterError: %s)", e)
            return False, backup_ok

    def backup_world(self) -> bool:
        """Stop Minecraft (so the world is flushed to disk) and stream a tarball of it to S3."""
        logger.info("backup_world called")
        # bash for pipefail, so a tar failure isn't masked by a successful upload
        script = (
            f"cd {SERVER_DIR} && systemctl stop minecraft && "
            f"tar czf - world | aws s3 cp - s3://{BACKUP_BUCKET}/{BACKUP_PREFIX}world-$(date +%F_%H-%M).tar.gz"
        )
        ok = self.run_ssm_command([f"bash -c 'set -eo pipefail; {script}'"])
        logger.info("backup_world -> %s", ok)
        return ok

    def latest_backup_url(self) -> tuple[str, datetime] | None:
        """Return (presigned download URL, backup time) for the newest world backup, or None if there are none."""
        logger.info("latest_backup_url called")
        paginator = self.s3.get_paginator("list_objects_v2")
        latest = None
        for page in paginator.paginate(Bucket=BACKUP_BUCKET, Prefix=BACKUP_PREFIX):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".tar.gz") and (latest is None or obj["LastModified"] > latest["LastModified"]):
                    latest = obj
        if latest is None:
            logger.warning("latest_backup_url -> None (no backups found)")
            return None
        url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BACKUP_BUCKET, "Key": latest["Key"]},
            ExpiresIn=DOWNLOAD_URL_EXPIRY,
        )
        logger.info("latest_backup_url -> %s", latest["Key"])
        return url, latest["LastModified"]

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

    def run_ssm_command(self, commands: list[str], timeout: int = 300) -> bool:
        """Send a shell command via SSM and block until it finishes. Returns True if it succeeded."""
        logger.info("run_ssm_command called")
        try:
            response = self.ssm.send_command(
                InstanceIds=[self.instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": commands, "executionTimeout": [str(timeout)]},
            )
            command_id = response["Command"]["CommandId"]
            waiter = self.ssm.get_waiter("command_executed")
            waiter.wait(
                CommandId=command_id,
                InstanceId=self.instance_id,
                WaiterConfig={"Delay": 2, "MaxAttempts": timeout // 2},
            )
            return True
        except WaiterError as e:
            stderr = (e.last_response or {}).get("StandardErrorContent", "")
            logger.error("run_ssm_command -> False (WaiterError: %s, stderr: %s)", e, stderr)
            return False
        except Exception as e:
            logger.error("run_ssm_command -> False (exception: %s)", e)
            return False
