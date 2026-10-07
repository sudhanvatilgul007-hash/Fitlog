import json
import threading
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from test_fitlog import setup
from app import main
from app.provider import OpenAICompatibleProvider, ProviderError

REQUEST={'name':'Cooked lentils','baseQuantity':100,'baseUnit':'g','details':''}
NUTRITION={'calories':116,'proteinG':9,'carbsG':20,'fatG':0.4,'fiberG':8,'notes':'Typical cooked lentils without oil; values are approximate.'}


def mock_food_provider(p, monkeypatch):
    def estimate(food):
        p.calls+=1
        if p.block:p.block.wait(5)
        if p.fail:raise RuntimeError('provider failure')
        return {'calories':-1} if p.invalid else NUTRITION.copy()
    monkeypatch.setattr(p,'estimate_food',estimate,raising=False)


def test_estimate_cache_save_scale_and_historical_values(setup,monkeypatch):
    c,p,_=setup;mock_food_provider(p,monkeypatch)
    result=c.post('/api/foods/estimate',json=REQUEST)
    assert result.status_code==200 and p.calls==1
    assert result.json()['source']=='ai'
    assert c.post('/api/foods/estimate',json={**REQUEST,'name':' cooked   LENTILS '}).json()['cached']
    assert p.calls==1
    food=c.post('/api/foods',json={**{k:v for k,v in REQUEST.items() if k!='details'},**{k:v for k,v in NUTRITION.items() if k!='notes'},'nutritionSource':'ai','nutritionNotes':NUTRITION['notes']}).json()
    scaled=c.post('/api/foods/estimate',json={**REQUEST,'baseQuantity':200}).json()
    assert scaled['source']=='saved' and scaled['calories']==232 and scaled['carbsG']==40 and p.calls==1
    log=c.post('/api/logs/2026-10-07/foods',json={'foodPresetId':food['id'],'quantity':200,'unit':'g'}).json()
    assert log['calculated']['totalCalories']==232
    assert log['food'][0]['nutrition']['fatG']==0.4
    c.patch('/api/foods/'+food['id'],json={'fatG':5})
    assert c.get('/api/logs/2026-10-07').json()['food'][0]['nutrition']['fatG']==0.4


def test_incomplete_saved_food_and_changed_preparation_need_ai(setup,monkeypatch):
    c,p,_=setup;mock_food_provider(p,monkeypatch)
    assert c.post('/api/foods/estimate',json={**REQUEST,'name':'Rice · cooked'}).json()['source']=='ai'
    assert p.calls==1
    c.post('/api/foods',json={'name':'Cooked lentils','baseUnit':'g','baseQuantity':100,**{k:v for k,v in NUTRITION.items() if k!='notes'}})
    assert c.post('/api/foods/estimate',json={**REQUEST,'details':'with butter'}).json()['source']=='ai'
    assert c.post('/api/foods/estimate',json={**REQUEST,'baseUnit':'ml'}).json()['source']=='ai'
    assert p.calls==3


@pytest.mark.parametrize('invalid',[False,True])
def test_failures_and_invalid_values_require_explicit_retry(setup,monkeypatch,invalid):
    c,p,_=setup;mock_food_provider(p,monkeypatch);p.fail=not invalid;p.invalid=invalid
    assert c.post('/api/foods/estimate',json=REQUEST).status_code==502
    assert c.post('/api/foods/estimate',json=REQUEST).status_code==409
    assert p.calls==1
    p.fail=False;p.invalid=False
    assert c.post('/api/foods/estimate',json={**REQUEST,'retry':True}).status_code==200
    assert p.calls==2


def test_estimate_concurrency_makes_one_call(setup,monkeypatch):
    c,p,_=setup;mock_food_provider(p,monkeypatch);p.block=threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(c.post,'/api/foods/estimate',json=REQUEST)
        import time
        for _ in range(100):
            if p.calls:break
            time.sleep(.01)
        assert c.post('/api/foods/estimate',json=REQUEST).status_code==409
        p.block.set();assert first.result().status_code==200
    assert p.calls==1


def test_estimate_validation_auth_and_user_isolation(setup,monkeypatch):
    c,p,_=setup;mock_food_provider(p,monkeypatch)
    for value in (0,-1,100001):
        assert c.post('/api/foods/estimate',json={**REQUEST,'baseQuantity':value}).status_code==422
    assert c.post('/api/foods/estimate',json={**REQUEST,'name':'   '}).status_code==422
    assert c.post('/api/foods/estimate',json=REQUEST,headers={'X-CSRF-Token':''}).status_code==403
    c.post('/api/foods/estimate',json=REQUEST)
    c.cookies.clear()
    assert c.post('/api/foods/estimate',json=REQUEST).status_code==401
    auth=c.post('/api/auth/signup',json={'email':'other@example.com','password':'another-password','gender':'female','age':30,'heightCm':160,'weightKg':60})
    assert auth.status_code==201
    c.headers['X-CSRF-Token']=auth.json()['csrfToken']
    assert c.post('/api/foods/estimate',json=REQUEST).json()['cached'] is False
    assert p.calls==2


def test_food_provider_strict_schema_and_request_payload(monkeypatch):
    monkeypatch.setenv('LLM_API_KEY','test-only-key')
    seen=[]
    def post(client,url,**kwargs):
        seen.append(kwargs['json'])
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(NUTRITION)}}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx.Client,'post',post)
    result=OpenAICompatibleProvider().estimate_food(REQUEST)
    assert result==NUTRITION and len(seen)==1
    schema=seen[0]['response_format']['json_schema']
    assert schema['strict'] and set(schema['schema']['required'])==set(NUTRITION)
    assert json.loads(seen[0]['messages'][1]['content'])==REQUEST


def test_missing_key_does_not_create_failed_claim(setup,monkeypatch):
    c,p,_=setup
    def unavailable():raise ProviderError('missing_api_key','Configure AI first',503)
    monkeypatch.setattr(main,'get_provider',unavailable)
    assert c.post('/api/foods/estimate',json=REQUEST).status_code==503
    mock_food_provider(p,monkeypatch);monkeypatch.setattr(main,'get_provider',lambda:p)
    assert c.post('/api/foods/estimate',json=REQUEST).status_code==200
