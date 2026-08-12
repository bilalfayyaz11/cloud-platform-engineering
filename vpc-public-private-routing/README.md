# VPC Public-Private Network Routing with LocalStack

## What This Does

This implementation builds a custom AWS-style VPC network topology entirely through the AWS CLI against LocalStack.

It provisions a `10.0.0.0/16` VPC, separates the network into public and private `/24` subnets, attaches an internet gateway, creates a dedicated public route table, and configures a default route so only the public subnet receives an internet gateway path.

The environment reproduces the core networking architecture used in AWS while remaining completely local and isolated from production cloud infrastructure.

## Architecture

    Internet
       |
       |
    +-------------------+
    | Internet Gateway  |
    +---------+---------+
              |
              |
        0.0.0.0/0
              |
    +---------+--------------------------------+
    |                                          |
    |              VPC 10.0.0.0/16             |
    |                                          |
    |   +-----------------------+              |
    |   | Public Subnet         |              |
    |   | 10.0.1.0/24           |              |
    |   +-----------+-----------+              |
    |               |                          |
    |               v                          |
    |   +-----------------------+              |
    |   | Public Route Table    |              |
    |   |                       |              |
    |   | 10.0.0.0/16 -> local  |              |
    |   | 0.0.0.0/0 -> IGW      |              |
    |   +-----------------------+              |
    |                                          |
    |   +-----------------------+              |
    |   | Private Subnet        |              |
    |   | 10.0.2.0/24           |              |
    |   +-----------+-----------+              |
    |               |                          |
    |               v                          |
    |   +-----------------------+              |
    |   | Main VPC Route Table  |              |
    |   |                       |              |
    |   | 10.0.0.0/16 -> local  |              |
    |   | No explicit IGW route |              |
    |   +-----------------------+              |
    |                                          |
    +------------------------------------------+

## Prerequisites

- Ubuntu or another Linux environment capable of running Docker
- Docker Engine
- AWS CLI v2
- curl
- Internet connectivity for pulling the LocalStack container image
- Local TCP port `4566` available
- Permission for the current Linux user to communicate with Docker

No real AWS account or production AWS credentials are required because all AWS API calls are redirected to LocalStack.

## Setup & Installation

Verify the required tools:

    docker --version
    aws --version
    curl --version

If Docker is installed but the current user cannot access the Docker daemon:

    sudo usermod -aG docker "$USER"
    newgrp docker

Start LocalStack:

    docker run -d \
      --name localstack \
      -p 127.0.0.1:4566:4566 \
      -e SERVICES=ec2 \
      localstack/localstack:4.14.0

Verify the container:

    docker ps --filter name=localstack

Verify LocalStack health:

    curl -s http://127.0.0.1:4566/_localstack/health

Configure dummy AWS CLI credentials:

    aws configure set aws_access_key_id test
    aws configure set aws_secret_access_key test
    aws configure set region us-east-1
    aws configure set output json

Create a convenient shell alias:

    alias awslocal="aws --endpoint-url=http://127.0.0.1:4566"

Verify EC2 API connectivity:

    awslocal ec2 describe-vpcs

## How to Reproduce

### Create the VPC

Create a VPC using the `10.0.0.0/16` address space and automatically capture its resource ID:

    VPC_ID=$(awslocal ec2 create-vpc \
      --cidr-block 10.0.0.0/16 \
      --query 'Vpc.VpcId' \
      --output text)

    export VPC_ID

    echo "VPC_ID=$VPC_ID"

Tag the VPC:

    awslocal ec2 create-tags \
      --resources "$VPC_ID" \
      --tags Key=Name,Value=CustomVPC

### Create the Public Subnet

Create the public subnet:

    PUBLIC_SUBNET_ID=$(awslocal ec2 create-subnet \
      --vpc-id "$VPC_ID" \
      --cidr-block 10.0.1.0/24 \
      --query 'Subnet.SubnetId' \
      --output text)

    export PUBLIC_SUBNET_ID

Tag it:

    awslocal ec2 create-tags \
      --resources "$PUBLIC_SUBNET_ID" \
      --tags Key=Name,Value=PublicSubnet

### Create the Private Subnet

Create the private subnet:

    PRIVATE_SUBNET_ID=$(awslocal ec2 create-subnet \
      --vpc-id "$VPC_ID" \
      --cidr-block 10.0.2.0/24 \
      --query 'Subnet.SubnetId' \
      --output text)

    export PRIVATE_SUBNET_ID

Tag it:

    awslocal ec2 create-tags \
      --resources "$PRIVATE_SUBNET_ID" \
      --tags Key=Name,Value=PrivateSubnet

### Create and Attach the Internet Gateway

Create an internet gateway:

    IGW_ID=$(awslocal ec2 create-internet-gateway \
      --query 'InternetGateway.InternetGatewayId' \
      --output text)

    export IGW_ID

Attach the gateway to the VPC:

    awslocal ec2 attach-internet-gateway \
      --vpc-id "$VPC_ID" \
      --internet-gateway-id "$IGW_ID"

### Create the Public Route Table

Create a dedicated route table:

    RT_ID=$(awslocal ec2 create-route-table \
      --vpc-id "$VPC_ID" \
      --query 'RouteTable.RouteTableId' \
      --output text)

    export RT_ID

Tag it:

    awslocal ec2 create-tags \
      --resources "$RT_ID" \
      --tags Key=Name,Value=PublicRouteTable

Add the default route:

    awslocal ec2 create-route \
      --route-table-id "$RT_ID" \
      --destination-cidr-block 0.0.0.0/0 \
      --gateway-id "$IGW_ID"

### Associate the Public Subnet

Associate the public subnet with the public route table:

    ASSOCIATION_ID=$(awslocal ec2 associate-route-table \
      --route-table-id "$RT_ID" \
      --subnet-id "$PUBLIC_SUBNET_ID" \
      --query 'AssociationId' \
      --output text)

    export ASSOCIATION_ID

The private subnet remains associated with the VPC's main route table and therefore does not receive the explicit `0.0.0.0/0` route through the internet gateway.

### Verify the VPC

    awslocal ec2 describe-vpcs \
      --vpc-ids "$VPC_ID"

Expected CIDR:

    10.0.0.0/16

### Verify the Subnets

    awslocal ec2 describe-subnets \
      --filters Name=vpc-id,Values="$VPC_ID"

Expected subnet ranges:

    PublicSubnet  -> 10.0.1.0/24
    PrivateSubnet -> 10.0.2.0/24

### Verify the Internet Gateway

    awslocal ec2 describe-internet-gateways \
      --internet-gateway-ids "$IGW_ID"

The gateway attachment should reference the created VPC.

### Verify the Public Route Table

    awslocal ec2 describe-route-tables \
      --route-table-ids "$RT_ID"

The route table should contain:

    10.0.0.0/16 -> local
    0.0.0.0/0   -> Internet Gateway

It should also contain an explicit association with the public subnet.

## Network Design

The final architecture separates workloads into two network tiers.

The public subnet:

    CIDR: 10.0.1.0/24

    Routing:
    10.0.0.0/16 -> local
    0.0.0.0/0   -> Internet Gateway

The private subnet:

    CIDR: 10.0.2.0/24

    Routing:
    10.0.0.0/16 -> local

    No explicit internet gateway route

This separation creates the routing foundation used by multi-tier AWS architectures where internet-facing components and internal workloads require different connectivity models.

## Tools Used

- Linux
- Docker
- LocalStack
- AWS CLI v2
- Amazon EC2 API
- Amazon VPC networking concepts
- Bash
- CIDR addressing
- AWS resource tagging
- AWS CLI JMESPath queries

## Key Skills Demonstrated

- Designing custom VPC address spaces
- Applying CIDR subnetting for network segmentation
- Building public and private subnet architecture
- Creating and attaching internet gateways
- Configuring custom route tables
- Creating default internet routes
- Managing subnet-to-route-table associations
- Automating AWS resource ID extraction
- Validating infrastructure through AWS CLI describe operations
- Managing infrastructure through command-line interfaces
- Running AWS-compatible networking environments locally with LocalStack
- Troubleshooting Docker permissions and cloud-emulation dependencies

## Real-World Use Case

This architecture represents the networking foundation commonly used for production multi-tier applications.

Internet-facing services such as application load balancers, reverse proxies, bastion hosts, and public web endpoints can be placed in public subnets with routes to an internet gateway.

Sensitive workloads such as databases, internal APIs, application workers, data-processing systems, model-serving infrastructure, and backend services can remain in private network segments without direct internet gateway routes.

Production environments commonly extend this architecture with multiple Availability Zones, NAT gateways, security groups, network ACLs, VPC endpoints, centralized logging, DNS, load balancers, and Infrastructure as Code.

## Key Networking Concepts

A VPC defines the private address space available to cloud resources.

Subnets divide that address space into smaller network segments:

    VPC:
    10.0.0.0/16

    Public:
    10.0.1.0/24

    Private:
    10.0.2.0/24

The internet gateway provides a routing target for traffic leaving the VPC.

The route table determines which network destinations can be reached from resources associated with that table.

The route:

    0.0.0.0/0 -> Internet Gateway

represents the default IPv4 route for traffic whose destination is outside the VPC.

The private subnet intentionally does not receive this route.

## Important Production Consideration

A subnet is not automatically fully internet-accessible simply because its route table contains an internet gateway route.

For an EC2 instance to communicate directly with the public internet, additional requirements normally include:

- A public IPv4 address or Elastic IP
- Security group rules permitting the required traffic
- Network ACL rules permitting the required traffic
- Correct DNS and operating system networking configuration

The topology implemented here focuses specifically on VPC routing architecture.

## Lessons Learned

- CIDR planning determines how efficiently and safely a VPC can be divided into network tiers.
- Public and private subnets can share the same VPC while following different routing policies.
- Internet gateways must be attached to a VPC before they can be used as routing targets.
- Route-table associations determine which routing rules apply to a subnet.
- A `0.0.0.0/0` route represents the default destination for IPv4 traffic outside known local routes.
- AWS CLI queries can automatically extract resource identifiers and remove error-prone manual copy-and-paste steps.
- Infrastructure verification should confirm relationships between resources, not merely confirm that individual resources exist.
- Containerized cloud emulation provides a fast way to test AWS API workflows without interacting with production accounts.

## Troubleshooting Log

### Docker Permission Failure

Docker was installed and the daemon was active, but the Linux user initially did not have access to the Docker socket.

The issue was resolved with:

    sudo usermod -aG docker "$USER"
    newgrp docker

Docker access was then verified using:

    docker info

### LocalStack Python CLI Avoided

The supplied environment workflow relied on installing the LocalStack Python CLI and `awscli-local`.

Neither dependency was necessary.

LocalStack was started directly through Docker, while the installed AWS CLI v2 was redirected to LocalStack using:

    alias awslocal="aws --endpoint-url=http://127.0.0.1:4566"

This reduced unnecessary dependencies and kept the runtime simpler.

### Mutable LocalStack Image Avoided

Using:

    localstack/localstack

without a version tag can cause behavior to change when new releases are published.

The environment was pinned to:

    localstack/localstack:4.14.0

to improve reproducibility.

### Manual AWS Resource ID Handling Removed

Manually copying identifiers such as:

    VpcId
    SubnetId
    InternetGatewayId
    RouteTableId

creates unnecessary opportunities for malformed-ID errors.

Instead, resource identifiers were captured automatically:

    --query 'Vpc.VpcId' --output text

and stored in shell variables.

This made the provisioning workflow faster, safer, and easier to reproduce.

## Final Result

The resulting topology contains:

    VPC
    10.0.0.0/16

    ├── PublicSubnet
    │   └── 10.0.1.0/24
    │       └── PublicRouteTable
    │           ├── 10.0.0.0/16 -> local
    │           └── 0.0.0.0/0 -> InternetGateway
    │
    └── PrivateSubnet
        └── 10.0.2.0/24
            └── Main VPC Route Table
                └── No explicit InternetGateway route

This provides a reproducible demonstration of core AWS VPC segmentation and routing behavior using AWS CLI-driven infrastructure operations.
