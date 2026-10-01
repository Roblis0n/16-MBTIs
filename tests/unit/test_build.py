from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import unittest
from tools.build import ROOT,build,collect,verify_existing,digest,make_zip
from runtime.minds.errors import MindsError

class BuildTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/"tests/临时 中文路径"; base.mkdir(exist_ok=True)
        self.temp=TemporaryDirectory(prefix="构建 ",dir=base)
        self.path=Path(self.temp.name).resolve()
        self.assertTrue(self.path.is_relative_to(base.resolve()))

    def tearDown(self):
        # Only this test's fresh directory; verify containment before recursive cleanup.
        if not self.path.is_relative_to((ROOT/"tests/临时 中文路径").resolve()): raise RuntimeError("unsafe cleanup")
        self.temp.cleanup()

    def clone_source(self):
        root=self.path/"isolated project"; root.mkdir()
        for d in ("source","runtime/minds"): shutil.copytree(ROOT/d,root/d)
        return root

    def test_wp04_02_two_clean_builds(self):
        root=self.clone_source()
        a=build(root,root/"one/16-minds"); b=build(root,root/"two/16-minds")
        self.assertEqual(a["zip_sha256"],b["zip_sha256"])
        for p in (root/"one/16-minds").rglob("*"):
            if p.is_file(): self.assertEqual(p.read_bytes(),(root/"two/16-minds"/p.relative_to(root/"one/16-minds")).read_bytes())
        self.assertEqual(build(root,root/"two/16-minds")["zip_sha256"],b["zip_sha256"])

    def test_x_build_01_forbidden_sources(self):
        root=self.clone_source()
        for name in (".env","holdout/answer.json","runs/private.json","__pycache__/x.pyc"):
            p=root/"source/references"/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text("synthetic_secret",encoding="utf-8")
            with self.assertRaises(Exception) as cm: collect(root)
            self.assertEqual(getattr(cm.exception,"code",None),"E_SEMANTIC")
            self.assertTrue(p.exists())
            p.unlink()
            if p.parent.name in ("holdout","runs","__pycache__"): p.parent.rmdir()

    def test_manual_generated_change_rejected(self):
        root=self.clone_source(); target=root/"plugins/16-minds"; build(root,target)
        f=target/"skills/minds/SKILL.md"; f.write_text("manual edit",encoding="utf-8")
        with self.assertRaises(Exception) as cm: build(root,target)
        self.assertEqual(getattr(cm.exception,"code",None),"E_EXISTS")
        self.assertEqual(f.read_text("utf-8"),"manual edit")

    def test_modified_dist_refused_before_output_write(self):
        root=self.clone_source(); target=root/"plugins/16-minds"; result=build(root,target)
        archive=root/result["zip_file"];archive.write_bytes(b"SYNTHETIC USER MODIFICATION")
        old=(target/"build-manifest.json").read_bytes()
        with self.assertRaises(Exception) as cm:build(root,target)
        self.assertEqual(getattr(cm.exception,"code",None),"E_EXISTS")
        self.assertEqual(archive.read_bytes(),b"SYNTHETIC USER MODIFICATION")
        self.assertEqual((target/"build-manifest.json").read_bytes(),old)

    def test_x_build_02_per_skill_fallback(self):
        _,files,_=collect(ROOT)
        for skill in (ROOT/"source/skills").iterdir():
            self.assertIn(f"skills/{skill.name}/scripts/minds_runtime/normalize.py",files)
            self.assertIn(f"skills/{skill.name}/references/personas/entj.json",files)
        with self.assertRaises(Exception) as cm: build(ROOT,self.path/"16-minds","shared")
        self.assertEqual(getattr(cm.exception,"code",None),"E_CAPABILITY")

    def test_paths_and_absolute_content_rejected(self):
        root=self.clone_source()
        with self.assertRaises(Exception) as cm: build(root,root/"../16-minds")
        self.assertEqual(getattr(cm.exception,"code",None),"E_PATH_ESCAPE")
        p=root/"source/references/leak.md"; p.write_text('C:/Users/synthetic/private.txt',encoding="utf-8")
        with self.assertRaises(Exception) as cm: collect(root)
        self.assertEqual(getattr(cm.exception,"code",None),"E_PATH_ESCAPE")

if __name__=="__main__": unittest.main()
