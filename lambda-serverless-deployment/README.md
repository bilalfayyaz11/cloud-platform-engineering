# Local AWS Lambda Deployment and Update Workflow

## What This Does

This implementation builds a complete local AWS Lambda development workflow using Docker, LocalStack, AWS CLI, Python, and IAM.

It provisions a local serverless runtime, creates a realistic Lambda execution role, packages a Python handler into a deployment ZIP, deploys the function, invokes it synchronously with JSON input, updates the function code, redeploys it, and verifies that the behavior and deployment hash changed successfully.

The workflow mirrors the core lifecycle used when developing event-driven workloads on AWS while allowing the entire implementation to run locally without interacting with a production AWS account.

## Architecture

    +------------------------------------------------------+
    |                    Linux Host                        |
    |                                                      |
    |  +----------------------+                            |
    |  | Python Source        |                            |
    |  |                      |                            |
    |  | handler.py           |                            |
    |  +----------+-----------+                            |
    |             |                                        |
    |             | zip                                    |
    |             v                                        |
    |  +----------------------+                            |
    |  | function.zip         |                            |
    |  +----------+-----------+                            |
    |             |                                        |
    |             | AWS CLI                                |
    |             v                                        |
    |  +------------------------------------------------+  |
    |  |              LocalStack Container              |  |
    |  |                                                |  |
    |  |  +----------------+    +--------------------+   |  |
    |  |  | IAM Service    |    | Lambda Service     |   |  |
    |  |  |                |    |                    |   |  |
    |  |  | lambda-role    |    | greeting-fn        |   |  |
    |  |  +----------------+    +---------+----------+   |  |
    |  |                                  |              |  |
    |  +----------------------------------|--------------+  |
    |                                     |                 |
    |                        Docker socket |                 |
    |                                     v                 |
    |  +------------------------------------------------+  |
    |  |           Lambda Runtime Container             |  |
    |  |                                                |  |
    |  |           Python 3.12 Runtime                  |  |
    |  |           handler.lambda_handler               |  |
    |  +------------------------------------------------+  |
    |                                                      |
    +------------------------------------------------------+

                         Invocation Flow

    JSON Payload
         |
         v
    AWS CLI
         |
         v
    LocalStack Lambda API
         |
         v
    Python Handler
         |
         v
    JSON Response
         |
         v
    response-v1.json / response-v2.json

## Prerequisites

The following components are required:

- Ubuntu or another Linux environment capable of running Docker
- Docker Engine
- Docker Compose plugin
- AWS CLI v2
- Python 3
- zip
- unzip
- curl
- diff
- Internet connectivity for pulling container images
- Local TCP port `4566` available
- Access to `/var/run/docker.sock`

No real AWS credentials are required because all AWS API requests are redirected to LocalStack.

## Setup & Installation

Verify the required tooling:

    docker --version
    docker compose version
    python3 --version
    aws --version
    zip -v
    unzip -v
    curl --version

Verify Docker is active:

    systemctl is-active docker

If Docker is installed but the current user cannot communicate with the Docker daemon:

    sudo usermod -aG docker "$USER"
    newgrp docker

Verify access:

    docker info

## Local Serverless Environment

Create the working directory:

    mkdir -p ~/lambda-runtime
    cd ~/lambda-runtime

Create the LocalStack Compose configuration:

    cat > docker-compose.yml << 'COMPOSE'
    services:
      localstack:
        image: localstack/localstack:4.14.0
        container_name: localstack
        ports:
          - "127.0.0.1:4566:4566"
        environment:
          - SERVICES=lambda,iam
          - DEBUG=1
          - DOCKER_HOST=unix:///var/run/docker.sock
        volumes:
          - "/var/run/docker.sock:/var/run/docker.sock"
          - "./volume:/var/lib/localstack"
    COMPOSE

Start LocalStack:

    docker compose up -d

Verify the container:

    docker ps --filter name=localstack

Verify LocalStack health:

    curl -s http://127.0.0.1:4566/_localstack/health

Configure dummy AWS credentials:

    aws configure set aws_access_key_id test
    aws configure set aws_secret_access_key test
    aws configure set region us-east-1
    aws configure set output json

## AWS CLI Local Endpoint Wrapper

Create a persistent AWS CLI wrapper instead of relying on an additional Python package:

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
    awslocal lambda list-functions
    awslocal iam list-roles

## Lambda Handler

Create the initial function:

    cat > handler.py << 'PYTHON'
    import json


    def lambda_handler(event: dict, context) -> dict:
        """
        AWS Lambda entrypoint.

        Args:
            event: Invocation payload containing an optional 'name' key.
            context: Lambda runtime metadata.

        Returns:
            API-style response containing a status code and JSON body.
        """
        name = event.get("name", "World")

        message = f"Hello, {name}!"

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": message
            })
        }
    PYTHON

Validate Python syntax:

    python3 -m py_compile handler.py

## Deployment Package

Create the ZIP package:

    rm -f function.zip
    zip function.zip handler.py

Verify archive contents:

    unzip -l function.zip

The archive must contain:

    handler.py

directly at the ZIP root.

## IAM Execution Role

Create the Lambda trust policy:

    cat > trust-policy.json << 'JSON'
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }
    JSON

Validate the policy:

    python3 -m json.tool trust-policy.json

Create the IAM role:

    awslocal iam create-role \
      --role-name lambda-role \
      --assume-role-policy-document file://trust-policy.json

Capture the role ARN automatically:

    ROLE_ARN=$(awslocal iam get-role \
      --role-name lambda-role \
      --query 'Role.Arn' \
      --output text)

    export ROLE_ARN

    echo "ROLE_ARN=$ROLE_ARN"

## Create the Lambda Function

Deploy the function:

    awslocal lambda create-function \
      --function-name greeting-fn \
      --runtime python3.12 \
      --role "$ROLE_ARN" \
      --handler handler.lambda_handler \
      --zip-file fileb://function.zip

Verify:

    awslocal lambda get-function \
      --function-name greeting-fn

Capture the initial deployment hash:

    CODE_SHA_V1=$(awslocal lambda get-function \
      --function-name greeting-fn \
      --query 'Configuration.CodeSha256' \
      --output text)

    export CODE_SHA_V1

    echo "CODE_SHA_V1=$CODE_SHA_V1"

## Invoke Version 1

Create an invocation payload:

    cat > payload-v1.json << 'JSON'
    {
      "name": "Bilal"
    }
    JSON

Invoke synchronously:

    awslocal lambda invoke \
      --function-name greeting-fn \
      --payload fileb://payload-v1.json \
      response-v1.json

Inspect the response:

    cat response-v1.json

Expected behavior:

    {
      "statusCode": 200,
      "body": "{\"message\": \"Hello, Bilal!\"}"
    }

## Update the Function

Replace the original handler with updated behavior:

    cat > handler.py << 'PYTHON'
    import json
    from datetime import datetime, timezone


    def lambda_handler(event: dict, context) -> dict:
        name = event.get("name", "World")

        timestamp = datetime.now(timezone.utc).isoformat()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Welcome, {name}! Your Lambda function was updated successfully.",
                "timestamp": timestamp,
                "version": 2
            })
        }
    PYTHON

Validate the updated source:

    python3 -m py_compile handler.py

Rebuild the ZIP:

    rm -f function.zip
    zip function.zip handler.py

Verify:

    unzip -l function.zip

Redeploy the code:

    awslocal lambda update-function-code \
      --function-name greeting-fn \
      --zip-file fileb://function.zip

Capture the updated code hash:

    CODE_SHA_V2=$(awslocal lambda get-function \
      --function-name greeting-fn \
      --query 'Configuration.CodeSha256' \
      --output text)

    export CODE_SHA_V2

Compare:

    echo "Version 1: $CODE_SHA_V1"
    echo "Version 2: $CODE_SHA_V2"

The hashes should differ, proving that the deployed Lambda package changed.

## Invoke Version 2

Invoke the updated function:

    awslocal lambda invoke \
      --function-name greeting-fn \
      --payload fileb://payload-v1.json \
      response-v2.json

Inspect:

    cat response-v2.json

The response should now contain:

- Updated greeting text
- UTC timestamp
- `version` value of `2`

## Compare Function Behavior

Compare raw responses:

    diff -u response-v1.json response-v2.json || true

Inspect both responses semantically:

    python3 - << 'PYTHON'
    import json

    for filename in ["response-v1.json", "response-v2.json"]:
        with open(filename) as f:
            response = json.load(f)

        print(f"\n{filename}")
        print(json.dumps({
            "statusCode": response["statusCode"],
            "body": json.loads(response["body"])
        }, indent=2))
    PYTHON

## Verification

Verify deployed functions:

    awslocal lambda list-functions \
      --query 'Functions[].{Name:FunctionName,Runtime:Runtime,Handler:Handler,LastModified:LastModified,CodeSha256:CodeSha256}' \
      --output table

Verify function configuration:

    awslocal lambda get-function \
      --function-name greeting-fn

Verify hashes:

    echo "V1=$CODE_SHA_V1"
    echo "V2=$CODE_SHA_V2"

Inspect LocalStack runtime logs:

    docker logs --tail 100 localstack

Successful completion proves:

- `greeting-fn` exists
- Runtime is Python 3.12
- Handler is `handler.lambda_handler`
- IAM execution-role structure is valid
- ZIP deployment succeeds
- Synchronous invocation succeeds
- Updated code produces different behavior
- Deployment hash changes after redeployment
- Docker-backed Lambda execution completes without unhandled runtime exceptions

## Tools Used

- Linux
- Docker
- Docker Compose
- LocalStack
- AWS CLI v2
- AWS Lambda API
- AWS IAM API
- Python 3.12
- Bash
- JSON
- ZIP deployment packaging
- Docker socket integration
- JMESPath queries
- diff

## Key Skills Demonstrated

- Designing AWS Lambda-compatible Python handlers
- Understanding Lambda event and context execution contracts
- Creating reproducible Lambda ZIP deployment packages
- Managing IAM execution-role trust relationships
- Deploying Lambda functions through AWS CLI
- Performing synchronous serverless invocations
- Managing Lambda code updates and redeployments
- Validating deployments through `CodeSha256`
- Comparing runtime behavior between releases
- Debugging LocalStack and Lambda execution through container logs
- Integrating LocalStack with the Docker socket
- Building persistent local AWS CLI tooling
- Automating AWS resource metadata extraction
- Validating JSON and Python before deployment

## Real-World Use Case

This workflow mirrors the development cycle used for event-driven serverless workloads.

Lambda functions are commonly used for API backends, event processing, automation, data transformation, scheduled operations, file processing, infrastructure automation, notifications, security response workflows, and lightweight AI inference or orchestration components.

Engineers often develop and test function behavior locally before deploying into AWS environments. A local Lambda emulator enables rapid iteration while reducing unnecessary cloud usage during development.

## Lambda Execution Contract

AWS Lambda loads a configured handler using:

    module.function

For this implementation:

    handler.lambda_handler

means:

    handler.py
       |
       +-- lambda_handler(event, context)

The `event` object represents the invocation payload.

The `context` object exposes runtime metadata supplied by Lambda.

The handler returns an API-style structure:

    {
      "statusCode": 200,
      "body": "JSON encoded response"
    }

## Docker-Based Lambda Execution

LocalStack requires access to the Docker daemon to execute Lambda runtime containers.

The Docker socket is mounted with:

    /var/run/docker.sock:/var/run/docker.sock

and LocalStack uses:

    DOCKER_HOST=unix:///var/run/docker.sock

This allows the LocalStack container to communicate with the host Docker daemon and launch Lambda runtime containers when functions are invoked.

## Deployment Integrity

Each Lambda package receives a SHA-256 code hash.

The initial deployment hash was captured using:

    awslocal lambda get-function \
      --function-name greeting-fn \
      --query 'Configuration.CodeSha256' \
      --output text

After modifying and redeploying the function, the same value was retrieved again.

A different `CodeSha256` proves that a new code package was successfully deployed.

## Lessons Learned

- Lambda deployment requires more than valid Python code; handler naming, archive structure, runtime selection, IAM role metadata, and deployment packaging must all align.
- A Python handler can compile correctly while the deployment still fails if `handler.py` is not located at the ZIP archive root.
- The deployment archive must be rebuilt after source changes before `update-function-code` is executed.
- Docker socket access is fundamental to LocalStack Lambda execution.
- Synchronous invocation provides a fast feedback loop for validating serverless behavior.
- Capturing deployment hashes provides a deterministic way to verify that new code reached the runtime.
- Comparing response artifacts makes behavioral changes between releases easy to validate.
- Local cloud emulation enables serverless development without interacting with production infrastructure.

## Troubleshooting Log

### Docker Permission Failure

Docker was installed and the daemon was active, but the Linux user initially lacked permission to communicate with the Docker daemon.

Resolved with:

    sudo usermod -aG docker "$USER"
    newgrp docker

Docker access was then verified using:

    docker info

### LocalStack Python CLI Avoided

Installing `awscli-local` was unnecessary.

The existing AWS CLI v2 was redirected to LocalStack using a lightweight executable wrapper stored in:

    ~/bin/awslocal

This reduced dependencies and survived shell reconnections more reliably than a temporary alias.

### Legacy Lambda Executor Configuration Avoided

Older LocalStack configurations referenced values such as:

    LAMBDA_EXECUTOR=docker
    LAMBDA_EXECUTOR=docker-reuse

The implementation instead relies on the current Docker-based Lambda runtime model with Docker socket access.

### Mutable Container Tag Avoided

Using an unversioned LocalStack image can introduce behavior changes when new releases are published.

The environment was pinned to:

    localstack/localstack:4.14.0

to improve reproducibility.

### Missing Deployment ZIP

Python syntax validation succeeded using:

    python3 -m py_compile handler.py

but this does not create a Lambda deployment package.

The missing archive was resolved by explicitly running:

    zip function.zip handler.py

and validating the archive with:

    unzip -l function.zip

### ZIP Structure Validation

Lambda expects the configured handler module to be importable from the deployment archive root.

The archive was therefore verified to contain:

    handler.py

directly at the top level.

### Code Update Verification

After modifying `handler.py`, the deployment ZIP was recreated before calling:

    awslocal lambda update-function-code

The old and new `CodeSha256` values were then compared to confirm that the updated package was deployed successfully.

## Files Produced

The implementation creates the following artifacts:

    lambda-runtime/
    |
    +-- docker-compose.yml
    +-- handler.py
    +-- trust-policy.json
    +-- function.zip
    +-- payload-v1.json
    +-- response-v1.json
    +-- response-v2.json
    +-- README.md

## Final Result

The final environment demonstrates the complete serverless deployment lifecycle:

    Author Python Handler
            |
            v
    Validate Syntax
            |
            v
    Package ZIP
            |
            v
    Create IAM Role
            |
            v
    Deploy Lambda
            |
            v
    Invoke Version 1
            |
            v
    Modify Source Code
            |
            v
    Repackage ZIP
            |
            v
    Update Lambda Code
            |
            v
    Verify New Code Hash
            |
            v
    Invoke Version 2
            |
            v
    Compare Runtime Behavior

This provides a reproducible local implementation of AWS Lambda development, deployment, invocation, update, and runtime validation using standard AWS-compatible tooling.
