# Deployment and disaster recovery results

**Reference run:** November 20–21, 2026, AWS Academy Learner Lab, us-east-1  
**Source commit:** `b2603e93fe6d2804d1afeb740b8a929fb50e504d`  
**Jenkins:** `nsrl-mysql-cloud-webapp-delivery`, Build **#3**, final **SUCCESS**  
**Database:** `jj_nsrl`, Amazon RDS MySQL 8.4.11, Multi-AZ enabled

## Tested recovery sequence

| Stage | Evidence | Result |
| --- | --- | --- |
| Initial CI | Python unit tests (5 passed), GitHub Actions run succeeded | PASS |
| Provisioning | CloudFormation stack `nsrl-mysql-cloud` reached CREATE_COMPLETE | PASS |
| Delivery | S3 object version and SHA-256 checks; MySQL load; web app deployment through SSM | PASS |
| API | Healthy /healthz; stats and MD5 API; UI searches | PASS |
| Forced failover | AWS events started at 04:59:35.144 UTC and completed at 05:00:17.570 UTC, November 21 | PASS |
| New primary | us-east-1c → us-east-1b; standby reversed | PASS |
| Reconnection | Web app reported healthy, verified TLS, database query returned expected result | PASS |
| Manual snapshot | `nsrl-dr-snap-20261121050540` | PASS, available in 181.0 s |
| DR restore | `nsrl-dr-restore-20261121050540`, us-east-1c | PASS, available in 575.0 s |
| Restored DB | Verified TLS 1.3 and four table counts | PASS |
| Temporary DR cleanup | Workflow reported `delete_requested`; subsequent AWS listing omitted the restore instance | Observed removal |

**Clarification:** The AWS failover event interval is approximately **42.426 seconds**, not a measurement of client-visible downtime. The 181-second snapshot creation and 575-second restore are observed single-run timings, not production SLOs.

## Dataset integrity checks

| Table | Before failover | After failover | Restored database |
| --- | ---: | ---: | ---: |
| nsrl_file | 10,000 | 10,000 | 10,000 |
| nsrl_pkg | 85,885 | 85,885 | 85,885 |
| nsrl_os | 309 | 309 | 309 |
| nsrl_mfg | 2,624 | 2,624 | 2,624 |

The query dashboard also returned a single expected MD5 result after failover. TLS was negotiated as **TLSv1.3** with cipher **TLS_AES_256_GCM_SHA384** on both primary and restored connections.

## API demonstrations

- MD5 search for `51580C2AEA9DE8E933C858A34502F78D`: **one result**, observed **41.6 ms** in the browser after failover.
- Filename `.exe` and manufacturer `Microsoft`: **39 matches**, first 25 displayed; observed **136.9 ms** after failover.
- File size at least 1,000,000 bytes: **161 matches**, first 25 displayed; observed **55.9 ms** in an earlier query.
- These numbers are **individual browser observations**, not statistically significant latency benchmarks.

## Evidence and limits

The Jenkins job archived JSON evidence, including preflight, S3 release, verification, web-app verification and DR verification. The final DR JSON recorded **status: PASS**, **webapp_reconnected: true**, and matching counts on the restored database. The AWS console confirmed the manual snapshot reached **available / 100%**.

**Limitations:** Checking table counts does not prove byte-for-byte equality or zero client downtime. One manual recovery run cannot establish RTO/RPO guarantees. Jenkins job success demonstrates the configured checks completed, not an external security audit.

Images from the course report should be reviewed and redacted before publishing publicly (account, institutional username, tokens, sessions, IP addresses and other context where appropriate).