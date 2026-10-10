import asyncio
from datetime import datetime,timezone,timedelta
from backend.mission import triage

def state(age=0,reference=False,thermal=False):
    return {'report':{'observed_at':(datetime.now(timezone.utc)-timedelta(minutes=age)).isoformat(),'status':'pending','reference':reference},'evidence':{'finding':{'smoke_detected':True},'temporal':{'frames':[]},'thermal_observations':[{}] if thermal else []}}

def test_agents_prioritize_fresh_corroboration_but_not_old_or_reference():
    async def run():
        fresh=await triage.ainvoke(state(thermal=True))
        old=await triage.ainvoke(state(age=120,thermal=True))
        reference=await triage.ainvoke(state(reference=True,thermal=True))
        assert fresh['rank']==4 and old['rank']==1 and reference['rank']==0
        assert len(fresh['agents'])==4
        assert 'fresh observation' in old['action']
    asyncio.run(run())

def test_environmental_context_can_raise_triage_priority_but_does_not_confirm_fire():
    assessed=state()
    assessed['report']['geographic_assessment']={'status':'available','data':{
        'screening':{'index':80,'label':'High screening conditions','coverage_percent':100,
            'factors':[{'name':'Mapped vegetation','value':'forest, scrub'}]}}}
    result=asyncio.run(triage.ainvoke(assessed))
    assert result['rank']==3
    assert 'not fire confirmation' in result['action']
    geo=next(agent for agent in result['agents'] if agent['name']=='Geographic context')
    assert 'forest, scrub' in geo['result']
    assert assessed['evidence']['finding']['smoke_detected'] is True

def test_mission_endpoint_excludes_preloaded_demo_and_separates_reference(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from backend.app import app
    from backend import mission,reporting
    monkeypatch.delenv('OPERATOR_PASSWORD',raising=False)
    monkeypatch.setenv('REPORT_DB',str(tmp_path/'reports.sqlite'))
    now=datetime.now(timezone.utc).isoformat()
    base={'id':'real','demo':False,'reference':False,'status':'pending','latitude':32.8,'longitude':-116.5,'observed_at':now,'submitted_at':now,'finding':{'smoke_detected':True,'confidence':.6},'events':[]}
    for r in [base,dict(base,id='reference',reference=True),dict(base,id='demo',demo=True)]:reporting.save(r)
    with TestClient(app) as c:r=c.get('/api/mission')
    assert r.status_code==200
    data=r.json();assert [r['id'] for r in data['queue']]==['real']
    assert data['reference_count']==1
    assert data['median_review_seconds'] is None
