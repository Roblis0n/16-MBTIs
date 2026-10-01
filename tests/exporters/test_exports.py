import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tools.build import collect, digest, json_bytes
from tools.exporters import export_standalone,export_claude

ROOT=Path(__file__).resolve().parents[2]
class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); cls.root=Path(cls.temp.name)
        cls.package=cls.root/'package'; cls.package.mkdir()
        source=cls.root/'source-copy'; source.mkdir()
        # Isolated test snapshot excludes interpreter caches created by other workers.
        for directory in ('source','runtime'):
            shutil.copytree(ROOT/directory,source/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        identity,files,inputs=collect(source)
        manifest={'source_hashes':inputs,'files':{p:digest(b) for p,b in files.items()}}
        files['build-manifest.json']=json_bytes(manifest)
        for p,b in files.items():
            target=cls.package/p; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def test_isolated_write_has_all_resources(self):
        dest=self.root/'standalone'
        m=export_standalone(self.package,dest)
        self.assertEqual(m['status'],'experimental_exporter')
        self.assertEqual(m['eight_entry_smoke'],'not_run')
        isolated=self.root/'isolated'; shutil.copytree(dest/'skills/minds-write',isolated)
        self.assertTrue((isolated/'references/personas/intj.json').is_file())
        self.assertTrue((isolated/'LICENSE').is_file())
        script='import sys;sys.path.insert(0,sys.argv[1]);from minds_runtime.resources import registry;assert len(registry()["commands"])==8'
        r=subprocess.run([sys.executable,'-B','-c',script,str(isolated/'scripts')],cwd=self.root,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr.decode())
    def test_name_conflict_no_overwrite(self):
        dest=self.root/'conflict'; dest.mkdir(); (dest/'user.txt').write_text('keep')
        with self.assertRaises(FileExistsError): export_standalone(self.package,dest)
        self.assertEqual((dest/'user.txt').read_text(),'keep')
    def test_claude_same_core(self):
        dest=self.root/'claude'; r=export_claude(self.package,dest)
        self.assertEqual((dest/'skills/minds-pair/SKILL.md').read_bytes(),(self.package/'skills/minds-pair/SKILL.md').read_bytes())
        self.assertTrue((dest/'.claude-plugin/plugin.json').exists())
        self.assertIsNone(r['host_version'])
    def test_tampered_core_refused(self):
        package=self.root/'tampered'; shutil.copytree(self.package,package)
        (package/'skills/minds-write/SKILL.md').write_text('changed')
        with self.assertRaises(Exception): export_standalone(package,self.root/'bad-output')
        self.assertFalse((self.root/'bad-output').exists())
