# NSRL MySQL 8.4 Cloud Computing Web App & DR Workshop (CSCI 6907)

Builds on the NSRL MySQL Database Workshop by deploying an **EC2-hosted Python/Flask Web App Server** (Amazon Linux 2023 + Gunicorn + systemd) connected privately to **Amazon RDS MySQL 8.4 Multi-AZ** over strict TLS (`verify-full`) with **AWS Secrets Manager** via `LabInstanceProfile`.

Demonstrates the complete Cloud Computing CI/CD and resilience lifecycle: GitHub Actions CI, dedicated private Jenkins EC2 host over SSM, versioned S3 release artifacts with SHA-256 verification, automated SSM Web App deployment, live **RDS Multi-AZ Standby Failover** with automatic Web App reconnection, and **Manual Snapshot Backup & Restore Disaster Recovery**.
