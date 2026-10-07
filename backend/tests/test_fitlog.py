import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app import main, seed
from app.models import DailyAnalysis
from app.calculations import food_totals, activity_burn, snapshot_hash

RESPONSE={'summary':'Logged day reviewed','dayScore':7,'proteinAssessment':'Below goal','deficitAssessment':'Above goal','activityAssessment':'Active','warnings':[],'recommendations':['Eat more protein'],'confidenceNotes':['Burn is estimated']}
@pytest.fixture()
def setup(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite:///{tmp_path}/test.db',connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    session=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(main,'Session',session);monkeypatch.setattr(seed,'Session',session);seed.seed()
    class Provider:
        name='mock';model='test';calls=0;fail=False;invalid=False;block=None
        def analyze(self,snapshot):
            self.calls+=1
            if self.block:self.block.wait(5)
            if self.fail:raise RuntimeError('Network failure')
            if self.invalid:return {'summary':'invalid'}
            return RESPONSE.copy()
    p=Provider();monkeypatch.setattr(main,'get_provider',lambda:p)
    with TestClient(main.app) as client:yield client,p,session

DAY='/api/logs/2026-10-07'
def test_calculations():
    assert snapshot_hash({'value':2500})==snapshot_hash({'value':2500.0})
    e={'quantity':2,'nutrition':{'baseQuantity':1,'calories':58,'proteinG':6.5}}
    assert food_totals(e)['calories']==116
    assert food_totals(e)['proteinG']==13
    assert activity_burn({'type':'walking','distanceKm':8.16},95.5,.5)==389.64
    assert snapshot_hash({'a':1,'b':2})==snapshot_hash({'b':2,'a':1})

def test_crud_and_history_zero_calls(setup):
    c,p,_=setup
    assert c.get('/api/today').status_code==200
    assert c.put(DAY+'/weight',json={'weightKg':95.5}).status_code==200
    log=c.post(DAY+'/foods',json={'foodPresetId':'bread','quantity':2,'unit':'slice'}).json()
    id=log['food'][0]['id']
    assert log['calculated']['totalCalories']==116
    assert c.patch(DAY+'/foods/'+id,json={'quantity':4,'unit':'slice'}).json()['calculated']['totalProteinG']==26
    assert c.put(DAY+'/tdee',json={'profile':'gym_walking'}).status_code==200
    log=c.post(DAY+'/activities',json={'type':'walking','distanceKm':8.16}).json()
    assert log['calculated']['walkingCaloriesEstimate']==389.64
    assert log['calculated']['deficitKcal']==3250-232
    aid=log['activity'][0]['id']
    assert c.patch(DAY+'/activities/'+aid,json={'type':'walking','distanceKm':5}).status_code==200
    assert c.get('/api/history?from=2026-10-01&to=2026-10-07').json()['sevenDay']['totalCalories']==232
    assert c.get(DAY+'/analysis').json()==[]
    assert c.delete(DAY+'/foods/'+id).status_code==200
    assert c.delete(DAY+'/activities/'+aid).status_code==200
    assert p.calls==0

def test_analysis_idempotency_stale_confirmation(setup):
    c,p,session=setup
    c.post(DAY+'/foods',json={'foodPresetId':'whey','quantity':4,'unit':'scoop'})
    a=c.post(DAY+'/analyze',json={})
    assert a.status_code==200 and p.calls==1
    assert c.post(DAY+'/analyze',json={}).json()['id']==a.json()['id']
    assert p.calls==1
    c.get(DAY);c.get(DAY+'/analysis');c.get('/api/history');assert p.calls==1
    c.put(DAY+'/weight',json={'weightKg':94})
    assert c.get(DAY).json()['analysis']['stale']
    assert c.post(DAY+'/analyze',json={}).status_code==409 and p.calls==1
    assert c.post(DAY+'/analyze',json={'confirmReanalysis':True}).status_code==200 and p.calls==2
    assert len(c.get(DAY+'/analysis').json())==2
    with session() as db:assert len(list(db.scalars(select(DailyAnalysis))))==2

def test_history_nutrition_is_immutable(setup):
    c,p,_=setup
    c.post(DAY+'/foods',json={'foodPresetId':'whey','quantity':1,'unit':'scoop'})
    c.patch('/api/foods/whey',json={'calories':999,'proteinG':1})
    assert c.get(DAY).json()['calculated']['totalCalories']==140
    assert c.get(DAY).json()['calculated']['totalProteinG']==25
    c.post(DAY+'/foods',json={'foodPresetId':'whey','quantity':1,'unit':'scoop'})
    assert c.get(DAY).json()['calculated']['totalCalories']==1139 and p.calls==0

@pytest.mark.parametrize('invalid',[False,True])
def test_failures_require_explicit_retry(setup,invalid):
    c,p,_=setup;p.fail=not invalid;p.invalid=invalid
    assert c.post(DAY+'/analyze',json={}).status_code==502 and p.calls==1
    assert c.get(DAY).json()['analysis'] is None
    assert c.post(DAY+'/analyze',json={}).status_code==409 and p.calls==1
    p.fail=False;p.invalid=False
    assert c.post(DAY+'/analyze',json={'retry':True}).status_code==200 and p.calls==2
    assert c.post(DAY+'/analyze',json={}).status_code==200 and p.calls==2

def test_concurrent_analyze_has_one_provider_call(setup):
    c,p,_=setup;c.get(DAY)
    p.block=threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(c.post,DAY+'/analyze',json={})
        import time
        for _ in range(100):
            if p.calls:break
            time.sleep(.01)
        second=c.post(DAY+'/analyze',json={})
        assert second.status_code==409
        p.block.set()
        assert first.result().status_code==200
    assert p.calls==1
    assert c.post(DAY+'/analyze',json={}).status_code==200 and p.calls==1

def test_validation_and_weight_memory(setup):
    c,p,_=setup
    assert c.put(DAY+'/weight',json={'weightKg':0}).status_code==422
    assert c.put(DAY+'/weight',json={'weightKg':500}).status_code==422
    assert c.post(DAY+'/foods',json={'foodPresetId':'whey','quantity':0,'unit':'scoop'}).status_code==422
    assert c.post(DAY+'/foods',json={'foodPresetId':'whey','quantity':1,'unit':'g'}).status_code==422
    assert c.post(DAY+'/activities',json={'type':'treadmill','durationMinutes':10}).status_code==422
    c.put(DAY+'/weight',json={'weightKg':94})
    assert c.get('/api/logs/2026-10-08').json()['weightKg']==94
    assert c.put('/api/settings',json={'proteinMinG':170,'proteinMaxG':150}).status_code==422
    assert p.calls==0

def test_provider_sends_one_structured_request(monkeypatch):
    import httpx,json
    from app.provider import OpenAICompatibleProvider
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(RESPONSE)}}]})
    original=httpx.Client
    monkeypatch.setenv('LLM_API_KEY','test-secret')
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    response=OpenAICompatibleProvider().analyze({'calculated':{'totalCalories':116}})
    assert response==RESPONSE and len(requests)==1
    payload=json.loads(requests[0].content)
    assert payload['response_format']['json_schema']['strict'] is True
    assert payload['response_format']['json_schema']['schema']['additionalProperties'] is False
    assert requests[0].headers['Authorization']=='Bearer test-secret'

def test_custom_food_and_settings_do_not_call_provider(setup):
    c,p,_=setup
    f=c.post('/api/foods',json={'name':'Test food','baseQuantity':100,'baseUnit':'ml','calories':50,'proteinG':3}).json()
    c.patch('/api/foods/'+f['id'],json={'favorite':False,'sortOrder':99})
    assert not any(x['id']==f['id'] for x in c.get('/api/foods?favorite=true').json())
    s=c.get('/api/settings').json();s['walkingCoefficient']=.6
    assert c.put('/api/settings',json=s).status_code==200
    c.post(DAY+'/foods',json={'foodPresetId':f['id'],'quantity':200,'unit':'ml'})
    assert c.get(DAY).json()['calculated']['totalCalories']==100
    assert c.delete('/api/foods/'+f['id']).status_code==200
    assert c.get(DAY).json()['food'][0]['displayName']=='Test food'
    assert p.calls==0
