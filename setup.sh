#!/bin/bash

# Update and upgrade the system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python3 and pip
sudo apt-get install python3 python3-pip -y

# Install discord.py library 
pip3 install discord.py

# Install additional Python libraries 
pip3 install boto3
pip3 install mcstatus
pip3 install mcrcon
pip3 install randfacts

# Install AWS CLI
sudo apt-get install awscli -y

# alert user that setup is complete 
echo "Setup complete. All necessary libraries installed."
