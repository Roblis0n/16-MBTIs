import tempfile
from pathlib import Path
import unittest
from runtime.minds import journal
from runtime.minds.errors import MindsError

def entry():
    return dict(decision_version='d1',goal='synthetic',evidence=['e1'],assumptions=['a'],triggers=['t'],recommendation='A',user_actual_choice=None,recorded_at='2026-09-30T13:00:00+02:00')
class JournalTests(unittest.TestCase):
    def test_no_persist_and_separate_choice(self):
        x=journal.save(entry()); self.assertFalse(x['persisted']); self.assertIsNone(x['entry']['user_actual_choice'])
        self.assertEqual(x['entry']['recorded_at'],'2026-09-30T11:00:00+00:00')
    def test_roundtrip_and_review(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'.gitignore').write_text('.16minds/runs/\n')
            saved=journal.save(entry(),root,True); original=journal.read(root,saved['run_id'])
            review=journal.review(original,'worked','user statement','2026-10-01T00:00:00Z',[])
            self.assertEqual(review['missing_sources'],['e1']); self.assertEqual(review['process_assessment'],'not_assessed')
            self.assertEqual(journal.read(root,saved['run_id']),original)
    def test_bad_time_and_unproven_outcome(self):
        e=entry(); e['recorded_at']='2026-09-30T00:00:00'
        with self.assertRaises(MindsError): journal.save(e)
        e=entry(); e['outcome']='success'
        with self.assertRaises(MindsError): journal.save(e)
    def test_canonical_identity_is_not_display_escaped(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'.gitignore').write_text('.16minds/runs/\n')
            e=entry();e.update(decision_version='-d1',evidence=['-e1'],recommendation='-retain literal ID',user_actual_choice='B')
            saved=journal.save(e,root,True);actual=journal.read(root,saved['run_id'])
            self.assertEqual(actual['decision_version'],'-d1');self.assertEqual(actual['evidence'],['-e1']);self.assertEqual(actual['user_actual_choice'],'B')
            self.assertEqual(journal.review(actual,available_evidence=['-e1'])['missing_sources'],[])
            self.assertFalse(saved['background_reminder'])
