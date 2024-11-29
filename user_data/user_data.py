USER_DATA = """#!/bin/bash
MYSQL_ROOT_PASSWORD="myPassword"

sudo debconf-set-selections <<< "mysql-server mysql-server/root_password password $MYSQL_ROOT_PASSWORD"
sudo debconf-set-selections <<< "mysql-server mysql-server/root_password_again password $MYSQL_ROOT_PASSWORD"

sudo apt update -y
sudo apt-get install -y mysql-server wget tar sysbench
# sudo mysql_secure_installation

sudo systemctl start mysql
sudo systemctl enable mysql

wget https://downloads.mysql.com/docs/sakila-db.tar.gz -O /tmp/sakila-db.tar.gz
tar -xvzf /tmp/sakila-db.tar.gz -C /tmp

sudo mysql -u root -p$MYSQL_ROOT_PASSWORD < /tmp/sakila-db/sakila-schema.sql
sudo mysql -u root -p$MYSQL_ROOT_PASSWORD < /tmp/sakila-db/sakila-data.sql

sudo mysql -u root -p$MYSQL_ROOT_PASSWORD -e "SHOW DATABASES;"

sudo sysbench /usr/share/sysbench/oltp_read_only.lua --mysql-db=sakila --mysql-user="root" --mysql-password=$MYSQL_ROOT_PASSWORD prepare
"""