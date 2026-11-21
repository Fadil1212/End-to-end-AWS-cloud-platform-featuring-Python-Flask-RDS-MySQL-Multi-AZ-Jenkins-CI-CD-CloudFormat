# System architecture

## Purpose
A private EC2-hosted Python/Flask NSRL search interface backed by RDS MySQL 8.4, provisioned and updated through a parameterized CI/CD workflow. Implemented for GWU CSCI 6907 Cloud Computing.

## Component responsibilities

| Component | Responsibility |
| --- | --- |
| GitHub Actions | Run Python unit tests, CloudFormation linting and MySQL-backed test script on push/PR |
| Dedicated Jenkins EC2 | Run Dockerized, parameterized continuous delivery stages and archive JSON verification evidence |
| CloudFormation | Provision web host, RDS MySQL, S3 release bucket, generated database secret, security groups, CloudWatch log group |
| Amazon S3 | Versioned and AES256-encrypted releases; exact object version download and SHA-256 verification |
| AWS Systems Manager | Run Command deploys application service to EC2; Session Manager enables local browser port forwarding |
| Flask + Gunicorn | Search dashboard, query API, health checks, live database topology via AWS API |
| RDS MySQL 8.4 | Private DB, Multi-AZ standby, encrypted storage, TLS-required parameter group |
| Secrets Manager | Provision and retrieve database credentials without embedding passwords in source |
| Manual RDS snapshot | Independent restore into temporary Single-AZ DB for disaster recovery validation |

## Network and trust boundaries

- Region: **us-east-1**. Test VPC and subnet group spanned **us-east-1b** and **us-east-1c**.
- Jenkins host listens on **127.0.0.1:8080** for Jenkins UI and is accessed through SSM.
- The web application listens on **port 8080**, restricted at its security group to the Jenkins security group. Browser access is achieved through an SSM tunnel, not direct public inbound access.
- The webapp EC2 has a public IP assigned for bootstrap/package downloads. This does **not** mean the app's inbound HTTP port is publicly open.
- MySQL **3306** is restricted to the Jenkins and web application security groups. Database configuration sets **PubliclyAccessible=false**.
- RDS parameter group enables **require_secure_transport**. The application and loaders use an RDS CA bundle with certificate and hostname verification.
- S3 blocks public access, enables versioning/encryption, and denies insecure transport. Database secrets are read through an instance profile.

## Deployment path
1. GitHub Actions validates source and SQL assumptions independently from AWS infrastructure.
2. Jenkins clones repository over SSH using a **read-only deploy key**, then runs tests and CloudFormation validation.
3. A parameter gate and preflight test confirm VPC, security group, subnet group, and allowed parameters.
4. CloudFormation deploys the database, app host, bucket, and security resources.
5. Jenkins publishes versioned schema, data, and web bundle to S3 and checks content digests when downloading.
6. Jenkins loads MySQL tables over TLS, deploys the web bundle over SSM, and validates REST endpoints.
7. A separate optional disaster-recovery stage forces RDS failover, validates reconnection and counts, snapshots the database, restores a separate instance, then tests TLS and record counts again.

## Design trade-offs
- The course-lab instance profile and permissions are preexisting; adapting IAM for a different AWS account is required.
- The process uses one EC2 web application server, so the application tier itself is **not** highly available. Multi-AZ protects the database tier.
- SSM is used for administrative access rather than exposing Jenkins or the web app directly.
- The snapshot test provisions a temporary second RDS instance, potentially incurring cost.
- The S3 bucket has **DeletionPolicy: Retain** and the RDS instance **DeletionPolicy: Snapshot**; these require explicit post-lab inventory and cleanup.

For measured outcomes see [RESULTS.md](RESULTS.md).