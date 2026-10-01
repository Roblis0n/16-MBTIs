"""Actual packaged helper processes, not a Codex installation/skill invocation test."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import subprocess
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
class PackagedTests(unittest.TestCase):
    def test_eight_helpers_in_isolated_chinese_space_path(self):
        base=ROOT/"tests/临时 中文路径"; base.mkdir(exist_ok=True)
        with TemporaryDirectory(prefix="插件 隔离 ",dir=base) as temp:
            isolated=Path(temp).resolve()
            self.assertTrue(isolated.is_relative_to(base.resolve()))
            identity=json.loads((ROOT/"source/plugin/identity.json").read_text("utf-8"))
            archive=ROOT/"dist"/f"16-minds-{identity['version']}-static_candidate.zip"
            with zipfile.ZipFile(archive) as z:
                for info in z.infolist():
                    dest=isolated/info.filename
                    self.assertTrue(dest.resolve().is_relative_to(isolated))
                    self.assertNotEqual(info.external_attr>>16&0o170000,0o120000)
                z.extractall(isolated)
            package=isolated/"16-minds"
            manifest=json.loads((package/"build-manifest.json").read_text("utf-8"))
            import hashlib
            actual={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob("*") if p.is_file() and p.name!="build-manifest.json"}
            self.assertEqual(actual,manifest["files"])
            for relative in actual:
                self.assertFalse(any(part in relative.split('/') for part in ("tests","holdout","baseline","runs","__pycache__",".env")))
            self.assertFalse((isolated/"source").exists())
            env=dict(os.environ); env["PYTHONPATH"]=str(isolated/"nonexistent")
            env["HOME"]=str(isolated/"nonexistent home"); env["USERPROFILE"]=env["HOME"]
            reg=json.loads((package/"skills/minds/references/commands/registry.json").read_text("utf-8"))
            for entry in reg["commands"]:
                skill=package/"skills"/entry["skill"]; helper=skill/"scripts/minds_cli.py"
                for cwd in (isolated,package/"skills"):
                    # -I ignores PYTHONPATH/site customization; helper resolves all package assets itself.
                    def call(command,payload=None):
                        p=subprocess.run([sys.executable,"-I","-B",str(helper),command],input=None if payload is None else json.dumps(payload,ensure_ascii=False),capture_output=True,encoding="utf-8",cwd=cwd,env=env)
                        self.assertNotIn("Traceback",p.stderr)
                        return p,json.loads(p.stdout)
                    p,data=call("version"); self.assertEqual(p.returncode,0); self.assertEqual(data["version"],identity["version"])
                    opts={"workflow":entry["workflow"]}
                    if entry["workflow"]=="vote": opts["workflow_options"]={"proposal_id":"p1","proposal_version":"v1","proposal_text":"合成提案"}
                    if entry["workflow"]=="decide": opts["workflow_options"]={"candidates":[{"id":"a","version":"v1","description":"A"},{"id":"b","version":"v1","description":"B"}],"user_goal":"合成目标","hard_constraints":[]}
                    p,data=call("normalize",{"raw_text":"-- 合成正文 --n 99","explicit_options":opts})
                    self.assertEqual(p.returncode,0,data); request=data["request"]
                    self.assertEqual(request["workflow"],entry["workflow"]); self.assertEqual(request["question"],"合成正文 --n 99")
                    p,data=call("validate",{"kind":"request","payload":request}); self.assertEqual(p.returncode,0,data)
                    persona=json.loads((skill/"references/personas/entj.json").read_text("utf-8"))
                    p,data=call("validate",{"kind":"persona","payload":persona}); self.assertEqual(p.returncode,0,data)
                    p,data=call("execute",{}); self.assertEqual(p.returncode,3); self.assertEqual(data["error"]["machine_code"],"E_CAPABILITY")
            self.assertTrue((ROOT/"source").is_dir(),"原始维护源始终保留")

if __name__=="__main__": unittest.main()
