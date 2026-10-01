"""Authorization preflight only: deliberately contains no network/SDK/key access."""
from evaluation.protocol import number

def multimodel_experiment(protocol, explicit_provider_permissions, budget):
    number(budget)
    gaps=[]
    if not protocol.get('baseline_completed'): gaps.append('Single-model baseline is not complete')
    if not protocol.get('experiment_approval_ref'): gaps.append('No independently approved experiment CR')
    if budget <= 0: gaps.append('No positive authorized budget')
    providers=protocol.get('providers',[])
    fields=protocol.get('data_fields',[])
    if not providers or len(set(providers))!=len(providers): gaps.append('Unique explicit providers required')
    if not fields: gaps.append('No field-level disclosure specification')
    permissions=explicit_provider_permissions or {}
    for provider in providers:
        permission=permissions.get(provider,{})
        if permission.get('api_authorized') is not True or not permission.get('approval_ref'):
            gaps.append('Provider API permission absent: '+provider)
        authorized=permission.get('fields',[])
        if not set(fields)<=set(authorized): gaps.append('Field-level transmission permission absent: '+provider)
        if not permission.get('model_ids') or protocol.get('models',{}).get(provider) not in permission['model_ids']:
            gaps.append('Exact model permission absent: '+provider)
    estimate=protocol.get('maximum_cost')
    if estimate is None: gaps.append('No bounded maximum cost')
    else:
        number(estimate)
        if estimate > budget: gaps.append('Protocol exceeds authorized budget')
    return {'status':'not_run','external_calls':0,'spent':0,'preflight_valid':not gaps,
            'limitations':gaps+['No external adapter installed; approval metadata alone is not trusted execution authority'],
            'results':[],'productization':'no_go','default_routing_changed':False}
