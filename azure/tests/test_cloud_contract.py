import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

cloud = module('cloud_run')
sql = module('sql_warehouse')

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.request = 'a' * 32
        self.manifest = {'request_id':self.request, 'status':'complete', 'files':[
            {'path':f'data/cleaned/{name}.csv', 'blob':f'runs/{self.request}/data/cleaned/{name}.csv',
             'sha256':'b'*64, 'bytes':10}
            for name in ['annual_filings', 'financial_measures']]}

    def test_accepts_exact_completed_run(self):
        self.assertEqual(len(cloud.verify_manifest(self.manifest, self.request)), 2)

    def test_rejects_another_run(self):
        with self.assertRaises(ValueError): cloud.verify_manifest(self.manifest, 'c'*32)

    def test_rejects_incomplete(self):
        self.manifest['status']='running'
        with self.assertRaises(ValueError): cloud.verify_manifest(self.manifest, self.request)

    def test_rejects_missing_dataset(self):
        self.manifest['files'].pop()
        with self.assertRaises(ValueError): cloud.verify_manifest(self.manifest, self.request)

    def test_rejects_duplicate(self):
        self.manifest['files'].append(copy.deepcopy(self.manifest['files'][0]))
        with self.assertRaises(ValueError): cloud.verify_manifest(self.manifest, self.request)

    def test_rejects_foreign_blob(self):
        self.manifest['files'][0]['blob']='runs/other/data/cleaned/annual_filings.csv'
        with self.assertRaises(ValueError): cloud.verify_manifest(self.manifest, self.request)

    def test_rejects_invalid_hash(self):
        self.manifest['files'][0]['sha256']='not-a-hash'
        with self.assertRaises(ValueError): cloud.verify_manifest(self.manifest, self.request)

    def test_sql_schema_whitelist(self):
        self.assertEqual(sql.run_schema('run_'+self.request), 'run_'+self.request)
        for bad in ['main', 'run_;DROP TABLE x', 'run_'+'A'*32, 'run_'+'a'*31]:
            with self.assertRaises(ValueError): sql.run_schema(bad)

if __name__=='__main__': unittest.main()
