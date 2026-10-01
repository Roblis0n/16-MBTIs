import unittest
from runtime.minds.personas import load_persona
from runtime.minds.resources import registry,resource_root
from runtime.minds.errors import MindsError

class PersonaTests(unittest.TestCase):
    def test_sixteen_distinct_assets_and_references(self):
        lenses=set(); voices=set(); checks=set()
        for pid in registry()["personas"]:
            p=load_persona(pid)
            lenses.add(tuple(p["lens"])); voices.add(tuple(p["voice"])); checks.add(tuple(p["self_check"]))
            self.assertTrue((resource_root()/p["common_competence_ref"]).is_file())
            self.assertEqual({m["field"] for m in p["source_map"]},{"lens","voice","self_check","common_competence_ref"})
            self.assertTrue(all("L" in m["source_section"] for m in p["source_map"]))
        self.assertEqual([len(lenses),len(voices),len(checks)],[16,16,16])

    def test_invalid_persona_and_revision(self):
        self.assertEqual(load_persona(" INTJ ")["id"],"intj")
        for pid,rev in (("unknown",None),("intj","other"),(None,None)):
            with self.assertRaises(MindsError): load_persona(pid,rev)

if __name__=="__main__": unittest.main()
