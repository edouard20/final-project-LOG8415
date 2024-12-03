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

def create_vpc():
    ec2 = boto3.client('ec2')
    vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
    return vpc['Vpc']['VpcId']

def create_subnets(vpc_id):
    ec2 = boto3.client('ec2')
    public_subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock='10.0.1.0/24')
    private_subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock='10.0.2.0/24')
    return public_subnet['Subnet']['SubnetId'], private_subnet['Subnet']['SubnetId']

def create_internet_gateway(vpc_id):
    ec2 = boto3.client('ec2')
    internet_gateway = ec2.create_internet_gateway()
    igw_id = internet_gateway['InternetGateway']['InternetGatewayId']
    ec2.attach_internet_gateway(VpcId=vpc_id, InternetGatewayId=igw_id)
    return igw_id

def create_nat_gateway(public_subnet_id):
    ec2 = boto3.client('ec2')
    allocation = ec2.allocate_address(Domain='vpc')

    nat_gateway = ec2.create_nat_gateway(
        SubnetId=public_subnet_id,
        AllocationId=allocation['AllocationId']
    )
    return nat_gateway['NatGateway']['NatGatewayId'], allocation['AllocationId']

def create_route_tables(vpc_id, igw_id, public_subnet_id, private_subnet_id, nat_gateway_id):
    public_route_table = ec2.create_route_table(VpcId=vpc_id)
    public_rt_id = public_route_table['RouteTable']['RouteTableId']
    ec2.create_route(
        RouteTableId=public_rt_id,
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=igw_id
    )
    ec2.associate_route_table(SubnetId=public_subnet_id, RouteTableId=public_rt_id)
    print(f"Created Public Route Table: {public_rt_id}")

    private_route_table = ec2.create_route_table(VpcId=vpc_id)
    private_rt_id = private_route_table['RouteTableId']
    ec2.create_route(
        RouteTableId=private_rt_id,
        DestinationCidrBlock='0.0.0.0/0',
        NatGatewayId=nat_gateway_id
    )
    ec2.associate_route_table(SubnetId=private_subnet_id, RouteTableId=private_rt_id)
    print(f"Created Private Route Table: {private_rt_id}")

    return public_rt_id, private_rt_id

def create_security_groups(vpc_id):
    public_sg = ec2.create_security_group(
        GroupName='public-TP3',
        VpcId=vpc_id
    )
    private_sg = ec2.create_security_group(
        GroupName='private-TP3',
        VpcId=vpc_id
    )
    
    ec2.authorize_security_group_ingress(
        GroupId=public_sg['GroupId'],
        IpPermissions=[
            {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        ]
    )

    ec2.authorize_security_group_ingress(
        GroupId=private_sg['GroupId'],
        IpPermissions=[
            {'IpProtocol': '-1', 'UserIdGroupPairs': [{'GroupId': public_sg['GroupId']}]},
            {'IpProtocol': '-1', 'UserIdGroupPairs': [{'GroupId': private_sg['GroupId']}]},
        ]
    )
    print(f"Created Public SG: {public_sg['GroupId']}")
    print(f"Created Private SG: {private_sg['GroupId']}")
    return public_sg['GroupId'], private_sg['GroupId']


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

def delete_resources(resource_ids):
    ec2 = boto3.client('ec2')

    vpc_id = resource_ids.get('vpc_id')
    public_subnet_id = resource_ids.get('public_subnet_id')
    private_subnet_id = resource_ids.get('private_subnet_id')
    nat_gateway_id = resource_ids.get('nat_gateway_id')
    internet_gateway_id = resource_ids.get('internet_gateway_id')
    route_table_ids = resource_ids.get('route_table_ids', [])
    allocation_id = resource_ids.get('allocation_id')

    if nat_gateway_id:
        print(f"Deleting NAT Gateway: {nat_gateway_id}")
        ec2.delete_nat_gateway(NatGatewayId=nat_gateway_id)
        waiter = ec2.get_waiter('nat_gateway_deleted')
        waiter.wait(NatGatewayIds=[nat_gateway_id])
        print(f"NAT Gateway {nat_gateway_id} deleted.")

    if allocation_id:
        print(f"Releasing Elastic IP: {allocation_id}")
        ec2.release_address(AllocationId=allocation_id)
        print(f"Elastic IP {allocation_id} released.")

    if internet_gateway_id and vpc_id:
        print(f"Detaching and deleting Internet Gateway: {internet_gateway_id}")
        ec2.detach_internet_gateway(InternetGatewayId=internet_gateway_id, VpcId=vpc_id)
        ec2.delete_internet_gateway(InternetGatewayId=internet_gateway_id)
        print(f"Internet Gateway {internet_gateway_id} deleted.")

    for route_table_id in route_table_ids:
        print(f"Deleting route table: {route_table_id}")
        ec2.delete_route_table(RouteTableId=route_table_id)
        print(f"Route table {route_table_id} deleted.")

    if public_subnet_id:
        print(f"Deleting public subnet: {public_subnet_id}")
        ec2.delete_subnet(SubnetId=public_subnet_id)
        print(f"Public subnet {public_subnet_id} deleted.")

    if private_subnet_id:
        print(f"Deleting private subnet: {private_subnet_id}")
        ec2.delete_subnet(SubnetId=private_subnet_id)
        print(f"Private subnet {private_subnet_id} deleted.")

    if vpc_id:
        print(f"Deleting VPC: {vpc_id}")
        ec2.delete_vpc(VpcId=vpc_id)
        print(f"VPC {vpc_id} deleted.")

    print("All resources have been successfully deleted.")

ec2_client = boto3.resource('ec2')
ec2 = boto3.client('ec2')

verify_valid_credentials()
create_login_key_pair(ec2_client)
vpc_id = create_vpc()
public_subnet_id, private_subnet_id = create_subnets(vpc_id)
internet_gateway_id = create_internet_gateway(vpc_id)
nat_gateway_id, allocation_id = create_nat_gateway(public_subnet_id)
public_rt_id, private_rt_id = create_route_tables(vpc_id, internet_gateway_id, public_subnet_id, private_subnet_id, nat_gateway_id)
public_security_group, private_security_group = create_security_groups(vpc_id)
time.sleep(15)
worker_instances = create_ec2_instances('t2.micro', 2, 'Worker', private_security_group[0], private_security_group[1], False, USER_DATA)
manager_instance = create_ec2_instances('t2.micro', 1, 'Manager', private_security_group[0], private_security_group[1], False, USER_DATA)
time.sleep(15)
manager_ip = get_SQL_cluster_ips("Manager")
worker_ips = get_SQL_cluster_ips("Worker")

PROXY_USER_DATA = PROXY_USER_DATA.replace("manager_ip", manager_ip[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip1", worker_ips[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip2", worker_ips[1])
proxy_instance = create_ec2_instances('t2.large', 1, 'Proxy', private_security_group[0], private_security_group[1], False, PROXY_USER_DATA)
trusted_host_instance = create_ec2_instances('t2.large', 1, 'Trusted_Host', private_security_group[0], private_security_group[1], False, USER_DATA)
time.sleep(15)

response = ec2.describe_instances(
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

time.sleep(600)
delete_resources({
    'vpc_id': vpc_id,
    'public_subnet_id': public_subnet_id,
    'private_subnet_id': private_subnet_id,
    'nat_gateway_id': nat_gateway_id,
    'internet_gateway_id': internet_gateway_id,
    'route_table_ids': [public_rt_id, private_rt_id],
    'allocation_id': allocation_id
})