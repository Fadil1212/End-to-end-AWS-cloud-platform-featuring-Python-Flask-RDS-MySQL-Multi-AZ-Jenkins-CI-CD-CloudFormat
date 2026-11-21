#!/usr/bin/env python3
"""EC2-Hosted Python Web App Server for CSCI 6907 (Cloud Computing).

Serves an interactive NSRL MySQL Query GUI and JSON REST APIs directly from an
Amazon Linux 2023 EC2 instance inside the VPC. Retrieves MySQL credentials from
AWS Secrets Manager via LabInstanceProfile, enforces strict TLS (verify-full)
with the AWS RDS global CA bundle, and reports live Multi-AZ Primary/Standby AZs.
"""
import json
import os
import socket
import ssl
import time
from pathlib import Path

import boto3
import pymysql
from flask import Flask, jsonify, render_template, request

APP_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(APP_DIR / 'templates'))

_SECRET_CACHE = None


def get_db_config():
    global _SECRET_CACHE
    host = os.environ.get('DB_HOST', '127.0.0.1')
    port = int(os.environ.get('DB_PORT', '3306'))
    db_name = os.environ.get('DB_NAME', 'jj_nsrl')
    secret_arn = os.environ.get('DB_SECRET_ARN', '')
    region = os.environ.get('AWS_REGION', 'us-east-1')

    if secret_arn:
        if _SECRET_CACHE is None:
            sm = boto3.client('secretsmanager', region_name=region)
            _SECRET_CACHE = json.loads(sm.get_secret_value(SecretId=secret_arn)['SecretString'])
        user = _SECRET_CACHE['username']
        password = _SECRET_CACHE['password']
    else:
        user = os.environ.get('DB_USER', 'nsrl_admin')
        password = os.environ.get('DB_PASSWORD', '')

    return host, port, db_name, user, password


def get_connection():
    host, port, db_name, user, password = get_db_config()
    ca_path = os.environ.get('RDS_CA_BUNDLE', '/opt/rds/global-bundle.pem')
    ssl_ctx = None
    if ca_path and Path(ca_path).exists():
        ssl_ctx = ssl.create_default_context(cafile=ca_path)
        ssl_ctx.check_hostname = os.environ.get('DB_SSL_VERIFY_HOSTNAME', 'true').lower() == 'true'
        ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        charset='utf8mb4',
        ssl=ssl_ctx,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=15,
        read_timeout=30,
    )


def get_rds_topology():
    db_id = os.environ.get('DB_IDENTIFIER', '')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    if not db_id:
        return {'multi_az': None, 'primary_az': 'local', 'secondary_az': None, 'status': 'local'}
    try:
        rds = boto3.client('rds', region_name=region)
        info = rds.describe_db_instances(DBInstanceIdentifier=db_id)['DBInstances'][0]
        return {
            'db_identifier': db_id,
            'status': info['DBInstanceStatus'],
            'multi_az': info['MultiAZ'],
            'primary_az': info['AvailabilityZone'],
            'secondary_az': info.get('SecondaryAvailabilityZone'),
            'storage_encrypted': info['StorageEncrypted'],
            'publicly_accessible': info['PubliclyAccessible'],
            'engine_version': info['EngineVersion'],
        }
    except Exception as exc:
        return {'db_identifier': db_id, 'error': str(exc)}


def build_search_query(params):
    where = []
    args = []

    digest = (params.get('hash') or '').strip().upper()
    if digest:
        if len(digest) == 32:
            where.append('md5 = %s')
            args.append(digest)
        elif len(digest) == 40:
            where.append('sha1 = %s')
            args.append(digest)
        elif len(digest) == 64:
            where.append('sha256 = %s')
            args.append(digest)
        else:
            where.append('(md5 LIKE %s OR sha1 LIKE %s OR sha256 LIKE %s)')
            like_val = f'{digest}%'
            args.extend([like_val, like_val, like_val])

    for param_name, col in [
        ('file_name', 'file_name'),
        ('package_name', 'package_name'),
        ('os_name', 'os_name'),
        ('manufacturer', 'manufacturer_name'),
    ]:
        val = (params.get(param_name) or '').strip()
        if val:
            where.append(f'{col} LIKE %s')
            args.append(f'%{val}%')

    min_size = (params.get('min_size') or '').strip()
    if min_size.isdigit():
        where.append('file_size >= %s')
        args.append(int(min_size))

    max_size = (params.get('max_size') or '').strip()
    if max_size.isdigit():
        where.append('file_size <= %s')
        args.append(int(max_size))

    limit = min(max(int(params.get('limit') or 50), 1), 200)
    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    sql = (
        'SELECT file_name, file_size, md5, sha1, sha256, package_id, package_name, '
        'package_version, os_name, manufacturer_name, application_type '
        f'FROM nsrl_file_details{where_sql} '
        'ORDER BY file_size DESC LIMIT %s'
    )
    count_sql = f'SELECT COUNT(*) AS total FROM nsrl_file_details{where_sql}'
    return sql, args + [limit], count_sql, list(args)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    try:
        t0 = time.time()
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW STATUS WHERE Variable_name IN ('Ssl_cipher', 'Ssl_version')")
                tls = {r['Variable_name']: r['Value'] for r in cur.fetchall()}
                cur.execute('SELECT VERSION() AS mysql_version, DATABASE() AS db_name')
                info = cur.fetchone()
        finally:
            conn.close()
        return jsonify({
            'status': 'healthy',
            'app_host': socket.gethostname(),
            'database': info['db_name'],
            'mysql_version': info['mysql_version'],
            'tls': tls,
            'latency_ms': round((time.time() - t0) * 1000, 1),
        })
    except Exception as exc:
        return jsonify({'status': 'unhealthy', 'error': str(exc)}), 503


@app.route('/api/info')
def api_info():
    topo = get_rds_topology()
    return jsonify({
        'service': 'NSRL MySQL Cloud Web App Server (CSCI 6907)',
        'app_host': socket.gethostname(),
        'region': os.environ.get('AWS_REGION', 'us-east-1'),
        'app_commit': os.environ.get('APP_COMMIT', 'local'),
        'rds_topology': topo,
    })


@app.route('/api/stats')
def api_stats():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  (SELECT COUNT(*) FROM nsrl_file) AS files,
                  (SELECT COUNT(*) FROM nsrl_pkg) AS packages,
                  (SELECT COUNT(*) FROM nsrl_os) AS operating_systems,
                  (SELECT COUNT(*) FROM nsrl_mfg) AS manufacturers
            """)
            counts = cur.fetchone()
            cur.execute("SHOW STATUS WHERE Variable_name IN ('Ssl_cipher', 'Ssl_version')")
            tls = {r['Variable_name']: r['Value'] for r in cur.fetchall()}
            cur.execute('SELECT VERSION() AS mysql_version, DATABASE() AS db_name')
            meta = cur.fetchone()
            cur.execute('SELECT source_commit, s3_bucket, s3_prefix, loaded_at FROM workshop_release ORDER BY id DESC LIMIT 1')
            release = cur.fetchone()
            if release and release.get('loaded_at'):
                release['loaded_at'] = str(release['loaded_at'])
    finally:
        conn.close()
    return jsonify({
        'app_host': socket.gethostname(),
        'app_commit': os.environ.get('APP_COMMIT', 'local'),
        'counts': counts,
        'tls': tls,
        'mysql_version': meta['mysql_version'],
        'database': meta['db_name'],
        'release': release,
        'rds_topology': get_rds_topology(),
    })


@app.route('/api/search')
def api_search():
    t0 = time.time()
    sql, args, count_sql, count_args = build_search_query(request.args)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(count_sql, count_args)
            total = cur.fetchone()['total']
            cur.execute(sql, args)
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({
        'total_matches': total,
        'returned': len(rows),
        'query_ms': round((time.time() - t0) * 1000, 1),
        'sql_preview': sql,
        'rows': rows,
    })


@app.route('/api/hash/<digest>')
def api_hash(digest):
    sql, args, _, _ = build_search_query({'hash': digest, 'limit': '25'})
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({'digest': digest.upper(), 'matches': len(rows), 'rows': rows})


if __name__ == '__main__':
    port = int(os.environ.get('APP_PORT', '8080'))
    app.run(host='0.0.0.0', port=port, debug=False)
