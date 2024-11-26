USER_DATA = """#!/bin/bash
MYSQL_ROOT_PASSWORD="myPassword"

sudo debconf-set-selections <<< "mysql-server mysql-server/root_password password $MYSQL_ROOT_PASSWORD"
sudo debconf-set-selections <<< "mysql-server mysql-server/root_password_again password $MYSQL_ROOT_PASSWORD"

sudo apt update -y
sudo apt-get install -y mysql-server
sudo mysql_secure_installation

"""