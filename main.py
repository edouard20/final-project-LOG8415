import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import os
import time
from user_data.user_data import USER_DATA
from user_data.proxy_user_data import PROXY_USER_DATA
from user_data.gatekeeper_user_data import GATEKEEPER_USER_DATA

def verify_valid_credentials():
    try:
        sts_client = boto3.client('sts')
        sts_client.get_caller_identity()
        print("Valid credentials")
    except NoCredentialsError as e:
        print("No credentials found")
    except ClientError as e:
        print(f"Error: {e}")

def create_ec2_instances(instance_type, count, name, security_group_id, subnet_id, isPublic, user_data):
    try:
        ec2_client.create_instances(
            ImageId='ami-0e86e20dae9224db8', MaxCount=count, InstanceType = instance_type, MinCount=1, KeyName='test-key-pair',TagSpecifications=[  {'ResourceType': 'instance','Tags': [  {'Key': 'Name',
                    'Value': name}]}], NetworkInterfaces=[
            {
                'SubnetId': subnet_id,
                'DeviceIndex': 0,
                'Groups': [security_group_id],
                'AssociatePublicIpAddress': isPublic
            }
        ],
                                     UserData=user_data)
        print(f"Creating {count} {name} instances")
    except ClientError as e:
        print(f"Error: {e}")

def create_security_groups():
    ec2 = boto3.client('ec2')
    vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
    vpc_id = vpc['Vpc']['VpcId']

    print("Created VPC with ID: ", vpc_id)

    public_subnet = ec2.create_subnet(VpcId = vpc_id, CidrBlock='10.0.1.0/24')
    public_subnet_id = public_subnet['Subnet']['SubnetId']

    print("Created public subnet with ID: ", public_subnet_id)

    private_subnet = ec2.create_subnet(VpcId = vpc_id, CidrBlock='10.0.2.0/24')
    private_subnet_id = private_subnet['Subnet']['SubnetId']

    print("Created private subnet with ID: ", private_subnet_id)

    internet_gateway = ec2.create_internet_gateway()
    igw_id = internet_gateway['InternetGateway']['InternetGatewayId']
    ec2.attach_internet_gateway(VpcId=vpc_id, InternetGatewayId=igw_id)

    print("Created internet gateway with ID: ", igw_id)

    public_route_table = ec2.create_route_table(VpcId=vpc_id)
    public_route_table_id = public_route_table['RouteTable']['RouteTableId']

    print("Created public route table with ID: ", public_route_table_id)

    ec2.create_route(
        RouteTableId=public_route_table_id,
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=igw_id
    )

    ec2.associate_route_table(SubnetId=public_subnet_id, RouteTableId=public_route_table_id)

    eip = ec2.allocate_address(Domain='vpc')
    eip_id = eip['AllocationId']

    nat_gateway = ec2.create_nat_gateway(
    SubnetId=public_subnet_id,
    AllocationId=eip_id
    )

    nat_gateway_id = nat_gateway['NatGateway']['NatGatewayId']

    waiter = ec2.get_waiter('nat_gateway_available')
    waiter.wait(NatGatewayIds=[nat_gateway_id])

    private_route_table = ec2.create_route_table(VpcId=vpc_id)
    private_route_table_id = private_route_table['RouteTable']['RouteTableId']

    print("Created private route table with ID: ", private_route_table_id)

    ec2.create_route(
    RouteTableId=private_route_table_id,
    DestinationCidrBlock='0.0.0.0/0',
    NatGatewayId=nat_gateway_id
    )

    ec2.associate_route_table(SubnetId=private_subnet_id, RouteTableId=private_route_table_id)

    public_security_group = ec2.create_security_group(
        GroupName="lab3-8415-public",
        Description="Public security group for lab3-8415",
        VpcId=vpc_id,
    )

    private_security_group = ec2.create_security_group(
        GroupName="lab3-8415-private",
        Description="Private security group for lab3-8415",
        VpcId=vpc_id,
    )

    ec2.authorize_security_group_ingress(
        GroupId=public_security_group['GroupId'],
        IpPermissions=[
            {'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        ])
    
    ec2.authorize_security_group_ingress(
        GroupId=private_security_group['GroupId'],
        IpPermissions=[
            {'IpProtocol': 'tcp',
                'FromPort': 3306,
                'ToPort': 3306,
                 'UserIdGroupPairs': [
                {
                    'GroupId': public_security_group['GroupId'],
                },
                 ],
                'IpRanges': [{'CidrIp': '10.0.1.0/24'}]},
            {'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                 'UserIdGroupPairs': [
                {
                    'GroupId': public_security_group['GroupId'],
                },
                 ],
                'IpRanges': [{'CidrIp': '10.0.1.0/24'}]},
             {'IpProtocol': 'tcp',
                'FromPort': 80,
                'ToPort': 80,
                 'UserIdGroupPairs': [
                {
                    'GroupId': public_security_group['GroupId'],
                },
                 ],
                'IpRanges': [{'CidrIp': '10.0.1.0/24'}]},
            ])
                              
    return (public_security_group['GroupId'], public_subnet_id), (private_security_group['GroupId'], private_subnet_id)

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
public_security_group, private_security_group = create_security_groups()
worker_instances = create_ec2_instances('t2.micro', 2, 'Worker', private_security_group[0], private_security_group[1], False, USER_DATA)
manager_instance = create_ec2_instances('t2.micro', 1, 'Manager', private_security_group[0], private_security_group[1], False, USER_DATA)
time.sleep(5)
manager_ip = get_SQL_cluster_ips("Manager")
worker_ips = get_SQL_cluster_ips("Worker")

PROXY_USER_DATA = PROXY_USER_DATA.replace("manager_ip", manager_ip[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip1", worker_ips[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip2", worker_ips[1])
proxy_instance = create_ec2_instances('t2.large', 1, 'Proxy', private_security_group[0], private_security_group[1], False, PROXY_USER_DATA)
trusted_host_instance = create_ec2_instances('t2.large', 1, 'Trusted_Host', private_security_group[0], private_security_group[1], False, USER_DATA)
time.sleep(5)

response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": ["Trusted_Host"]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )

ip_addresses = [
        instance["PrivateIpAddress"]
        for reservation in response["Reservations"]
        for instance in reservation["Instances"]
    ]

print(ip_addresses)
GATEKEEPER_USER_DATA = GATEKEEPER_USER_DATA.replace("TRUSTED_HOST_URL", ip_addresses[0])
gatekeeper_instance = create_ec2_instances('t2.large', 1, 'Gatekeeper',  public_security_group[0], public_security_group[1], True, USER_DATA)
