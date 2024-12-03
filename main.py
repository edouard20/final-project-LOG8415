import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import os
import time
import logging
from user_data.user_data import USER_DATA
from user_data.proxy_user_data import PROXY_USER_DATA
from user_data.gatekeeper_user_data import GATEKEEPER_USER_DATA
from user_data.trusted_host_user_data import TRUSTED_HOST_USER_DATA
from cleanup import get_instance_ids, terminate_instances
def verify_valid_credentials():
    try:
        sts_client = boto3.client('sts')
        sts_client.get_caller_identity()
        logging.info("Valid credentials")
    except NoCredentialsError as e:
        logging.info("No credentials found")
    except ClientError as e:
        logging.error(f"Error: {e}")

def create_ec2_instances(instance_type, count, name, security_group_id, subnet_id, isPublic, user_data):
    try:
        instance = ec2_client.create_instances(
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
        logging.info(f"Creating {count} {name} instances")
    except ClientError as e:
        logging.error(f"Error: {e}")
    
    return instance[0].id

def create_vpc():
    ec2 = boto3.client('ec2')
    vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
    return vpc['Vpc']['VpcId']

def create_subnets(ec2, vpc_id):
    public_subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock='10.0.1.0/24')
    private_subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock='10.0.2.0/24')
    logging.info(f"Creating public subnet: {public_subnet['Subnet']['SubnetId']}")
    logging.info(f"Creating private subnet: {private_subnet['Subnet']['SubnetId']}")
    return public_subnet['Subnet']['SubnetId'], private_subnet['Subnet']['SubnetId']

def create_internet_gateway(ec2, vpc_id):
    internet_gateway = ec2.create_internet_gateway()
    igw_id = internet_gateway['InternetGateway']['InternetGatewayId']
    logging.info(f"Creating Internet Gateway: {igw_id}")
    ec2.attach_internet_gateway(VpcId=vpc_id, InternetGatewayId=igw_id)
    return igw_id

def create_nat_gateway(ec2, public_subnet_id):
    allocation = ec2.allocate_address(Domain='vpc')

    nat_gateway = ec2.create_nat_gateway(
        SubnetId=public_subnet_id,
        AllocationId=allocation['AllocationId']
    )
    nat_gateway_id = nat_gateway['NatGateway']['NatGatewayId']
    logging.info(f"Waiting for NAT Gateway: {nat_gateway_id} to be created")
    waiter = ec2.get_waiter('nat_gateway_available')
    try:
        waiter.wait(
            NatGatewayIds=[nat_gateway_id],
            WaiterConfig={
                'Delay': 15,
                'MaxAttempts': 20
            }
        )
        logging.info(f"NAT Gateway {nat_gateway_id} is now available.")
    except Exception as e:
        logging.error(f"Error waiting for NAT Gateway to become available: {e}")
        raise
    return nat_gateway_id, allocation['AllocationId']

def create_route_tables(ec2, vpc_id, igw_id, public_subnet_id, private_subnet_id, nat_gateway_id):
    public_route_table = ec2.create_route_table(VpcId=vpc_id)
    public_rt_id = public_route_table['RouteTable']['RouteTableId']
    ec2.create_route(
        RouteTableId=public_rt_id,
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=igw_id
    )
    ec2.associate_route_table(SubnetId=public_subnet_id, RouteTableId=public_rt_id)
    logging.info(f"Created Public Route Table: {public_rt_id}")

    private_route_table = ec2.create_route_table(VpcId=vpc_id)
    private_rt_id = private_route_table['RouteTable']['RouteTableId']
    ec2.create_route(
        RouteTableId=private_rt_id,
        DestinationCidrBlock='0.0.0.0/0',
        NatGatewayId=nat_gateway_id
    )
    ec2.associate_route_table(SubnetId=private_subnet_id, RouteTableId=private_rt_id)
    logging.info(f"Created Private Route Table: {private_rt_id}")

    return public_rt_id, private_rt_id

def create_security_groups(ec2, vpc_id):
    public_sg = ec2.create_security_group(
        GroupName='public-TP3',
        Description='Security group for public instances',
        VpcId=vpc_id
    )
    private_sg = ec2.create_security_group(
        GroupName='private-TP3',
        Description='Security group for private instances',
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
    logging.info(f"Created Public SG: {public_sg['GroupId']}")
    logging.info(f"Created Private SG: {private_sg['GroupId']}")
    return public_sg['GroupId'], private_sg['GroupId']


def get_SQL_cluster_ips(ec2_client, role):
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
        logging.info("Creating a key-pair to connect to the instances")
        with open('test-key-pair.pem', 'w') as file:
            file.write(key_pair.key_material)
        os.chmod('test-key-pair.pem', 0o444)
    except ClientError as e:
        logging.error(f"Error: {e}")

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

def wait_for_instance(instance_id):
    logging.info(f"Waiting for instance {instance_id} to boot up")
    while True:
        response = ec2.describe_instance_status(InstanceIds=[instance_id])
        
        if response['InstanceStatuses']:
            status = response['InstanceStatuses'][0]
            instance_state = status['InstanceState']['Name']
            system_status = status['SystemStatus']['Status']
            instance_status = status['InstanceStatus']['Status']
            
            logging.info(f"Instance {instance_id} state: {instance_state}, "
                         f"System status: {system_status}, Instance status: {instance_status}")
            
            if instance_state == 'running' and system_status == 'ok' and instance_status == 'ok':
                logging.info(f"Instance {instance_id} is ready.")
                break
        else:
            logging.info(f"Instance {instance_id} status not yet available.")
        
        time.sleep(10)

def delete_resources(ec2, resource_ids):

    vpc_id = resource_ids.get('vpc_id')
    public_subnet_id = resource_ids.get('public_subnet_id')
    private_subnet_id = resource_ids.get('private_subnet_id')
    nat_gateway_id = resource_ids.get('nat_gateway_id')
    internet_gateway_id = resource_ids.get('internet_gateway_id')
    route_table_ids = resource_ids.get('route_table_ids', [])
    allocation_id = resource_ids.get('allocation_id')

    if nat_gateway_id:
        logging.info(f"Deleting NAT Gateway: {nat_gateway_id}")
        ec2.delete_nat_gateway(NatGatewayId=nat_gateway_id)
        waiter = ec2.get_waiter('nat_gateway_deleted')
        waiter.wait(NatGatewayIds=[nat_gateway_id])
        logging.info(f"NAT Gateway {nat_gateway_id} deleted.")

    if allocation_id:
        logging.info(f"Releasing Elastic IP: {allocation_id}")
        ec2.release_address(AllocationId=allocation_id)
        logging.info(f"Elastic IP {allocation_id} released.")

    if internet_gateway_id and vpc_id:
        logging.info(f"Detaching and deleting Internet Gateway: {internet_gateway_id}")
        ec2.detach_internet_gateway(InternetGatewayId=internet_gateway_id, VpcId=vpc_id)
        ec2.delete_internet_gateway(InternetGatewayId=internet_gateway_id)
        logging.info(f"Internet Gateway {internet_gateway_id} deleted.")

    for route_table_id in route_table_ids:
        logging.info(f"Deleting route table: {route_table_id}")
        try:
            response = ec2.describe_route_tables(RouteTableIds=[route_table_id])
            for association in response['RouteTables'][0]['Associations']:
                if not association['Main']:  # Skip disassociating the main route table
                    association_id = association['RouteTableAssociationId']
                    logging.info(f"Disassociating route table: {association_id}")
                    try:
                        ec2.disassociate_route_table(AssociationId=association_id)
                        logging.info(f"Successfully disassociated: {association_id}")
                    except ClientError as e:
                        logging.error(f"Error disassociating route table: {e}")
            
            # Delete the route table after disassociations
            ec2.delete_route_table(RouteTableId=route_table_id)
            logging.info(f"Route table {route_table_id} deleted successfully.")
        except ClientError as e:
            logging.error(f"Error deleting route table {route_table_id}: {e}")

    if public_subnet_id:
        logging.info(f"Deleting public subnet: {public_subnet_id}")
        ec2.delete_subnet(SubnetId=public_subnet_id)
        logging.info(f"Public subnet {public_subnet_id} deleted.")
    time.sleep(90)
    if private_subnet_id:
        logging.info(f"Deleting private subnet: {private_subnet_id}")
        ec2.delete_subnet(SubnetId=private_subnet_id)
        logging.info(f"Private subnet {private_subnet_id} deleted.")
    time.sleep(60)
    logging.info("Deleting security groups...")
    try:
        security_groups = ec2.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['SecurityGroups']
        for sg in security_groups:
            if sg['GroupName'] != 'default':  # Skip default security group
                logging.info(f"Deleting security group {sg['GroupId']}")
                ec2.delete_security_group(GroupId=sg['GroupId'])
                logging.info(f"Security group {sg['GroupId']} deleted.")
    except ClientError as e:
        logging.error(f"Error deleting security groups: {e}")

    time.sleep(30)
    if vpc_id:
        logging.info(f"Deleting VPC: {vpc_id}")
        ec2.delete_vpc(VpcId=vpc_id)
        logging.info(f"VPC {vpc_id} deleted.")

    logging.info("All resources have been successfully deleted.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
ec2_client = boto3.resource('ec2')
ec2 = boto3.client('ec2')

verify_valid_credentials()
create_login_key_pair(ec2_client)
vpc_id = create_vpc()
public_subnet_id, private_subnet_id = create_subnets(ec2, vpc_id)
internet_gateway_id = create_internet_gateway(ec2, vpc_id)
nat_gateway_id, allocation_id = create_nat_gateway(ec2, public_subnet_id)
public_rt_id, private_rt_id = create_route_tables(ec2, vpc_id, internet_gateway_id, public_subnet_id, private_subnet_id, nat_gateway_id)
public_security_group_id, private_security_group_id = create_security_groups(ec2, vpc_id)
time.sleep(15)
worker_instances = create_ec2_instances('t2.micro', 2, 'Worker', private_security_group_id, private_subnet_id, False, USER_DATA)
manager_instance_id = create_ec2_instances('t2.micro', 1, 'Manager', private_security_group_id, private_subnet_id, False, USER_DATA)
time.sleep(30)
wait_for_instance(manager_instance_id)
manager_ip = get_SQL_cluster_ips("Manager")
worker_ips = get_SQL_cluster_ips("Worker")

PROXY_USER_DATA = PROXY_USER_DATA.replace("manager_ip", manager_ip[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip1", worker_ips[0])
PROXY_USER_DATA = PROXY_USER_DATA.replace("worker_ip2", worker_ips[1])
proxy_instance = create_ec2_instances('t2.large', 1, 'Proxy', private_security_group_id, private_subnet_id, False, PROXY_USER_DATA)
trusted_host_instance_id = create_ec2_instances('t2.large', 1, 'Trusted_Host', private_security_group_id, private_subnet_id, False, TRUSTED_HOST_USER_DATA)
time.sleep(15)
wait_for_instance(trusted_host_instance_id)

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

GATEKEEPER_USER_DATA = GATEKEEPER_USER_DATA.replace("TRUSTED_HOST_URL", ip_addresses[0])
gatekeeper_instance = create_ec2_instances('t2.large', 1, 'Gatekeeper',  public_security_group_id, public_subnet_id, True, USER_DATA)

time.sleep(400)
instance_ids = get_instance_ids()
terminate_instances(instance_ids)
time.sleep(60)
delete_resources(ec2, {
    'vpc_id': vpc_id,
    'public_subnet_id': public_subnet_id,
    'private_subnet_id': private_subnet_id,
    'nat_gateway_id': nat_gateway_id,
    'internet_gateway_id': internet_gateway_id,
    'route_table_ids': [public_rt_id, private_rt_id],
    'allocation_id': allocation_id
})