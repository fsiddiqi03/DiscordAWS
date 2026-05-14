import logging
import time
from typing import Callable

from mcstatus import JavaServer
from rcon.source import Client
from randfacts import get_fact

from config import RCON_PASSWORD, port
from ec2 import EC2Manager

logger = logging.getLogger("minecraft")


class MinecraftServer:
    """Operations that talk directly to the running Minecraft server.

    Uses the EC2 instance's PRIVATE IP for all communication, so traffic
    stays inside the VPC (bypasses TCPShield's public-facing security rules).
    """

    def __init__(self, ec2: EC2Manager):
        self.ec2 = ec2
        self.rcon_password = RCON_PASSWORD
        self.rcon_port = port

    def is_running(self) -> bool:
        """Return True if the MC server responds to a status ping."""
        logger.debug("is_running called")
        if self.ec2.check_status() != "running":
            logger.info("is_running -> False (EC2 not running)")
            return False
        ip = self.ec2.private_ip()
        if ip is None:
            logger.warning("is_running -> False (private IP is None)")
            return False
        try:
            latency = JavaServer.lookup(ip).status().latency
            logger.info("is_running -> True (latency=%.1fms)", latency)
            return True
        except Exception as e:
            logger.warning("is_running -> False (ping failed: %s)", e)
            return False

    def player_count(self) -> int:
        """Return online player count, or -1 if the server is unreachable."""
        logger.debug("player_count called")
        if not self.is_running():
            logger.warning("player_count -> -1 (server not reachable)")
            return -1
        ip = self.ec2.private_ip()
        count = JavaServer.lookup(ip).status().players.online
        logger.info("player_count -> %d", count)
        return count

    def start(self) -> bool:
        """Launch the MC server via SSM, then poll until it's responding."""
        logger.info("start called")
        # Need to cd into the server folder and launch with `screen -dmS` so the
        # process stays alive after the SSM session ends.
        sent = self.ec2.send_ssm_command([
            "cd /opt/minecraft/server && screen -dmS minecraft java -Xmx12288M -Xms12288M -jar server.jar nogui"
        ])
        if not sent:
            logger.error("start -> False (SSM command failed)")
            return False

        # Modded servers can take a while; allow up to 5 minutes
        attempts = self._wait_for(self.is_running, attempts=60, interval=5)
        if attempts is None:
            logger.error("start -> False (server never responded after 60 attempts)")
            return False
        logger.info("start -> True (server responding after %d attempts)", attempts)
        return True

    def stop(self) -> bool:
        """Send /stop via RCON and wait for the server to go offline."""
        logger.info("stop called")
        response = self._send_rcon(("stop",))
        if response is None:
            logger.error("stop failed - RCON command did not execute")
            return False

        attempts = self._wait_for(lambda: not self.is_running(), attempts=15, interval=5)
        if attempts is None:
            logger.warning("stop timed out waiting for server to stop")
            return False
        logger.info("stop confirmed server stopped after %d attempts", attempts)
        return True

    def random_message(self) -> None:
        """Send a random fact to the MC server chat via RCON."""
        logger.debug("random_message called")
        fact = get_fact(False)
        self._send_rcon(("say", fact))

    def _send_rcon(self, command_parts: tuple) -> str | None:
        """Send an RCON command. Returns the response, or None on failure."""
        ip = self.ec2.private_ip()
        if ip is None:
            logger.warning("RCON skipped (private IP is None)")
            return None
        try:
            with Client(ip, self.rcon_port, passwd=self.rcon_password) as client:
                response = client.run(*command_parts)
                logger.info("RCON sent: %s -> %s", command_parts, response)
                return response
        except Exception:
            logger.exception("RCON command failed: %s", command_parts)
            return None

    @staticmethod
    def _wait_for(predicate: Callable[[], bool], attempts: int, interval: int) -> int | None:
        """Poll predicate() until it returns True. Returns the attempt count, or None on timeout."""
        for i in range(attempts):
            if predicate():
                return i + 1
            time.sleep(interval)
        return None
