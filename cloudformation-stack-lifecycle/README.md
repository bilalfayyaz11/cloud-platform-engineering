# CloudFormation S3 Infrastructure Lifecycle with LocalStack

## What This Does

This implementation demonstrates a complete Infrastructure as Code workflow using AWS CloudFormation against LocalStack.

It defines S3 infrastructure declaratively in YAML, validates the template, creates a CloudFormation stack, inspects stack resources and outputs, updates the template to introduce a second managed bucket, verifies the updated state, and tears the infrastructure down through the CloudFormation lifecycle.

The implementation mirrors the core workflow used in production AWS environments while remaining fully local and isolated from real cloud resources.

## Architecture

    +--------------------------------------------------+
    |                  Linux Host                      |
    |                                                  |
    |  +--------------------------------------------+  |
    |  |              infra.yaml                    |  |
    |  |                                            |  |
    |  |  AWS::S3::Bucket                           |  |
    |  |  PrimaryDataBucket                         |  |
    |  |                                            |  |
    |  |  AWS::S3::Bucket                           |  |
    |  |  ArchiveDataBucket                         |  |
    |  +----------------------+---------------------+  |
    |                         |                        |
    |                         | AWS CLI                |
    |                         v                        |
    |  +--------------------------------------------+  |
    |  |           LocalStack Container             |  |
    |  |                                            |  |
    |  |  +----------------------+                  |  |
    |  |  | CloudFormation API   |                  |  |
    |  |  +----------+-----------+                  |  |
    |  |             |                              |  |
    |  |             v                              |  |
    |  |  +----------------------+                  |  |
    |  |  | S3 API               |                  |  |
    |  |  +----------+-----------+                  |  |
    |  |             |                              |  |
    |  |      +------+-------+                      |  |
    |  |      |              |                      |  |
    |  |      v              v                      |  |
    |  | Primary Bucket   Archive Bucket            |  |
    |  +--------------------------------------------+  |
    |                                                  |
    +--------------------------------------------------+

                  CloudFormation Lifecycle

    Validate Template
          |
          v
    Create Stack
          |
          v
    CREATE_COMPLETE
          |
          v
    Inspect Resources
          |
          v
    Modify Template
          |
          v
    Update Stack
          |
          v
    UPDATE_COMPLETE
          |
          v
    Verify Two Buckets
          |
          v
    Delete Stack
          |
          v
    Resources Removed

## Prerequisites

The following components are required:

- Ubuntu or another Linux environment capable of running Docker
- Docker Engine
- AWS CLI v2
- curl
- jq
- Internet connectivity for pulling the LocalStack container image
- Local TCP port `4566` available
- Permission for the current Linux user to communicate with Docker

No real AWS account or production AWS credentials are required because all AWS API requests are redirected to LocalStack.

## Setup & Installation

Verify the required tooling:

    docker --version
    aws --version
    curl --version
    jq --version

Verify Docker is running:

    systemctl is-active docker

If Docker is installed but the current user cannot access the Docker daemon:

    sudo usermod -aG docker "$USER"
    newgrp docker

Verify Docker access:

    docker info

## Start LocalStack

Create the working directory:

    mkdir -p ~/cloudformation-iac
    cd ~/cloudformation-iac

Start LocalStack with only CloudFormation and S3 enabled:

    docker run -d \
      --name localstack \
      -p 127.0.0.1:4566:4566 \
      -e SERVICES=cloudformation,s3 \
      localstack/localstack:4.14.0

Verify the container:

    docker ps --filter name=localstack

Verify service health:

    curl -s http://127.0.0.1:4566/_localstack/health | jq

Configure dummy AWS CLI credentials:

    aws configure set aws_access_key_id test
    aws configure set aws_secret_access_key test
    aws configure set region us-east-1
    aws configure set output json

## AWS CLI Local Endpoint Wrapper

Create a persistent wrapper:

    mkdir -p ~/bin

    cat > ~/bin/awslocal << 'WRAPPER'
    #!/bin/bash
    ENDPOINT="http:"'//127.0.0.1:4566'
    exec aws --endpoint-url="$ENDPOINT" "$@"
    WRAPPER

    chmod +x ~/bin/awslocal

    export PATH="$HOME/bin:$PATH"

    grep -qxF 'export PATH="$HOME/bin:$PATH"' ~/.bashrc || \
      echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc

Verify:

    command -v awslocal
    awslocal cloudformation list-stacks
    awslocal s3 ls

## Initial CloudFormation Template

Create `infra.yaml`:

    cat > infra.yaml << 'YAML'
    AWSTemplateFormatVersion: "2010-09-09"

    Description: >
      Provision local S3 infrastructure through AWS CloudFormation
      using declarative Infrastructure as Code.

    Resources:

      PrimaryDataBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Sub "primary-data-${AWS::AccountId}-${AWS::Region}"

    Outputs:

      PrimaryBucketName:
        Description: Name of the primary S3 bucket
        Value: !Ref PrimaryDataBucket
    YAML

Validate the template:

    awslocal cloudformation validate-template \
      --template-body file://infra.yaml

## Create the Stack

Set the stack name:

    STACK_NAME="storage-foundation"
    export STACK_NAME

Create the stack:

    awslocal cloudformation create-stack \
      --stack-name "$STACK_NAME" \
      --template-body file://infra.yaml

Poll until the stack is complete:

    while true; do
      STATUS=$(awslocal cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null)

      echo "Stack status: $STATUS"

      case "$STATUS" in
        CREATE_COMPLETE)
          break
          ;;
        *FAILED*|ROLLBACK_COMPLETE|ROLLBACK_FAILED)
          echo "Stack creation failed"
          awslocal cloudformation describe-stack-events \
            --stack-name "$STACK_NAME"
          break
          ;;
      esac

      sleep 2
    done

Verify stack outputs:

    awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query 'Stacks[0].Outputs'

Verify the bucket:

    awslocal s3 ls

## Inspect Stack Resources

List resources managed by CloudFormation:

    awslocal cloudformation list-stack-resources \
      --stack-name "$STACK_NAME"

Inspect stack events when troubleshooting:

    awslocal cloudformation describe-stack-events \
      --stack-name "$STACK_NAME"

## Update the Infrastructure

Replace `infra.yaml` with the two-bucket configuration:

    cat > infra.yaml << 'YAML'
    AWSTemplateFormatVersion: "2010-09-09"

    Description: >
      Provision local S3 infrastructure through AWS CloudFormation
      using declarative Infrastructure as Code.

    Resources:

      PrimaryDataBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Sub "primary-data-${AWS::AccountId}-${AWS::Region}"

      ArchiveDataBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Sub "archive-data-${AWS::AccountId}-${AWS::Region}"

    Outputs:

      PrimaryBucketName:
        Description: Name of the primary S3 bucket
        Value: !Ref PrimaryDataBucket

      ArchiveBucketName:
        Description: Name of the archive S3 bucket
        Value: !Ref ArchiveDataBucket
    YAML

Validate the updated template:

    awslocal cloudformation validate-template \
      --template-body file://infra.yaml

Apply the update:

    awslocal cloudformation update-stack \
      --stack-name "$STACK_NAME" \
      --template-body file://infra.yaml

Poll until complete:

    while true; do
      STATUS=$(awslocal cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null)

      echo "Stack status: $STATUS"

      case "$STATUS" in
        UPDATE_COMPLETE)
          break
          ;;
        *FAILED*|UPDATE_ROLLBACK_COMPLETE|UPDATE_ROLLBACK_FAILED)
          echo "Stack update failed"
          awslocal cloudformation describe-stack-events \
            --stack-name "$STACK_NAME"
          break
          ;;
      esac

      sleep 2
    done

## Verify Updated Resources

List the stack resources:

    awslocal cloudformation list-stack-resources \
      --stack-name "$STACK_NAME" \
      --query 'StackResourceSummaries[].{LogicalID:LogicalResourceId,Type:ResourceType,Status:ResourceStatus,PhysicalID:PhysicalResourceId}' \
      --output table

Expected logical resources:

    PrimaryDataBucket
    ArchiveDataBucket

Verify outputs:

    awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query 'Stacks[0].Outputs'

Verify both physical S3 buckets:

    awslocal s3 ls

## Change Management Strategy

For this small local implementation, `update-stack` is sufficient because the infrastructure change is simple and low risk.

In production environments, CloudFormation Change Sets are often preferable because they allow engineers to inspect the intended resource additions, modifications, replacements, and deletions before execution.

This provides an additional safety layer for infrastructure changes.

## Stack Teardown

Delete the stack:

    awslocal cloudformation delete-stack \
      --stack-name "$STACK_NAME"

Poll until the stack disappears:

    while true; do
      STATUS=$(awslocal cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null)

      if [ $? -ne 0 ] || [ -z "$STATUS" ] || [ "$STATUS" = "None" ]; then
        echo "Stack deletion complete"
        break
      fi

      echo "Stack status: $STATUS"
      sleep 2
    done

Verify S3 cleanup:

    awslocal s3 ls

Confirm the stack no longer exists:

    awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME"

A validation error is expected after successful deletion.

## Tools Used

- Linux
- Docker
- LocalStack
- AWS CLI v2
- AWS CloudFormation
- Amazon S3
- YAML
- Bash
- jq
- CloudFormation intrinsic functions
- JMESPath queries
- AWS pseudo-parameters

## Key Skills Demonstrated

- Authoring declarative CloudFormation templates
- Using `AWSTemplateFormatVersion`
- Designing descriptive logical resource IDs
- Creating S3 resources through Infrastructure as Code
- Using `!Sub` for dynamic resource naming
- Using `!Ref` for stack outputs
- Validating CloudFormation templates before deployment
- Managing complete stack lifecycle operations
- Polling CloudFormation stack state programmatically
- Inspecting stack resources and stack events
- Updating existing infrastructure declaratively
- Verifying physical resources through service APIs
- Troubleshooting failed and rolled-back stacks
- Removing infrastructure through stack deletion
- Working with LocalStack CloudFormation limitations
- Separating desired configuration from imperative provisioning

## Infrastructure as Code Model

The implementation follows a declarative model.

Instead of issuing individual commands such as:

    create bucket A
    create bucket B

the desired state is defined in a template:

    Resources:

      PrimaryDataBucket:
        Type: AWS::S3::Bucket

      ArchiveDataBucket:
        Type: AWS::S3::Bucket

CloudFormation then determines which underlying API operations are necessary to move the current environment toward that desired state.

This model enables repeatability, reviewability, version control, and automation.

## Intrinsic Functions

The bucket names are generated with:

    !Sub "primary-data-${AWS::AccountId}-${AWS::Region}"

and:

    !Sub "archive-data-${AWS::AccountId}-${AWS::Region}"

`!Sub` substitutes CloudFormation values into strings during deployment.

The template also uses:

    !Ref PrimaryDataBucket

to return the physical resource name through the stack outputs.

## Real-World Use Case

CloudFormation is used to provision and manage repeatable AWS environments across development, staging, and production.

Typical infrastructure can include:

- VPCs
- subnets
- security groups
- IAM roles
- S3 buckets
- Lambda functions
- API Gateway resources
- databases
- load balancers
- monitoring resources
- application infrastructure

Declarative templates allow teams to review infrastructure changes through source control, reproduce environments consistently, and reduce configuration drift caused by manual console operations.

## Stack Lifecycle

The lifecycle implemented here is:

    Template Authoring
          |
          v
    Template Validation
          |
          v
    create-stack
          |
          v
    CREATE_COMPLETE
          |
          v
    Resource Inspection
          |
          v
    Template Modification
          |
          v
    update-stack
          |
          v
    UPDATE_COMPLETE
          |
          v
    Resource Verification
          |
          v
    delete-stack
          |
          v
    Infrastructure Removed

## Lessons Learned

- Infrastructure as Code separates desired configuration from the manual sequence of API calls required to create infrastructure.
- CloudFormation logical IDs provide stable template-level references while physical resource identifiers can vary between deployments.
- Template validation should occur before stack creation or update.
- Stack status must be inspected rather than assuming that a create or update command succeeded.
- `describe-stack-events` is one of the most important CloudFormation troubleshooting commands because it exposes the resource that failed first.
- Stack outputs provide a clean interface for exposing important resource identifiers.
- CloudFormation updates can modify the existing managed infrastructure without manually recreating every resource.
- Stack deletion provides centralized resource cleanup when resources remain under CloudFormation management.
- Local emulation can differ from AWS and unsupported operations should be identified rather than forced.

## Troubleshooting Log

### Docker Permission Failure

Docker was installed and active, but the Linux user initially lacked permission to access the Docker daemon.

Resolved with:

    sudo usermod -aG docker "$USER"
    newgrp docker

Docker access was confirmed using:

    docker info

### LocalStack CLI Avoided

Installing the LocalStack Python CLI and `awscli-local` was unnecessary.

LocalStack was started directly through Docker, while the installed AWS CLI v2 was redirected to the LocalStack endpoint using a persistent wrapper.

This reduced dependencies and improved reproducibility.

### Mutable Container Image Avoided

Using:

    localstack/localstack

without a version tag can introduce unexpected runtime changes.

The environment was pinned to:

    localstack/localstack:4.14.0

to provide consistent behavior.

### Stack State Unexpectedly Disappeared

During the initial lifecycle execution, the expected `storage-foundation` stack was no longer present when resource inspection was attempted.

The failure was detected using:

    awslocal cloudformation list-stack-resources \
      --stack-name storage-foundation

and:

    awslocal cloudformation describe-stacks \
      --stack-name storage-foundation

The environment was recovered by recreating the template and stack, then validating state after each lifecycle operation.

This reinforced the importance of checking CloudFormation state transitions explicitly rather than assuming that the previous operation persisted correctly.

### Drift Detection Unsupported

The attempted CloudFormation drift operation returned:

    DetectStackDrift operation ... is not currently supported by LocalStack

The unsupported validation step was removed rather than treated as an infrastructure failure.

In a real AWS environment, drift detection can be used to compare CloudFormation-managed desired state with resource configuration that may have been changed outside the stack.

### Update Behavior Requires Careful Validation

LocalStack CloudFormation update behavior can differ from AWS.

After the stack was recovered, the update workflow was validated through:

    describe-stacks
    list-stack-resources
    describe-stack-events
    s3 ls

This ensured that both logical and physical resource state matched the intended template.

## Files Produced

The implementation produces:

    cloudformation-iac/
    |
    +-- infra.yaml
    +-- README.md

The final version of `infra.yaml` contains both managed S3 resources.

## Final Result

The resulting CloudFormation template manages:

    storage-foundation
    |
    +-- PrimaryDataBucket
    |   |
    |   +-- AWS::S3::Bucket
    |
    +-- ArchiveDataBucket
        |
        +-- AWS::S3::Bucket

The workflow demonstrates:

    Declarative Template
          |
          v
    CloudFormation Stack
          |
          +----> Primary S3 Bucket
          |
          +----> Archive S3 Bucket
          |
          v
    Managed Update
          |
          v
    Managed Teardown

This provides a reproducible demonstration of CloudFormation template authoring, stack lifecycle management, infrastructure updates, verification, troubleshooting, and cleanup using standard AWS-compatible tooling.
