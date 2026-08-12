# Cloud Platform Engineering

This repository contains hands-on cloud infrastructure implementations focused on AWS architecture, serverless systems, Infrastructure as Code, networking, and local cloud emulation.

Each implementation is designed around practical infrastructure outcomes rather than isolated commands. The emphasis is on architecture, reproducibility, lifecycle management, security, validation, and troubleshooting using AWS-compatible tooling.

## Implementations

| # | What Was Built | Key Technologies | Level |
|---|----------------|-----------------|-------|
| 1 | Public and private VPC routing architecture with custom CIDR ranges, subnet segmentation, internet gateway attachment, and route-table association | AWS VPC, EC2 API, AWS CLI, LocalStack, Docker, CIDR | Intermediate |
| 2 | Local Lambda deployment and update workflow with IAM execution role, ZIP packaging, synchronous invocation, code redeployment, and deployment hash verification | AWS Lambda, IAM, AWS CLI, LocalStack, Docker, Python | Advanced |
| 3 | CloudFormation infrastructure lifecycle automation with declarative S3 provisioning, stack creation, update, inspection, troubleshooting, and teardown | AWS CloudFormation, S3, AWS CLI, LocalStack, YAML, Docker | Advanced |
| 4 | Multi-service serverless infrastructure combining S3 static hosting, Lambda compute, DynamoDB persistence, least-privilege IAM, failure handling, and zero-orphan teardown | AWS CloudFormation, S3, DynamoDB, Lambda, IAM, STS, Python, LocalStack, Docker | Advanced |

## Architecture Coverage

The implementations in this repository currently cover four major cloud-platform areas:

    Networking
        |
        +-- VPC address-space design
        +-- Public/private subnet segmentation
        +-- Internet gateway routing
        +-- Route-table associations

    Serverless Compute
        |
        +-- Python Lambda handlers
        +-- ZIP deployment packaging
        +-- IAM execution roles
        +-- Function invocation
        +-- Code updates
        +-- Deployment verification

    Infrastructure as Code
        |
        +-- CloudFormation YAML
        +-- Stack lifecycle management
        +-- Resource outputs
        +-- Stack updates
        +-- Event inspection
        +-- Controlled teardown

    Multi-Service Architecture
        |
        +-- S3 static hosting
        +-- Lambda application logic
        +-- DynamoDB persistence
        +-- Least-privilege IAM
        +-- Failure-path validation
        +-- Zero-orphan cleanup

## Repository Structure

    cloud-platform-engineering/
    |
    +-- vpc-public-private-routing/
    |   +-- README.md
    |
    +-- lambda-serverless-deployment/
    |   +-- README.md
    |   +-- docker-compose.yml
    |   +-- handler.py
    |   +-- trust-policy.json
    |   +-- payload-v1.json
    |   +-- response-v1.json
    |   +-- response-v2.json
    |   +-- function.zip
    |
    +-- cloudformation-stack-lifecycle/
    |   +-- README.md
    |   +-- infra.yaml
    |
    +-- serverless-fullstack-iac/
        +-- README.md
        +-- infra.yaml
        +-- index.html
        +-- error.html
        +-- valid-payload.json
        +-- invalid-payload.json
        +-- success-response.json
        +-- failure-response.json

## Technical Focus

The repository demonstrates practical experience with:

- AWS VPC architecture
- CIDR planning and subnet segmentation
- Internet gateways and route tables
- AWS Lambda deployment lifecycle
- Python serverless handlers
- Lambda invocation contracts
- IAM trust relationships
- Least-privilege policy design
- AWS CloudFormation
- Declarative infrastructure
- Stack lifecycle management
- S3 static website infrastructure
- DynamoDB serverless persistence
- CloudFormation intrinsic functions
- AWS CLI automation
- LocalStack cloud emulation
- Docker-based AWS service environments
- Resource-state verification
- Failure-path testing
- Infrastructure teardown
- Zero-orphan validation

## Engineering Principles Demonstrated

### Infrastructure as Code

Infrastructure is increasingly defined through declarative templates instead of manual console operations.

The CloudFormation implementations demonstrate:

    Desired State
         |
         v
    CloudFormation Template
         |
         v
    AWS-Compatible APIs
         |
         v
    Managed Infrastructure

This approach improves repeatability, reviewability, environment consistency, and lifecycle control.

### Least-Privilege Security

IAM permissions are designed around the operations actually required by the workload.

For example, the serverless full-stack implementation grants its Lambda function only:

    dynamodb:PutItem

against only the DynamoDB table managed by the same stack.

It does not grant broad permissions such as:

    dynamodb:*
    Resource: "*"

This reflects production security practices where application permissions are minimized by default.

### Explicit Validation

Infrastructure commands are not treated as successful simply because they return without an obvious shell error.

Implementations verify state using service APIs such as:

    describe-stacks
    list-stack-resources
    describe-vpcs
    describe-subnets
    describe-route-tables
    get-function
    scan
    list-functions
    s3 ls

This provides stronger evidence that the infrastructure reached the intended state.

### Reproducibility

LocalStack environments use pinned container versions where necessary instead of relying blindly on mutable image tags.

Tooling is also minimized where possible. Standard AWS CLI commands are redirected to local AWS-compatible endpoints rather than adding unnecessary dependencies.

### Troubleshooting Discipline

The implementations include practical debugging around:

- Docker socket permissions
- shell session resets
- malformed local endpoint aliases
- Lambda ZIP structure
- LocalStack runtime changes
- unsupported CloudFormation operations
- stack state loss
- S3 teardown dependencies
- CloudFormation rollback conditions
- Lambda code update verification

These failures are treated as part of the engineering workflow rather than hidden from the implementation.

## Cloud Architecture Progression

The repository currently demonstrates a progression from foundational infrastructure into integrated cloud systems:

    VPC Network Architecture
              |
              v
    Lambda Deployment Lifecycle
              |
              v
    CloudFormation IaC Lifecycle
              |
              v
    Multi-Service Serverless Architecture

This progression moves from individual infrastructure components toward complete, declaratively managed cloud systems.

## Real-World Relevance

The patterns implemented here map directly to common production cloud workloads.

### VPC Architecture

Public/private subnet patterns are used to separate internet-facing services from internal workloads such as:

- databases
- internal APIs
- application workers
- model-serving systems
- data-processing workloads

### Lambda

Serverless compute can support:

- API backends
- automation
- event processing
- file transformation
- notifications
- scheduled operations
- AI workflow orchestration
- security-response automation

### CloudFormation

Infrastructure as Code is used to reproduce consistent environments across:

- development
- staging
- production
- disaster recovery
- isolated testing environments

### S3 + Lambda + DynamoDB

This combination is commonly used for lightweight serverless applications, event ingestion, request processing, application metadata, automation, and low-maintenance backend systems.

## Tools and Technologies

    AWS
    |
    +-- VPC
    +-- S3
    +-- DynamoDB
    +-- Lambda
    +-- IAM
    +-- STS
    +-- CloudFormation

    Tooling
    |
    +-- AWS CLI v2
    +-- LocalStack
    +-- Docker
    +-- Docker Compose
    +-- Linux
    +-- Bash
    +-- Python
    +-- YAML
    +-- JSON
    +-- jq
    +-- JMESPath

## Current Portfolio Direction

The repository is focused on cloud platform engineering patterns that are increasingly important for roles involving:

- Cloud Platform Engineering
- DevOps Engineering
- DevSecOps Engineering
- AIOps Engineering
- Applied AI Infrastructure
- Serverless Engineering
- Cloud Architecture
- Infrastructure Automation

Future implementations can extend this foundation into areas such as:

- multi-AZ VPC design
- NAT gateways
- security groups and NACLs
- API Gateway
- event-driven architectures
- SQS and SNS
- CloudWatch observability
- container orchestration
- CI/CD infrastructure
- Terraform
- Kubernetes
- GitOps
- production-grade IAM boundaries
- secrets management
- multi-environment IaC patterns

## Summary

This repository demonstrates cloud infrastructure as an engineering system rather than as a collection of isolated service commands.

The implementations emphasize:

    Architecture
        +
    Infrastructure as Code
        +
    Security
        +
    Automation
        +
    Validation
        +
    Troubleshooting
        +
    Lifecycle Management

The current work spans networking, serverless compute, declarative infrastructure, and integrated multi-service AWS architectures using reproducible local environments and standard AWS-compatible tooling.
