# EC2 Monitoring Solution

## Overview

This repository contains a solution for monitoring AWS EC2 instances. The solution includes a Python script that collects metrics, sets up CloudWatch alarms, and sends notifications via SNS. The setup is designed to scale and handle multiple servers.

## Architecture

![Architecture Diagram](https://github.com/SulakshanaBandara/ec2_monitoring/assets/129736390/3d58ec42-baf6-40f5-b38e-b2bb2de54e71)


### Configuration

- Launch three EC2 instances.
- Update the `config.json` file with the appropriate values for your environment. 
- The file includes instance IDs, thresholds for metrics, SNS topic name, and email for notifications.
- Update with the **Instance IDs** and the **email**, **YOUR_AWS_ACCOUNT_ID** and **REGION**.

### Setup Instructions

#### Prerequisites

  - Ensure you have Python 3.x installed.
  - Ensure you have AWS CLI installed and configured with appropriate permissions.
  - Install the Boto3 library for AWS interactions.
    
#### Installation

  - Clone the repository.
  - Install the required Python packages.

### Running the Script

#### Run the Python script. 

    python3 ec2_monitor.py




