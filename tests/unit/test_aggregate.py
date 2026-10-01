import unittest
from minds.aggregate import aggregate_scores
from minds.errors import MindsError

def score(actor,value,**extra):
    return {'actor_id':actor,'value':value,'subject_id':'title','subject_version':'1','criterion_id':'clarity','scale_id':'ordinal5',**extra}

class AggregateTests(unittest.TestCase):
    def test_distribution(self):
        r=aggregate_scores([score(str(i),v) for i,v in enumerate([2,3,3,5,5])])
        self.assertEqual((r['min'],r['modes'],r['max'],r['median']),(2,[3,5],5,3))
    def test_empty_even(self):
        self.assertIsNone(aggregate_scores([])['median'])
        self.assertEqual(aggregate_scores([score('a',2),score('b',5)])['median'],3.5)
    def test_object_version_scale_mismatch(self):
        for key in ('subject_id','subject_version','criterion_id','scale_id'):
            with self.assertRaises(MindsError) as c: aggregate_scores([score('a',2),score('b',3,**{key:'other'})])
            self.assertEqual(c.exception.code,'E_SCORE_OBJECT_MISMATCH')
    def test_duplicate_nonfinite_missing(self):
        for rows in [[score('a',2),score('a',3)],[score('a',float('nan'))],[score('a',True)],[{}]]:
            with self.assertRaises(MindsError): aggregate_scores(rows)
