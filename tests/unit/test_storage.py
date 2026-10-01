import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from runtime.minds import storage
from runtime.minds.errors import MindsError

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        (self.root/'.gitignore').write_text('.16minds/runs/\n')
    def tearDown(self): self.tmp.cleanup()
    def test_opt_in_creates_nothing(self):
        with self.assertRaises(MindsError): storage.create_run_dir(self.root)
        self.assertFalse((self.root/'.16minds').exists())
    def test_unique_private_atomic_and_no_clobber(self):
        a=storage.create_run_dir(self.root,True); b=storage.create_run_dir(self.root,True)
        self.assertNotEqual(a,b)
        p=f'.16minds/runs/{a}/report.json'
        storage.export_run(self.root,p,{'public':'safe'},True)
        old=(self.root/p).read_bytes()
        with self.assertRaises(MindsError) as e: storage.export_run(self.root,p,{'public':'changed'},True)
        self.assertEqual(e.exception.code,'E_EXISTS'); self.assertEqual((self.root/p).read_bytes(),old)
        self.assertEqual((self.root/p).stat().st_mode&0o777,0o600)
        self.assertFalse(list((self.root/p).parent.glob('.tmp-*')))
    def test_paths_and_symlinks(self):
        (self.root/'linked').symlink_to('/tmp',target_is_directory=True)
        for p in ['../bad','/tmp/bad','C:\\bad','\\\\host\\share','foo/../bad','CON','a.','a ','linked/bad']:
            with self.subTest(p=p), self.assertRaises(MindsError): storage.write_no_clobber(self.root,p,'x',True)
        (self.root/'target').symlink_to(self.root/'.gitignore')
        with self.assertRaises(MindsError): storage.resolve_authorized_path(self.root,'target')
    def test_ignore_and_tracked(self):
        (self.root/'.gitignore').write_text('')
        with self.assertRaises(MindsError): storage.create_run_dir(self.root,True)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        folder=self.root/'.16minds/runs'; folder.mkdir(parents=True); (folder/'old.json').write_text('{}')
        subprocess.run(['git','-C',str(self.root),'add','.16minds/runs/old.json'],check=True)
        (self.root/'.gitignore').write_text('.16minds/runs/\n')
        with self.assertRaises(MindsError): storage.create_run_dir(self.root,True)
    def test_delete_exact_preview_and_changed_file(self):
        a=storage.create_run_dir(self.root,True); b=storage.create_run_dir(self.root,True)
        p=f'.16minds/runs/{a}/record.json'; storage.export_run(self.root,p,{'x':1},True)
        preview=storage.delete_selected_run(self.root,a)
        self.assertTrue((self.root/p).exists())
        (self.root/p).write_text('{"x":2}')
        with self.assertRaises(MindsError): storage.delete_selected_run(self.root,a,True,preview['preview_digest'])
        preview=storage.delete_selected_run(self.root,a)
        storage.delete_selected_run(self.root,a,True,preview['preview_digest'])
        self.assertFalse((self.root/'.16minds/runs'/a).exists()); self.assertTrue((self.root/'.16minds/runs'/b).is_dir())
    def test_delete_rejects_link(self):
        a=storage.create_run_dir(self.root,True)
        (self.root/f'.16minds/runs/{a}/link').symlink_to(self.root/'.gitignore')
        with self.assertRaises(MindsError): storage.delete_selected_run(self.root,a)
        self.assertTrue((self.root/'.gitignore').exists())
    def test_concurrent_processes_only_one_publishes(self):
        script='''import sys\nfrom runtime.minds.storage import write_no_clobber\nfrom runtime.minds.errors import MindsError\ntry:\n write_no_clobber(sys.argv[1],"race.json",sys.argv[2],True); print("winner")\nexcept MindsError as e: print(e.code)\n'''
        ps=[subprocess.Popen([sys.executable,'-B','-c',script,str(self.root),str(i)],stdout=subprocess.PIPE,text=True) for i in range(8)]
        out=[p.communicate(timeout=15)[0].strip() for p in ps]
        self.assertEqual(out.count('winner'),1); self.assertEqual(sum(x in ('E_EXISTS','E_CONCURRENT_MODIFICATION') for x in out),7)
        self.assertIn((self.root/'race.json').read_text(),[str(i) for i in range(8)])
    def test_sensitive_export_and_html(self):
        for value in [{'password':'synthetic-only'},{'public':'api_key=FAKE_NOT_REAL'},{'hidden_reasoning':'not for export'}]:
            with self.assertRaises(MindsError): storage.export_run(self.root,'out.json',value,True)
        storage.export_run(self.root,'safe.md',{'field':'<script>alert(1)</script>','formula':'=1+1'},True,'markdown')
        s=(self.root/'safe.md').read_text(); self.assertNotIn('<script>',s); self.assertIn('&#x27;',s)
    def test_writer_lock_and_process_stale_preview(self):
        a=storage.create_run_dir(self.root,True);p=f'.16minds/runs/{a}/record.json'
        storage.export_run(self.root,p,{'x':1},True);preview=storage.delete_selected_run(self.root,a)
        subprocess.run([sys.executable,'-B','-c','import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("changed in another process")',str(self.root/p)],check=True)
        with self.assertRaises(MindsError) as e: storage.delete_selected_run(self.root,a,True,preview['preview_digest'])
        self.assertEqual(e.exception.code,'E_CONCURRENT_MODIFICATION');self.assertEqual((self.root/p).read_text(),'changed in another process')
        lock=(self.root/p).parent/'.minds-lock';lock.write_text('synthetic concurrent owner')
        with self.assertRaises(MindsError):storage.export_run(self.root,f'.16minds/runs/{a}/second.json',{},True)
        with self.assertRaises(MindsError):storage.delete_selected_run(self.root,a)
