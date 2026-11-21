import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'app'))

import server
import workshop


class CloudWebAppWorkshopTests(unittest.TestCase):
    def _valid_params(self):
        return {
            'DB_NAME': 'jj_nsrl',
            'STORAGE_GB': '20',
            'DB_INSTANCE_CLASS': 'db.t3.micro',
            'VPC_ID': 'vpc-0123456789abcdef0',
            'WEBAPP_SUBNET_ID': 'subnet-0123456789abcdef0',
            'DB_SUBNET_GROUP': 'nsrl-mysql-dbsubnetgroup-abc',
            'JENKINS_SECURITY_GROUP_ID': 'sg-0123456789abcdef0',
            'STACK_NAME': 'nsrl-mysql-cloud',
        }

    def test_valid_parameters_pass(self):
        workshop.validate(self._valid_params())

    def test_rejects_invalid_webapp_subnet(self):
        p = self._valid_params()
        p['WEBAPP_SUBNET_ID'] = 'invalid-subnet'
        with self.assertRaises(ValueError):
            workshop.validate(p)

    def test_manifest_and_data_files_exist(self):
        manifest = json.loads((ROOT / 'data' / 'manifest.json').read_text())
        self.assertEqual(manifest['tables']['file']['rows'], 10000)
        self.assertEqual(manifest['tables']['pkg']['rows'], 85885)
        for fname in workshop.NSRL_FILES:
            self.assertTrue((ROOT / 'data' / fname).exists(), fname)

    def test_cloudformation_template_has_ec2_and_rds(self):
        tpl = (ROOT / 'infra' / 'cloud-webapp.yaml').read_text()
        self.assertIn('AWS::RDS::DBInstance', tpl)
        self.assertIn('AWS::EC2::Instance', tpl)
        self.assertIn('require_secure_transport', tpl)
        self.assertIn('MultiAZ:', tpl)

    def test_search_query_builder_sha256_and_package(self):
        sha256 = '0' * 64
        sql, args, count_sql, count_args = server.build_search_query({
            'hash': sha256,
            'package_name': 'Windows',
            'limit': '15',
        })
        self.assertIn('sha256 = %s', sql)
        self.assertIn('package_name LIKE %s', sql)
        self.assertEqual(args, [sha256, '%Windows%', 15])
        self.assertEqual(count_args, [sha256, '%Windows%'])
        self.assertIn('COUNT(*)', count_sql)


if __name__ == '__main__':
    unittest.main()
