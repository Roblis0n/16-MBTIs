import unittest
from minds.interview import create_interview, select_next_question, record_answer, should_stop_interview, render_questions, stop_interview
from minds.errors import MindsError

def questions(n=8):
    return [{'question_id':f'q{i}','text':f'Question {i}?','why':'Reduces a supplied uncertainty','target_uncertainty':f'u{i}','answer_status':'unasked','answer_summary':None} for i in range(n)]

class InterviewTests(unittest.TestCase):
    def test_known_budget_not_repeated(self):
        s=create_interview(questions(),ask_mode='interview',known_answers={'u0':'budget 500'})
        s=select_next_question(s); self.assertEqual(s['active_question_id'],'q1')
    def test_three_turn_answer_driven(self):
        s=create_interview(questions(3),ask_mode='interview')
        for i,status in enumerate(['answered','unknown','declined']):
            s=select_next_question(s); self.assertEqual(s['active_question_id'],f'q{i}')
            self.assertEqual(select_next_question(s),s)
            s=record_answer(s,f'q{i}','provided answer' if status=='answered' else None,answer_status=status)
        self.assertEqual(s['status'],'completed'); self.assertEqual(s['asked_turns'],3)
        self.assertEqual([q['answer_status'] for q in s['questions']],['answered','unknown','declined'])
    def test_caps_why_not_implied_by_heavy(self):
        s=create_interview(questions())
        for mode,cap in [('light',3),('middle',5),('heavy',7)]:
            r=render_questions(s,mode); self.assertEqual(len(r),cap); self.assertTrue(all('why' not in q for q in r))
    def test_explicit_mode_and_single_active(self):
        with self.assertRaises(MindsError): select_next_question(create_interview(questions()))
        s=select_next_question(create_interview(questions(),ask_mode='interview'))
        self.assertEqual(len(render_questions(s,'heavy')),1)
        with self.assertRaises(MindsError): record_answer(s,'q2','x')
    def test_turn_budget_and_exit(self):
        s=select_next_question(create_interview(questions(),ask_mode='interview',max_interview_turns=1))
        self.assertIsNone(should_stop_interview(s))
        s=record_answer(s,'q0','answer'); self.assertEqual(s['stop_reason'],'turn_budget')
        self.assertIsNone(select_next_question(s)['active_question_id'])
        stopped=stop_interview(s,'conclusion'); self.assertEqual(render_questions(stopped),[])
    def test_duplicate_uncertainty_rejected(self):
        qs=questions(2); qs[1]['target_uncertainty']='u0'
        with self.assertRaises(MindsError): create_interview(qs)
