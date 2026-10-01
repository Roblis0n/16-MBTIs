import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
class CliTests(unittest.TestCase):
    def call(self,command,payload=None):
        return subprocess.run([sys.executable,"-B",str(ROOT/"tools/minds_cli.py"),command],input=payload,capture_output=True,encoding="utf-8",cwd=ROOT.parent)

    def test_actual_help_version_and_json(self):
        for command in ("help","--help","version","--version"):
            p=self.call(command); self.assertEqual(p.returncode,0,p.stderr); self.assertEqual(json.loads(p.stdout)["status"],"ok")
        p=self.call("normalize",json.dumps({"raw_text":"--n 2 -- 合成材料"}))
        self.assertEqual(p.returncode,0); self.assertEqual(json.loads(p.stdout)["request"]["n"],2)

    def test_exit_codes_and_redaction(self):
        for command,payload,code in [("step",None,2),("unknown",None,2),("normalize",'{"raw_text":"秘密", "raw_text":"secret"}',2),("normalize",json.dumps({"raw_text":"问题","explicit_options":{"n":4,"budget":{"max_agent_turns":3}}}),4)]:
            p=self.call(command,payload); self.assertEqual(p.returncode,code,p.stdout)
            self.assertEqual(json.loads(p.stdout)["status"],"error")
            self.assertNotIn("secret",p.stdout+p.stderr)

if __name__=="__main__": unittest.main()
