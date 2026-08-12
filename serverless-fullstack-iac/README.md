# Serverless Full-Stack Infrastructure with CloudFormation and LocalStack

## What This Does

This implementation provisions and validates a complete multi-service serverless architecture using AWS CloudFormation against LocalStack.

The stack contains an S3 bucket configured for static website hosting, a DynamoDB table using on-demand billing, a Python Lambda function, and a least-privilege IAM execution role that allows the function to write only to the DynamoDB table managed by the same stack.

The implementation validates the full application lifecycle: declarative infrastructure provisioning, static content deployment, successful Lambda invocation, DynamoDB persistence, malformed-payload handling, IAM scope verification, and complete stack teardown with zero orphaned resources.

## Architecture

    +----------------------------------------------------------------+
    |                    CloudFormation Stack                         |
    |                                                                |
    |  +----------------------+                                      |
    |  | S3 Website Bucket    |                                      |
    |  |                      |                                      |
    |  | index.html           |                                      |
    |  | error.html           |                                      |
    |  +----------------------+                                      |
    |                                                                |
    |  +----------------------+         +--------------------------+  |
    |  | Lambda Function      |         | DynamoDB Table           |  |
    |  |                      |         |                          |  |
    |  | Python 3.12          |-------->| ServerlessApplicationData|  |
    |  | index.lambda_handler | PutItem |                          |  |
    |  +----------+-----------+         +--------------------------+  |
    |             |                                                  |
    |             v                                                  |
    |  +----------------------+                                      |
    |  | IAM Execution Role   |                                      |
    |  |                      |                                      |
    |  | dynamodb:PutItem     |                                      |
    |  | only on table ARN    |                                      |
    |  +----------------------+                                      |
    |                                                                |
    +----------------------------------------------------------------+

                          Deployment Flow

    infra.yaml
        |
        v
    CloudFormation
        |
        +--------------------+--------------------+-------------------+
        |                    |                    |                   |
        v                    v                    v                   v
       S3                 DynamoDB              Lambda              IAM
        |                                         |
        |                                         |
        |                                JSON Test Payload
        |                                         |
        |                                         v
        |                               Validate + Generate UUID
        |                                         |
        |                                         v
        |                                  DynamoDB PutItem
        |                                         |
        |                                         v
        |                                   JSON Response
        |
        v
    Static Website Content

## Prerequisites

The following components are required:

- Ubuntu or another Linux environment capable of running Docker
- Docker Engine
- Docker Compose plugin
- AWS CLI v2
- Python 3
- curl
- jq
- Internet connectivity for pulling LocalStack container images
- Local TCP port `4566` available
- Access to `/var/run/docker.sock`

No production AWS account or credentials are required because all AWS API requests are redirected to LocalStack.

## Setup & Installation

Verify the required tooling:

    docker --version
    docker compose version
    aws --version
    python3 --version
    curl --version
    jq --version

Verify Docker is active:

    systemctl is-active docker

If Docker is installed but the current user cannot access the Docker daemon:

    sudo usermod -aG docker "$USER"
    newgrp docker

Verify Docker access:

    docker info

## Start LocalStack

Create the working directory:

    mkdir -p ~/serverless-fullstack
    cd ~/serverless-fullstack

Start LocalStack with only the required services:

    docker run -d \
      --name localstack \
      -p 127.0.0.1:4566:4566 \
      -e SERVICES=cloudformation,s3,dynamodb,lambda,iam,sts \
      -e DOCKER_HOST=unix:///var/run/docker.sock \
      -v /var/run/docker.sock:/var/run/docker.sock \
      localstack/localstack:4.14.0

Verify the container:

    docker ps --filter name=localstack

Verify service health:

    curl -s http://127.0.0.1:4566/_localstack/health | jq

Configure dummy AWS credentials:

    aws configure set aws_access_key_id test
    aws configure set aws_secret_access_key test
    aws configure set region us-east-1
    aws configure set output json

## AWS CLI Local Endpoint Wrapper

Create a persistent AWS CLI wrapper:

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

Verify connectivity:

    command -v awslocal
    awslocal cloudformation list-stacks
    awslocal s3 ls
    awslocal dynamodb list-tables
    awslocal lambda list-functions
    awslocal iam list-roles

## CloudFormation Template

Create `infra.yaml`:

    cat > infra.yaml << 'YAML'
    AWSTemplateFormatVersion: "2010-09-09"

    Description: >
      Multi-service serverless architecture containing an S3 static website,
      DynamoDB persistence layer, least-privilege IAM execution role,
      and Python Lambda compute function.

    Resources:

      WebsiteBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: !Sub "serverless-site-${AWS::AccountId}-${AWS::Region}"
          WebsiteConfiguration:
            IndexDocument: index.html
            ErrorDocument: error.html

      WebsiteBucketPolicy:
        Type: AWS::S3::BucketPolicy
        Properties:
          Bucket: !Ref WebsiteBucket
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Sid: PublicReadObjects
                Effect: Allow
                Principal: "*"
                Action:
                  - s3:GetObject
                Resource: !Sub "${WebsiteBucket.Arn}/*"

      ApplicationTable:
        Type: AWS::DynamoDB::Table
        Properties:
          TableName: ServerlessApplicationData
          BillingMode: PAY_PER_REQUEST
          AttributeDefinitions:
            - AttributeName: id
              AttributeType: S
          KeySchema:
            - AttributeName: id
              KeyType: HASH

      LambdaExecutionRole:
        Type: AWS::IAM::Role
        Properties:
          RoleName: serverless-data-writer-role

          AssumeRolePolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Principal:
                  Service:
                    - lambda.amazonaws.com
                Action:
                  - sts:AssumeRole

          Policies:
            - PolicyName: WriteApplicationTable
              PolicyDocument:
                Version: "2012-10-17"
                Statement:
                  - Sid: PutApplicationItem
                    Effect: Allow
                    Action:
                      - dynamodb:PutItem
                    Resource: !GetAtt ApplicationTable.Arn

      ApplicationFunction:
        Type: AWS::Lambda::Function
        Properties:
          FunctionName: serverless-data-writer
          Runtime: python3.12
          Handler: index.lambda_handler
          Role: !GetAtt LambdaExecutionRole.Arn
          MemorySize: 128
          Timeout: 10

          Environment:
            Variables:
              TABLE_NAME: !Ref ApplicationTable

          Code:
            ZipFile: |
              import json
              import os
              import uuid
              import logging
              from datetime import datetime, timezone

              import boto3

              logger = logging.getLogger()
              logger.setLevel(logging.INFO)

              dynamodb = boto3.resource("dynamodb")
              table = dynamodb.Table(os.environ["TABLE_NAME"])


              def lambda_handler(event, context):
                  logger.info("Received event: %s", json.dumps(event))

                  if not isinstance(event, dict):
                      logger.error("Payload must be a JSON object")
                      return {
                          "statusCode": 400,
                          "body": json.dumps({
                              "error": "Payload must be a JSON object"
                          })
                      }

                  name = event.get("name")

                  if not isinstance(name, str) or not name.strip():
                      logger.error("Missing or invalid name")
                      return {
                          "statusCode": 400,
                          "body": json.dumps({
                              "error": "A non-empty 'name' field is required"
                          })
                      }

                  item_id = str(uuid.uuid4())
                  timestamp = datetime.now(timezone.utc).isoformat()

                  item = {
                      "id": item_id,
                      "name": name.strip(),
                      "timestamp": timestamp
                  }

                  table.put_item(Item=item)

                  logger.info("Stored item: %s", json.dumps(item))

                  return {
                      "statusCode": 200,
                      "body": json.dumps({
                          "message": "Item stored successfully",
                          "id": item_id,
                          "timestamp": timestamp
                      })
                  }

    Outputs:

      WebsiteBucketName:
        Description: S3 bucket containing the static website
        Value: !Ref WebsiteBucket

      ApplicationTableName:
        Description: DynamoDB application table
        Value: !Ref ApplicationTable

      ApplicationFunctionArn:
        Description: Lambda function ARN
        Value: !GetAtt ApplicationFunction.Arn

      ApplicationFunctionName:
        Description: Lambda function name
        Value: !Ref ApplicationFunction
    YAML

Validate the template:

    awslocal cloudformation validate-template \
      --template-body file://infra.yaml

## Infrastructure Design Decisions

### Required Services

The LocalStack environment enables:

    cloudformation
    s3
    dynamodb
    lambda
    iam
    sts

CloudFormation manages the infrastructure lifecycle.

S3 provides static website storage.

DynamoDB provides application persistence.

Lambda provides application compute.

IAM provides the Lambda execution role.

STS supports identity-related behavior required by IAM and Lambda execution.

### DynamoDB Billing Mode

The table uses:

    PAY_PER_REQUEST

This is appropriate for workloads with unpredictable or low-frequency traffic because there is no need to pre-allocate read and write capacity.

For a small event-driven application, this provides a simpler operational model than provisioned throughput.

### Lambda Runtime Configuration

The function uses:

    Runtime: python3.12
    MemorySize: 128
    Timeout: 10

The workload performs only lightweight JSON validation, UUID generation, timestamp generation, and one DynamoDB `PutItem`.

Higher memory or timeout values would not provide meaningful benefit for this workload.

### Lambda Packaging Strategy

The function source is embedded in CloudFormation through:

    Code:
      ZipFile: |

This makes the stack self-contained and avoids requiring an artifact bucket before CloudFormation can create the function.

For larger production workloads, the preferred approach would typically be:

    source repository
         |
         v
    CI/CD pipeline
         |
         v
    versioned Lambda ZIP
         |
         v
    artifact S3 bucket
         |
         v
    CloudFormation deployment

## Deploy the Stack

Set the stack name:

    STACK_NAME="serverless-application-stack"
    export STACK_NAME

Create the stack:

    awslocal cloudformation create-stack \
      --stack-name "$STACK_NAME" \
      --template-body file://infra.yaml \
      --capabilities CAPABILITY_NAMED_IAM

Poll until deployment completes:

    while true; do

      STATUS=$(awslocal cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null)

      echo "Stack status: $STATUS"

      case "$STATUS" in

        CREATE_COMPLETE)
          echo "Stack creation complete"
          break
          ;;

        ROLLBACK_COMPLETE|ROLLBACK_FAILED|CREATE_FAILED)
          echo "Stack creation failed"

          awslocal cloudformation describe-stack-events \
            --stack-name "$STACK_NAME" \
            --query 'StackEvents[].{Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
            --output table

          break
          ;;

      esac

      sleep 3

    done

## Capture Stack Outputs

Extract the resource identifiers directly from CloudFormation:

    BUCKET_NAME=$(awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" \
      --output text)

    TABLE_NAME=$(awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query "Stacks[0].Outputs[?OutputKey=='ApplicationTableName'].OutputValue" \
      --output text)

    FUNCTION_NAME=$(awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query "Stacks[0].Outputs[?OutputKey=='ApplicationFunctionName'].OutputValue" \
      --output text)

    FUNCTION_ARN=$(awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query "Stacks[0].Outputs[?OutputKey=='ApplicationFunctionArn'].OutputValue" \
      --output text)

    export BUCKET_NAME TABLE_NAME FUNCTION_NAME FUNCTION_ARN

Verify:

    echo "BUCKET_NAME=$BUCKET_NAME"
    echo "TABLE_NAME=$TABLE_NAME"
    echo "FUNCTION_NAME=$FUNCTION_NAME"
    echo "FUNCTION_ARN=$FUNCTION_ARN"

## Static Website Content

Create `index.html`:

    cat > index.html << 'HTML'
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Serverless Application</title>
    </head>

    <body>

      <h1>Serverless Application</h1>

      <p>
        This application demonstrates a multi-service AWS architecture
        deployed entirely through Infrastructure as Code.
      </p>

      <h2>Architecture</h2>

      <p>
        Static content is stored in Amazon S3, application logic runs
        through AWS Lambda, and structured application data is persisted
        in Amazon DynamoDB.
      </p>

      <p>
        Infrastructure is managed declaratively through AWS CloudFormation.
      </p>

    </body>
    </html>
    HTML

Create `error.html`:

    cat > error.html << 'HTML'
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Page Not Found</title>
    </head>

    <body>
      <h1>404 - Page Not Found</h1>
    </body>
    </html>
    HTML

Upload:

    awslocal s3 cp index.html "s3://$BUCKET_NAME/index.html"
    awslocal s3 cp error.html "s3://$BUCKET_NAME/error.html"

Verify:

    awslocal s3 ls "s3://$BUCKET_NAME/"

## Successful Lambda Invocation

Create a valid payload:

    cat > valid-payload.json << 'JSON'
    {
      "name": "Bilal"
    }
    JSON

Invoke:

    awslocal lambda invoke \
      --function-name "$FUNCTION_NAME" \
      --payload fileb://valid-payload.json \
      success-response.json

Inspect:

    cat success-response.json | jq

Decode the body:

    python3 - << 'PYTHON'
    import json

    with open("success-response.json") as f:
        response = json.load(f)

    print("Status:", response["statusCode"])

    body = json.loads(response["body"])

    print(json.dumps(body, indent=2))
    PYTHON

Expected behavior:

    statusCode = 200

The response contains:

- success message
- generated UUID
- UTC timestamp

## DynamoDB Persistence Validation

Scan the table:

    awslocal dynamodb scan \
      --table-name "$TABLE_NAME"

For a cleaner view:

    awslocal dynamodb scan \
      --table-name "$TABLE_NAME" \
      --query 'Items[].{ID:id.S,Name:name.S,Timestamp:timestamp.S}' \
      --output table

Expected state:

    Count = 1

The persisted item contains:

    id
    name
    timestamp

The Lambda function generates the unique ID and timestamp before calling DynamoDB.

## Failure Handling

Create an invalid payload:

    cat > invalid-payload.json << 'JSON'
    {
      "unexpected": "value"
    }
    JSON

Invoke:

    awslocal lambda invoke \
      --function-name "$FUNCTION_NAME" \
      --payload fileb://invalid-payload.json \
      failure-response.json

Inspect:

    cat failure-response.json | jq

Expected behavior:

    statusCode = 400

Expected message:

    A non-empty 'name' field is required

Verify that the invalid request did not create another record:

    awslocal dynamodb scan \
      --table-name "$TABLE_NAME" \
      --select COUNT

Expected:

    Count = 1

## Least-Privilege IAM

Inspect the execution role:

    awslocal iam get-role \
      --role-name serverless-data-writer-role

List inline policies:

    awslocal iam list-role-policies \
      --role-name serverless-data-writer-role

Inspect the DynamoDB policy:

    awslocal iam get-role-policy \
      --role-name serverless-data-writer-role \
      --policy-name WriteApplicationTable

The function receives only:

    dynamodb:PutItem

against only:

    ApplicationTable ARN

The function does not receive:

    dynamodb:*
    Resource: "*"

It also does not receive unrelated permissions such as:

    dynamodb:DeleteTable
    dynamodb:Scan
    dynamodb:GetItem
    dynamodb:UpdateItem

This follows least-privilege design.

## Infrastructure Verification

Verify CloudFormation:

    awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME"

Verify stack resources:

    awslocal cloudformation list-stack-resources \
      --stack-name "$STACK_NAME" \
      --query 'StackResourceSummaries[].{LogicalID:LogicalResourceId,Type:ResourceType,Status:ResourceStatus}' \
      --output table

Verify S3:

    awslocal s3 ls "s3://$BUCKET_NAME/"

Verify DynamoDB:

    awslocal dynamodb scan \
      --table-name "$TABLE_NAME"

Verify Lambda:

    awslocal lambda list-functions \
      --query 'Functions[].{Name:FunctionName,Runtime:Runtime,Handler:Handler}' \
      --output table

Inspect LocalStack logs:

    docker logs --tail 150 localstack

## Teardown

The website objects were uploaded after stack creation.

A non-empty S3 bucket cannot normally be deleted cleanly by CloudFormation, so application objects must be removed before stack teardown.

Empty the bucket:

    awslocal s3 rm "s3://$BUCKET_NAME/" --recursive

Verify:

    awslocal s3 ls "s3://$BUCKET_NAME/"

Delete the stack:

    awslocal cloudformation delete-stack \
      --stack-name "$STACK_NAME"

Poll for deletion:

    while true; do

      STATUS=$(awslocal cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null)

      RC=$?

      if [ "$RC" -ne 0 ]; then
        echo "Stack deletion complete"
        break
      fi

      echo "Stack status: $STATUS"

      if [[ "$STATUS" == *FAILED* ]]; then
        echo "Deletion encountered a failure"

        awslocal cloudformation describe-stack-events \
          --stack-name "$STACK_NAME"

        break
      fi

      sleep 3

    done

## Zero-Orphan Verification

Verify CloudFormation removal:

    awslocal cloudformation describe-stacks \
      --stack-name "$STACK_NAME" 2>&1 || true

Verify S3 removal:

    awslocal s3api head-bucket \
      --bucket "$BUCKET_NAME" 2>&1 || \
      echo "S3 bucket removed"

Verify DynamoDB removal:

    awslocal dynamodb describe-table \
      --table-name "$TABLE_NAME" 2>&1 || \
      echo "DynamoDB table removed"

Verify Lambda removal:

    awslocal lambda get-function \
      --function-name "$FUNCTION_NAME" 2>&1 || \
      echo "Lambda function removed"

Verify IAM role removal:

    awslocal iam get-role \
      --role-name serverless-data-writer-role 2>&1 || \
      echo "IAM execution role removed"

Final listings:

    awslocal s3 ls
    awslocal dynamodb list-tables
    awslocal lambda list-functions
    awslocal cloudformation list-stacks

## Tools Used

- Linux
- Docker
- LocalStack
- AWS CLI v2
- AWS CloudFormation
- Amazon S3
- Amazon DynamoDB
- AWS Lambda
- AWS IAM
- AWS STS
- Python 3.12
- boto3
- YAML
- JSON
- Bash
- jq
- JMESPath queries

## Key Skills Demonstrated

- Designing multi-service AWS serverless architecture
- Authoring complete CloudFormation infrastructure from scratch
- Managing S3, DynamoDB, Lambda, and IAM through one IaC template
- Implementing least-privilege IAM permissions
- Using DynamoDB on-demand billing
- Designing Lambda input and output contracts
- Implementing UUID-based resource identifiers
- Persisting structured application data
- Adding timestamps to event-driven records
- Handling malformed event payloads safely
- Validating successful and failed Lambda behavior
- Capturing CloudFormation outputs programmatically
- Inspecting AWS resource state through CLI operations
- Managing named IAM resources through CloudFormation capabilities
- Handling S3 teardown dependencies
- Verifying zero orphaned resources after stack deletion
- Running Docker-backed Lambda execution through LocalStack
- Separating infrastructure lifecycle from application content deployment
- Troubleshooting multi-service cloud environments

## Real-World Use Case

This architecture represents a simplified serverless application foundation.

A real organization could use the same pattern for:

- user-submitted forms
- event ingestion
- lightweight APIs
- serverless workflow automation
- application telemetry
- metadata capture
- AI inference request tracking
- background processing
- internal automation services

S3 can host static application assets, Lambda can process incoming application events, and DynamoDB can provide low-latency serverless persistence.

CloudFormation allows the complete environment to be recreated consistently across development, staging, and production environments.

## Application Data Flow

The application flow is:

    JSON Invocation
          |
          v
    Lambda Function
          |
          +-- Validate payload
          |
          +-- Generate UUID
          |
          +-- Generate UTC timestamp
          |
          v
    DynamoDB PutItem
          |
          v
    ServerlessApplicationData
          |
          v
    Success Response

Invalid payload flow:

    Invalid JSON Payload
          |
          v
    Lambda Validation
          |
          v
    HTTP 400-style Response
          |
          X
    No DynamoDB Write

## Security Model

The Lambda function requires only one AWS API action:

    dynamodb:PutItem

The IAM policy therefore grants only that operation.

The resource scope is limited to the ARN of the DynamoDB table created by the same CloudFormation template.

This prevents the function from writing to unrelated DynamoDB tables or performing destructive administrative operations.

## Production Considerations

Several behaviors can differ between LocalStack and a real AWS account.

### IAM Propagation

AWS IAM role creation and policy updates can experience propagation delays.

LocalStack generally makes these resources available much faster.

Production automation should account for eventual consistency.

### S3 Global Naming

Real AWS S3 bucket names are globally unique.

LocalStack provides an isolated local environment, so collision behavior does not fully reproduce global AWS constraints.

### S3 Deletion

CloudFormation cannot delete an S3 bucket containing objects unless the objects are removed first or a custom cleanup mechanism is implemented.

Production deployments often handle this through:

- lifecycle policies
- custom resources
- CI/CD cleanup steps
- deliberate retention policies

### Lambda Packaging

Inline CloudFormation Lambda code is useful for small functions.

Production applications generally package Lambda source through CI/CD and deploy versioned ZIP artifacts or container images.

### Observability

A production implementation should integrate:

- CloudWatch Logs
- metrics
- tracing
- alarms
- dead-letter queues
- structured error monitoring

## Lessons Learned

- Multi-service infrastructure should be defined declaratively rather than manually provisioned resource by resource.
- CloudFormation Outputs provide a stable interface for retrieving deployed resource identifiers.
- Least-privilege IAM should be designed around the exact API operations the application performs.
- Event validation should occur before persistence to prevent malformed data from reaching storage.
- DynamoDB `PAY_PER_REQUEST` is appropriate for low-volume or unpredictable workloads.
- Lambda memory and timeout settings should reflect actual workload behavior rather than using unnecessarily large defaults.
- Inline Lambda code keeps small infrastructure demonstrations self-contained, while artifact-based deployment scales better for production.
- Application data should be verified independently at every layer rather than trusting only the Lambda response.
- Failure paths deserve the same verification as successful requests.
- Resources created by CloudFormation should also be removed through CloudFormation whenever possible.
- S3 objects uploaded outside the stack can become teardown dependencies.
- Complete teardown verification is necessary to prevent orphaned cloud resources and unexpected cost.
- LocalStack is useful for architecture validation, but real AWS behavior around IAM propagation, naming constraints, service quotas, and deletion semantics must still be considered.

## Troubleshooting Log

### Docker Permission Failure

Docker was installed and active, but the Linux user initially lacked permission to access the Docker daemon.

Resolved with:

    sudo usermod -aG docker "$USER"
    newgrp docker

Verified using:

    docker info

### Local AWS CLI Tooling

Neither the LocalStack Python CLI nor `awscli-local` was required.

A persistent wrapper was created around the installed AWS CLI v2:

    ~/bin/awslocal

This reduced dependencies and remained available across terminal sessions.

### Mutable LocalStack Image Avoided

Using:

    localstack/localstack:latest

would make runtime behavior dependent on whichever image is currently published.

The environment was pinned to:

    localstack/localstack:4.14.0

for reproducibility.

### Docker Socket Required for Lambda

LocalStack Lambda execution requires access to the host Docker daemon.

The socket was mounted:

    /var/run/docker.sock:/var/run/docker.sock

and LocalStack was configured with:

    DOCKER_HOST=unix:///var/run/docker.sock

### Least-Privilege IAM

The Lambda function did not receive broad DynamoDB access.

Its inline IAM policy allowed:

    dynamodb:PutItem

only on:

    ApplicationTable.Arn

This prevented unnecessary administrative access.

### Invalid Event Handling

The Lambda function explicitly validates the `name` field.

Malformed payloads return:

    statusCode = 400

without writing additional records to DynamoDB.

This was confirmed by verifying the table remained at exactly one item after the failure test.

### S3 Teardown Dependency

The S3 bucket contained website files uploaded after CloudFormation deployment.

The bucket was emptied before stack deletion:

    awslocal s3 rm "s3://$BUCKET_NAME/" --recursive

This prevented non-empty bucket deletion from blocking teardown.

### Zero-Orphan Verification

After deleting the stack, each major resource type was checked independently:

    S3
    DynamoDB
    Lambda
    IAM
    CloudFormation

The absence of these resources confirmed complete teardown rather than assuming that `delete-stack` alone was sufficient evidence.

## Files Produced

The implementation produces:

    serverless-fullstack/
    |
    +-- infra.yaml
    +-- index.html
    +-- error.html
    +-- valid-payload.json
    +-- invalid-payload.json
    +-- success-response.json
    +-- failure-response.json
    +-- README.md

## Final Result

The resulting architecture contains:

    CloudFormation
         |
         +--------------------------------------+
         |                                      |
         v                                      v
    S3 Website                            Serverless Backend
                                               |
                                     +---------+---------+
                                     |                   |
                                     v                   v
                                  Lambda              DynamoDB
                                     |
                                     v
                               IAM Execution Role
                                     |
                                     v
                         dynamodb:PutItem only
                         on application table

The complete lifecycle demonstrates:

    Design
      |
      v
    IaC Authoring
      |
      v
    Template Validation
      |
      v
    Stack Deployment
      |
      v
    Static Content Deployment
      |
      v
    Lambda Invocation
      |
      v
    DynamoDB Persistence
      |
      v
    Failure Validation
      |
      v
    IAM Verification
      |
      v
    Controlled Teardown
      |
      v
    Zero-Orphan Verification

This implementation provides recruiter-visible evidence of multi-service AWS architecture, Infrastructure as Code discipline, least-privilege security design, serverless application logic, data persistence, failure handling, and production-oriented resource lifecycle management.
