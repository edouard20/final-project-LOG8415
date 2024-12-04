from time import sleep
import boto3
import logging

ec2_client = boto3.client('ec2')
elbv2_client = boto3.client('elbv2')
cloudwatch_client = boto3.client('cloudwatch')

def get_instance_ids():
    response = ec2_client.describe_instances()
    instance_ids = []
    
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            instance_ids.append(instance_id)
    
    logging.info(f"Found EC2 Instances: {instance_ids}")
    return instance_ids

def terminate_instances(instance_ids):
    logging.info(f"Terminating instances: {instance_ids}")
    try:
        ec2_client.terminate_instances(InstanceIds=instance_ids)
    except Exception as e:
        logging.error(f"Error: {e}")
        
def get_security_group_id():
    response = ec2_client.describe_security_groups( Filters=[
                {
                    'Name': 'group-name',
                    'Values': ["lab3-8415"]
                }
            ]
        )
    security_group_ids = [sg['GroupId'] for sg in response['SecurityGroups']]
    logging.info(f"Found Security Groups: {security_group_ids}")
    return security_group_ids

def delete_security_group():
    security_group_id = get_security_group_id()[0]
    logging.info(f"Deleting Security Group: {security_group_id}")
    ec2_client.delete_security_group(GroupId=security_group_id)

if __name__ == '__main__':
    key_pair_name = "test-key-pair"
    instance_ids = get_instance_ids()
    terminate_instances()
    print("Waiting 2 minutes for instances to terminate...")

    try:
        ec2_client = boto3.client('ec2')
        eips = ec2_client.describe_addresses()
        for eip in eips['Addresses']:
            print(f"Releasing Elastic IP: {eip['PublicIp']}")
            ec2_client.release_address(AllocationId=eip['AllocationId'])
    except Exception as e:
        print(f"Error: {e}")
    print("Cleanup completed.")