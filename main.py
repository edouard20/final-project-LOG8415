import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import os
import time
from user_data.user_data import USER_DATA
from user_data.proxy_user_data import PROXY_USER_DATA

def verify_valid_credentials():
    try:
        sts_client = boto3.client('sts')
        sts_client.get_caller_identity()
        print("Valid credentials")
    except NoCredentialsError as e:
        print("No credentials found")
    except ClientError as e:
        print(f"Error: {e}")

def create_ec2_instances(instance_type, count, name, security_group_id, user_data):
    try:
        ec2_client.create_instances(
            ImageId='ami-0e86e20dae9224db8', MaxCount=count, InstanceType = instance_type, MinCount=1, KeyName='test-key-pair',TagSpecifications=[  {'ResourceType': 'instance','Tags': [  {'Key': 'Name',
                    'Value': name}]}], SecurityGroupIds=[security_group_id],
                                     UserData=user_data)
        print(f"Creating {count} {name} instances")
    except ClientError as e:
        print(f"Error: {e}")

def create_security_group(ec2):
    ec2 = boto3.client('ec2')
    response_vpcs = ec2.describe_vpcs()
    vpc_id = response_vpcs.get('Vpcs', [{}])[0].get('VpcId', '')

    response = ec2.create_security_group(
        GroupName="lab3-8415",
        Description="Security Group with access on port 8080 and 8081",
        VpcId=vpc_id
        )

    security_group_id = response['GroupId']

    ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
                'FromPort': 8080,
                'ToPort': 8081,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': '-1',
                'FromPort': 0,
                'ToPort': 65535,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        ])
    return security_group_id

def get_SQL_cluster_ips(role):
    ec2_client = boto3.client("ec2")
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Role", "Values": [role]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )
    ip_addresses = [
        instance["PrivateIpAddress"]
        for reservation in response["Reservations"]
        for instance in reservation["Instances"]
    ]
    return ip_addresses

def create_login_key_pair(ec2_client):
    try:
        key_pair = ec2_client.create_key_pair(KeyName='test-key-pair', KeyType='rsa')
        print("Creating a key-pair to connect to the instances")
        with open('test-key-pair.pem', 'w') as file:
            file.write(key_pair.key_material)
        os.chmod('test-key-pair.pem', 0o444)
    except ClientError as e:
        print(f"Error: {e}")

def get_SQL_cluster_ips(role):
    ec2_client = boto3.client("ec2")
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [role]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )
    ip_addresses = [
        instance["PrivateIpAddress"]
        for reservation in response["Reservations"]
        for instance in reservation["Instances"]
    ]

    return ip_addresses    

ec2_client = boto3.resource('ec2')
ec2 = boto3.client('ec2')

verify_valid_credentials()
create_login_key_pair(ec2_client)
security_group_id = create_security_group(ec2_client)
worker_instances = create_ec2_instances('t2.micro', 2, 'Worker', security_group_id, USER_DATA)
manager_instance = create_ec2_instances('t2.micro', 1, 'Manager', security_group_id, USER_DATA)
time.sleep(5)
manager_ip = get_SQL_cluster_ips("Manager")
worker_ips = get_SQL_cluster_ips("Worker")

PROXY_USER_DATA = PROXY_USER_DATA.replace("manager_ip", manager_ip[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip1", worker_ips[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip2", worker_ips[1])
proxy_instance = create_ec2_instances('t2.large', 1, 'Proxy', security_group_id, PROXY_USER_DATA)
# gatekeeper_instance = create_ec2_instances('t2.large', 1, 'Gatekeeper', security_group_id, USER_DATA)
# trusted_host_instance = create_ec2_instances('t2.large', 1, 'Trusted_Host', security_group_id, USER_DATA)
