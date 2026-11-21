# Operations, reproducibility and cleanup

## Prerequisites
- Python and dependencies listed in `requirements.txt`; AWS CLI; Git; an AWS account where EC2, SSM, CloudFormation, S3, Secrets Manager, RDS and CloudWatch are permitted.
- A VPC, public-outbound EC2 subnet, and DB subnet group covering two Availability Zones.
- An appropriate instance profile. The reference implementation uses **LabInstanceProfile**, an AWS Academy-specific resource; adjust policies and roles for another account.
- A dedicated Jenkins EC2 host with Docker; GitHub SSH deploy key attached as **read-only**.
- Confirm permissions and costs before enabling RDS Multi-AZ, restoration and additional EC2 instances.

## CI checks
From project root:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The GitHub Actions workflow also uses `cfn-lint infra/*.yaml` and a MySQL 8.4 service for `python scripts/test_database.py`.

## CD controls
The [Jenkinsfile](../Jenkinsfile) exposes database name, allocated storage, instance class, Multi-AZ, VPC, subnet, DB subnet group, Jenkins security group, CloudFormation stack name, and AWS region.

Both `RUN_DEPLOYMENT` and `RUN_FAILOVER_DR_TEST` default to **false**. A CI-only build does not create an RDS instance. The optional failover test **deliberately causes database disruption**, and the restore stage creates a temporary extra database.

## Access and health checks
The application's expected port on EC2 is `8080`. In a properly authorized workstation, a Session Manager port-forwarding session can bind a local port (for example `18089`) to that instance's port `8080`. The local URL is **not an Internet-accessible hosted website**.

Test the app from an authorized location:

```bash
curl http://127.0.0.1:18089/healthz
curl http://127.0.0.1:18089/api/stats
```

Never commit local AWS credentials, Jenkins passwords, SSH private keys, exported secrets, or live authorization cookies.

## Evidence collection
Before deleting lab infrastructure, save:
1. GitHub Actions successful CI workflow and Jenkins final SUCCESS console/log.
2. S3 release verification and Jenkins archived JSON artifacts.
3. CloudFormation outputs with sensitive identifiers appropriately masked for public use.
4. RDS failover events, snapshot available state, restored-data verification.
5. Browser UI and sample API search responses.
6. A copy of the final university report in a private location. Public repo screenshots should be reviewed for exposed details.

## Cleanup — project resources only
**Never delete the AWS Academy's original lab stack or unrelated VPC/network resources.**

1. Finish and export evidence; stop local SSM port-forwarding sessions.
2. Inventory the project CloudFormation stacks and their resources: `nsrl-mysql-cloud` (RDS + webapp) and `nsrl-mysql-cloud-jenkins` (dedicated Jenkins host).
3. Confirm temporary DR restored instances are already deleted. Manually retained recovery snapshots should be tracked separately.
4. Delete the application stack and wait for completion. Its RDS database has **DeletionPolicy: Snapshot**, so database deletion may produce another retained snapshot. Its S3 bucket has **DeletionPolicy: Retain**, so the bucket and all object versions may remain.
5. Identify and remove no-longer-needed retained project snapshots and **all versions/delete markers** from the retained project S3 bucket, if your evidence is safely saved and the course permits cleanup.
6. Delete the dedicated Jenkins stack after no longer needing the Jenkins logs or other resources. If a subnet group remains in use by an RDS instance, the instance must finish deleting before the subnet group can be removed.
7. Verify that project-specific EC2, RDS databases/snapshots, S3 buckets, secrets, log groups and CloudFormation resources are gone as intended. Retained and shared resources must be handled explicitly.

**Do not** automatically delete a database, bucket, snapshot or stack solely because it has a similar name. Confirm ownership, scope and retention requirements first.

## Caveats
- The database is Multi-AZ, but the webapp is a single EC2 host; the entire system is not full-stack highly available.
- The exact lab's administrative IAM policy restricts actions; a command can be denied even if the action normally exists in AWS.
- Source code here is a reproducible example, not a hardened production deployment.