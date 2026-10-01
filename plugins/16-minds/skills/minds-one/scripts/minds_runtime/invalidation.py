"""Conservative data dependency invalidation. Not an executable graph language."""
import hashlib
from .contracts import canonical, check_json
from .errors import fail
from .tool_policy import request_object

CACHE_FIELDS={'content_hash','task_version','protocol_version','persona_version','model','settings','tool_snapshot','user_constraints','evidence_freshness','locale','workflow_hash'}

def cache_key(context,benchmark=False):
    check_json(context)
    if type(benchmark) is not bool: fail('E_SCHEMA','Benchmark flag must be boolean.')
    if benchmark: return None
    if not isinstance(context,dict) or set(context)!=CACHE_FIELDS or any(v is None for v in context.values()): return None
    if any(context[k] in ('','unknown') for k in ('content_hash','task_version','protocol_version','persona_version','model')): return None
    def unknown(v):
        if v is None or (isinstance(v,str) and v in ('','unknown')): return True
        if isinstance(v,dict): return any(unknown(x) for x in v.values())
        if isinstance(v,list): return any(unknown(x) for x in v)
        return False
    if unknown(context): return None
    return hashlib.sha256(canonical(context).encode()).hexdigest()

def invalidate(evidence_change,dependency_graph=None):
    check_json([evidence_change,dependency_graph])
    if not isinstance(evidence_change,dict): fail('E_SCHEMA','Evidence change must be an object.')
    request_object(evidence_change, (), {'changed_ids','goal_changed'}, {'goal_changed'})
    changed=evidence_change.get('changed_ids',[])
    if not isinstance(changed,list) or any(not isinstance(x,str) for x in changed): fail('E_SCHEMA','Changed IDs must be strings.')
    if dependency_graph is None:
        return {'affected_nodes':None,'affected_scope':'unknown','mode':'full_conservative',
                'fresh_required':True,'reuse_allowed':False,'node_status':{},
                'new_independent_samples':0,'rechecked_nodes':[],
                'note':'Dependency graph is absent. Re-evaluate the full task from fresh inputs; no prior result is approved for reuse and affected node IDs cannot be enumerated.'}
    if not isinstance(dependency_graph,dict): fail('E_SCHEMA','A supplied dependency graph must be an object or null.')
    request_object(dependency_graph, {'nodes','edges','complete'}, (), {'complete'})
    nodes=dependency_graph.get('nodes'); edges=dependency_graph.get('edges')
    if not isinstance(nodes,dict) or not isinstance(edges,list) or len(nodes)>10000: fail('E_SCHEMA','Graph requires bounded nodes and edges.')
    if any(not isinstance(v,dict) or v.get('kind') not in ('evidence','claim','decision') for v in nodes.values()): fail('E_SCHEMA','Invalid dependency node.')
    adjacency={k:set() for k in nodes}; indegree={k:0 for k in nodes}
    unknown=dependency_graph.get('complete') is not True or any(v.get('dependencies_known') is not True for v in nodes.values())
    for edge in edges:
        if not isinstance(edge,list) or len(edge)!=2 or any(not isinstance(x,str) or x not in nodes for x in edge): unknown=True; continue
        a,b=edge
        if (nodes[a]['kind'],nodes[b]['kind']) not in {('evidence','claim'),('claim','claim'),('claim','decision'),('evidence','decision')}: unknown=True
        if b not in adjacency[a]: adjacency[a].add(b); indegree[b]+=1
    queue=[k for k,v in indegree.items() if v==0]; visited=[]
    while queue:
        k=queue.pop(); visited.append(k)
        for nxt in adjacency[k]:
            indegree[nxt]-=1
            if indegree[nxt]==0: queue.append(nxt)
    if len(visited)!=len(nodes): unknown=True
    changed=evidence_change.get('changed_ids',[])
    if not isinstance(changed,list) or any(not isinstance(x,str) for x in changed): fail('E_SCHEMA','Changed IDs must be strings.')
    if any(x not in nodes for x in changed): unknown=True
    affected=set(nodes) if unknown else set(changed)
    if evidence_change.get('goal_changed') is True: affected.update(k for k,v in nodes.items() if v['kind']=='decision')
    # Time-varying facts need an explicit current freshness check, never an invented TTL.
    affected.update(k for k,v in nodes.items() if v.get('time_varying') is True and v.get('freshness_verified') is not True)
    todo=list(affected)
    while todo:
        for k in adjacency[todo.pop()]:
            if k not in affected: affected.add(k); todo.append(k)
    return {'affected_nodes':sorted(affected),'mode':'full_conservative' if unknown else 'incremental',
            'node_status':{k:'stale' if k in affected else 'reuse' for k in nodes},'new_independent_samples':0,
            'rechecked_nodes':[], 'note':'Affected nodes require actual re-evaluation before they can be marked rechecked.'}

def dispatch(data):
    if not isinstance(data,dict): fail('E_SCHEMA','Expected invalidation request.')
    if data.get('action')=='cache-key':
        request_object(data, {'action','context'}, {'benchmark'}, {'benchmark'})
        return {'status':'ok','cache_key':cache_key(data.get('context'),data.get('benchmark',False))}
    request_object(data, {'evidence_change'}, {'action','dependency_graph'})
    if data.get('action','invalidate')!='invalidate': fail('E_SCHEMA','Unknown invalidation action.')
    return {'status':'ok',**invalidate(data.get('evidence_change'),data.get('dependency_graph'))}
