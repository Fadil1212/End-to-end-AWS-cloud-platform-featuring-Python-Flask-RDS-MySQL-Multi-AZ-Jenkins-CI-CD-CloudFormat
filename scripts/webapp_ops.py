"""EC2 Python Web App deployment and verification helpers for CSCI 6907."""
import base64
import json
import tarfile
import time
import urllib.request
from pathlib import Path


def package_webapp_bundle(root: Path, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    bundle_path = out / 'webapp-bundle.tar.gz'
    with tarfile.open(bundle_path, 'w:gz') as tf:
        tf.add(root / 'app', arcname='app')
    return bundle_path


def deploy_webapp_ssm(session, out_dict: dict, release: dict):
    ssm = session.client('ssm')
    bundle = release['objects']['webapp-bundle.tar.gz']
    instance_id = out_dict['WebAppInstanceId']
    region = session.region_name

    deadline = time.time() + 420
    while time.time() < deadline:
        info = ssm.describe_instance_information(
            Filters=[{'Key': 'InstanceIds', 'Values': [instance_id]}]
        )['InstanceInformationList']
        if info and info[0].get('PingStatus') == 'Online':
            break
        time.sleep(10)

    unit_text = (
        '[Unit]\n'
        'Description=NSRL MySQL Python Web App Server (CSCI 6907)\n'
        'After=network.target\n\n'
        '[Service]\n'
        'Type=simple\n'
        'WorkingDirectory=/opt/nsrl-webapp/app\n'
        'EnvironmentFile=/opt/nsrl-webapp/webapp.env\n'
        'ExecStart=/opt/nsrl-webapp/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:8080 --timeout 60 server:app\n'
        'Restart=always\n'
        'RestartSec=3\n\n'
        '[Install]\n'
        'WantedBy=multi-user.target\n'
    )
    env_text = (
        f"AWS_REGION={region}\nDB_HOST={out_dict['DBEndpoint']}\nDB_PORT=3306\nDB_NAME={out_dict['DBName']}\n"
        f"DB_IDENTIFIER={out_dict['DBIdentifier']}\nDB_SECRET_ARN={out_dict['AdminSecretArn']}\n"
        f"SCRIPTS_BUCKET={out_dict['ScriptsBucketName']}\nRDS_CA_BUNDLE=/opt/rds/global-bundle.pem\n"
        f"DB_SSL_VERIFY_HOSTNAME=true\nAPP_PORT=8080\nAPP_COMMIT={release['source_commit']}\n"
    )
    unit_b64 = base64.b64encode(unit_text.encode()).decode()
    env_b64 = base64.b64encode(env_text.encode()).decode()

    commands = [
        'set -euo pipefail',
        'mkdir -p /opt/nsrl-webapp /opt/rds',
        'if [ ! -f /opt/rds/global-bundle.pem ]; then curl -fsSL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o /opt/rds/global-bundle.pem; fi',
        'if [ ! -x /opt/nsrl-webapp/venv/bin/gunicorn ]; then dnf install -y python3 python3-pip unzip >/dev/null && python3 -m venv /opt/nsrl-webapp/venv && /opt/nsrl-webapp/venv/bin/pip install --quiet boto3 pymysql cryptography flask gunicorn; fi',
        f"aws s3api get-object --region {region} --bucket {release['bucket']} --key {bundle['key']} --version-id {bundle['version_id']} /tmp/webapp-bundle.tar.gz >/dev/null",
        f"echo \"{bundle['sha256']}  /tmp/webapp-bundle.tar.gz\" | sha256sum -c -",
        'tar -xzf /tmp/webapp-bundle.tar.gz -C /opt/nsrl-webapp',
        f'echo "{env_b64}" | base64 -d > /opt/nsrl-webapp/webapp.env',
        'chmod 600 /opt/nsrl-webapp/webapp.env',
        f'echo "{unit_b64}" | base64 -d > /etc/systemd/system/nsrl-webapp.service',
        'systemctl daemon-reload',
        'systemctl enable nsrl-webapp.service',
        'systemctl restart nsrl-webapp.service',
        'sleep 3',
        'systemctl is-active nsrl-webapp.service',
    ]

    resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': commands},
    )
    cmd_id = resp['Command']['CommandId']
    while True:
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
        if inv['Status'] in ('Success', 'Failed', 'Cancelled', 'TimedOut'):
            if inv['Status'] != 'Success':
                raise RuntimeError(f"SSM WebApp deploy failed ({inv['Status']}): {inv.get('StandardErrorContent')}")
            print(f"EC2 Web App deployed via SSM ({cmd_id}): {inv.get('StandardOutputContent', '').strip()}")
            break


def http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))


def verify_webapp_endpoints(out_dict: dict, release: dict) -> dict:
    base_url = f"http://{out_dict['WebAppPrivateIp']}:8080"
    health = http_json(f'{base_url}/healthz')
    stats = http_json(f'{base_url}/api/stats')
    search = http_json(f'{base_url}/api/search?hash=51580C2AEA9DE8E933C858A34502F78D')

    if health.get('status') != 'healthy':
        raise RuntimeError(f'Web App unhealthy: {health}')
    if stats['counts']['files'] != 10000:
        raise RuntimeError(f'Unexpected file count from Web App: {stats}')
    if stats.get('app_commit') != release['source_commit']:
        raise RuntimeError(f"Web App commit mismatch: {stats.get('app_commit')} != {release['source_commit']}")
    if search['total_matches'] < 1:
        raise RuntimeError(f'Expected MD5 match from Web App API, got: {search}')

    return {
        'status': 'PASS',
        'webapp_instance_id': out_dict['WebAppInstanceId'],
        'webapp_private_ip': out_dict['WebAppPrivateIp'],
        'health': health,
        'stats': stats,
        'sample_md5_api': search,
    }
