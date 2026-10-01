"""Execute bounded, developer-authored synthetic gold checks. No model invocation."""
import json
from pathlib import Path

def check():
    gold=json.loads((Path(__file__).parent/'answers/development-gold.json').read_text())
    actual={}
    active=0
    for event in ('mount','unmount','mount','unmount'):
        if event=='mount': active+=1
    actual['engineering-1']={'active_timers':active}
    try: [][0]
    except IndexError: empty='IndexError'
    actual['engineering-2']={'empty':empty,'singleton':[7][0]}
    display=None
    for response in ('B','A'): display=response
    actual['engineering-3']={'final_display':display}
    actual['engineering-4']={'keyboard_activation_provided':False}
    a,b=95+10,100
    actual['decision-1']={'A_total':a,'B_total':b,'feasible':[k for k,v in {'A':a,'B':b}.items() if v<=100]}
    candidates={'A':{'offline':True,'sync':False},'B':{'offline':False,'sync':True}}
    feasible=[k for k,v in candidates.items() if all(v.values())]
    actual['decision-2']={'status':'no_feasible_option' if not feasible else 'feasible','feasible':feasible}
    actual['decision-3']={'status':'needs_information','feasible':[],'unknown':['A'],'rejected':['B']}
    tie=(40-10)//(5-2)
    assert 40+2*tie==10+5*tie and 40+2*(tie-1)>10+5*(tie-1) and 40+2*(tie+1)<10+5*(tie+1)
    actual['decision-4']={'tie_q':tie,'below':'B','above':'A'}
    rows=[{'task_id':k,'actual':v,'matches_authored_gold':v==gold[k]['expected'],'method':gold[k]['verification']} for k,v in actual.items()]
    return {'status':'pass' if all(r['matches_authored_gold'] for r in rows) else 'failed','checks':rows,'model_trials':0,
            'limitations':['Developer-authored development gold, not independent ground truth audit','Engineering-4 and decision-3 are explicit feature/permission tables, not host tests','Writing requires independent semantic review; not auto-scored accuracy']}
if __name__=='__main__': print(json.dumps(check(),indent=2))
