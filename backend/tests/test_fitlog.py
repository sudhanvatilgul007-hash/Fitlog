import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app import main, seed, auth
from app.models import DailyAnalysis, User, AuthSession
from app.calculations import food_totals, activity_burn, snapshot_hash

RESPONSE={'summary':'Logged day reviewed','dayScore':7,'proteinAssessment':'Below goal','deficitAssessment':'Above goal','activityAssessment':'Active','warnings':[],'recommendations':['Eat more protein'],'confidenceNotes':['Burn is estimated']}
@pytest.fixture()
def setup(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite:///{tmp_path}/test.db',connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def enable_foreign_keys(connection,record): connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    session=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(main,'Session',session);monkeypatch.setattr(seed,'Session',session);monkeypatch.setattr(auth,'Session',session);monkeypatch.setattr(auth,'_attempts',{});seed.seed()
    from datetime import datetime,timedelta,timezone
    with session() as db:
        db.add(User(id='personal',email='test@example.com',password_hash=auth.hash_password('test-password'),profile={'gender':'male','age':30,'heightCm':175,'weightKg':95.5}))
        db.flush()
        db.add(AuthSession(token_hash=auth.digest('test-session'),user_id='personal',csrf='test-csrf',expires_at=datetime.now(timezone.utc)+timedelta(days=1)))
        db.commit()
    class Provider:
        name='mock';model='test';calls=0;fail=False;invalid=False;block=None
        def analyze(self,snapshot):
            self.calls+=1
            if self.block:self.block.wait(5)
            if self.fail:raise RuntimeError('Network failure')
            if self.invalid:return {'summary':'invalid'}
            return RESPONSE.copy()
    p=Provider();monkeypatch.setattr(main,'get_provider',lambda:p)
    with TestClient(main.app) as client:
        client.cookies.set(auth.COOKIE,'test-session',domain='testserver.local')
        client.headers['X-CSRF-Token']='test-csrf'
        yield client,p,session

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
    assert log['calculated']['deficitKcal']==3283.97-232
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

def test_automatic_tdee_tracks_weight_and_logged_expenditure(setup):
    c,p,_=setup
    initial=c.get(DAY).json()
    assert initial['profile']=='automatic'
    assert initial['calculated']['totalExpenditureKcal']==2284.5
    assert c.put(DAY+'/weight',json={'weightKg':90}).json()['calculated']['selectedTDEE']==2218.5
    log=c.post(DAY+'/activities',json={'type':'walking','distanceKm':8}).json()
    assert log['calculated']['walkingCaloriesEstimate']==360
    assert log['calculated']['totalExpenditureKcal']==2578.5
    log=c.post(DAY+'/activities',json={'type':'cycling','durationMinutes':10}).json()
    assert log['calculated']['exerciseCaloriesEstimate']==78.75
    assert log['calculated']['totalExpenditureKcal']==2657.25
    log=c.post(DAY+'/foods',json={'foodPresetId':'whey','quantity':1,'unit':'scoop'}).json()
    assert log['calculated']['deficitKcal']==2517.25
    aid=next(a['id'] for a in log['activity'] if a['type']=='walking')
    log=c.patch(DAY+'/activities/'+aid,json={'type':'walking','distanceKm':10}).json()
    assert log['calculated']['totalExpenditureKcal']==2747.25
    assert c.delete(DAY+'/activities/'+aid).json()['calculated']['totalExpenditureKcal']==2297.25
    assert p.calls==0

def test_full_day_profiles_and_overrides_do_not_double_count(setup):
    c,p,_=setup
    c.put(DAY+'/weight',json={'weightKg':95.5})
    c.post(DAY+'/activities',json={'type':'walking','distanceKm':8.16})
    log=c.put(DAY+'/tdee',json={'profile':'gym_walking'}).json()
    assert log['calculated']['selectedTDEE']==3283.97
    assert not log['calculated']['activityIncluded']
    log=c.put(DAY+'/weight',json={'weightKg':90}).json()
    assert log['calculated']['selectedTDEE']==3189.09
    assert c.put(DAY+'/tdee',json={'profile':'custom'}).status_code==422
    c.put(DAY+'/tdee',json={'profile':'custom','kcal':2800})
    assert c.put(DAY+'/weight',json={'weightKg':85}).json()['calculated']['selectedTDEE']==2800
    assert p.calls==0

def test_past_expenditure_calibration_is_preserved_when_settings_change(setup):
    c,p,session=setup
    old='/api/logs/2020-01-01'
    c.post(old+'/activities',json={'type':'walking','distanceKm':8})
    before=c.get(old).json()['calculated']
    s=c.get('/api/settings').json();s['walkingCoefficient']=.7;s['tdeeReferenceWeightKg']=100;s['tdeeProfiles']['sedentary']=2700
    assert c.put('/api/settings',json=s).status_code==200
    assert c.get(old).json()['calculated']==before
    from app.models import DailyLog
    with session() as db:
        row=db.scalar(select(DailyLog).where(DailyLog.date=='2020-01-01'))
        row.profile='gym_walking';row.tdee=3250;row.expenditure_config={'version':1,'walkingCoefficient':.5};db.commit()
    assert c.get(old).json()['calculated']['selectedTDEE']==3250
    assert c.put(old+'/weight',json={'weightKg':90}).json()['calculated']['expenditureMethod']=='mifflin_st_jeor'
    assert p.calls==0

def test_workout_calories_require_duration_and_use_net_met(setup):
    c,p,_=setup
    assert c.post(DAY+'/activities',json={'type':'legs','exerciseCount':6}).status_code==422
    log=c.post(DAY+'/activities',json={'type':'legs','exerciseCount':6,'durationMinutes':30}).json()
    assert log['calculated']['exerciseCaloriesEstimate']==125.34
    assert log['calculated']['totalExpenditureKcal']==2409.84
    assert not log['calculated']['expenditureEstimateIncomplete']
    assert p.calls==0

def register(c,email='female@example.com',gender='female'):
    response=c.post('/api/auth/signup',json={'email':email,'password':'correct-horse-battery','gender':gender,'age':30,'heightCm':175,'weightKg':95.5})
    assert response.status_code==201,response.text
    c.headers['X-CSRF-Token']=response.json()['csrfToken']
    return response.json()

def test_signup_formula_login_and_revocable_sessions(setup):
    c,p,session=setup
    result=register(c)
    assert 'password' not in str(result)
    log=c.get(DAY).json()
    assert log['weightKg']==95.5
    assert log['calculated']['restingExpenditureKcal']==1737.75
    assert log['calculated']['selectedTDEE']==2085.3
    assert c.put(DAY+'/weight',json={'weightKg':90}).json()['calculated']['selectedTDEE']==2019.3
    old_token=c.cookies.get(auth.COOKIE)
    assert c.post('/api/auth/logout').status_code==200
    assert c.get(DAY).status_code==401
    c.cookies.set(auth.COOKIE,old_token,domain='testserver.local')
    assert c.get(DAY).status_code==401
    assert c.post('/api/auth/login',json={'email':'female@example.com','password':'wrong-password'}).status_code==401
    response=c.post('/api/auth/login',json={'email':'FEMALE@example.com','password':'correct-horse-battery'})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    assert c.get(DAY).json()['weightKg']==90
    with session() as db:
        user=db.scalar(select(User).where(User.email=='female@example.com'))
        assert user.password_hash!='correct-horse-battery'
    assert p.calls==0

def test_accounts_cannot_read_or_modify_each_others_data(setup):
    c,p,_=setup
    owner=c.post('/api/foods',json={'name':'Private food','baseQuantity':1,'baseUnit':'serving','calories':100,'proteinG':20}).json()
    log=c.post(DAY+'/foods',json={'foodPresetId':owner['id'],'quantity':1,'unit':'serving'}).json()
    entry=log['food'][0]['id']
    c.post(DAY+'/analyze',json={})
    owner_hash=c.get(DAY).json()['snapshotHash']
    register(c)
    assert c.get(DAY).json()['food']==[]
    assert c.get(DAY).json()['analysis'] is None
    assert c.get(DAY+'/analysis').json()==[]
    assert c.get(DAY).json()['snapshotHash']!=owner_hash
    assert not any(f['id']==owner['id'] for f in c.get('/api/foods').json())
    assert c.patch('/api/foods/'+owner['id'],json={'calories':1}).status_code==404
    assert c.delete('/api/foods/'+owner['id']).status_code==404
    assert c.post(DAY+'/foods',json={'foodPresetId':owner['id'],'quantity':1,'unit':'serving'}).status_code==404
    assert c.delete(DAY+'/foods/'+entry).status_code==404
    assert c.get('/api/history?from=2026-10-07&to=2026-10-07').json()['days'][0]['totalCalories']==0
    s=c.get('/api/settings').json();s['proteinMinG']=100
    c.put('/api/settings',json=s)
    c.post('/api/auth/logout')
    response=c.post('/api/auth/login',json={'email':'test@example.com','password':'test-password'})
    c.headers['X-CSRF-Token']=response.json()['csrfToken']
    assert c.get('/api/settings').json()['proteinMinG']==150
    assert c.get(DAY).json()['calculated']['totalCalories']==100

def test_csrf_expiration_validation_and_profile_history(setup):
    c,p,session=setup
    c.headers.pop('X-CSRF-Token')
    assert c.put(DAY+'/weight',json={'weightKg':90}).status_code==403
    c.headers['X-CSRF-Token']='test-csrf'
    old='/api/logs/2020-01-01'
    before=c.get(old).json()['calculated']
    c.get('/api/today')
    response=c.put('/api/auth/profile',json={'gender':'female','age':35,'heightCm':170,'weightKg':70})
    assert response.status_code==200
    assert c.get(old).json()['calculated']==before
    today=c.get('/api/today').json()
    assert today['expenditureConfig']['gender']=='female'
    assert today['expenditureConfig']['age']==35
    assert today['weightKg']==70
    assert today['calculated']['restingExpenditureKcal']==1426.5
    assert c.post('/api/auth/signup',json={'email':'bad','password':'short','gender':'other','age':17,'weightKg':0,'heightCm':0}).status_code==422
    from datetime import datetime,timedelta,timezone
    with session() as db:
        row=db.get(AuthSession,auth.digest('test-session'));row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert c.get('/api/settings').status_code==401
    assert p.calls==0

def test_duplicate_signup_secure_production_cookie_and_rate_limit(setup,monkeypatch):
    c,p,_=setup;monkeypatch.setenv('APP_ENV','production')
    response=c.post('/api/auth/signup',json={'email':'new@example.com','password':'long-enough-password','gender':'male','age':30,'weightKg':70,'heightCm':175})
    assert response.status_code==201 and 'Secure' in response.headers['set-cookie']
    assert c.post('/api/auth/signup',json={'email':'new@example.com','password':'different-password','gender':'female','age':30,'weightKg':70,'heightCm':175}).status_code==409
    for _ in range(18):
        assert c.post('/api/auth/login',json={'email':'absent@example.com','password':'incorrect-password'}).status_code==401
    assert c.post('/api/auth/login',json={'email':'absent@example.com','password':'incorrect-password'}).status_code==429


def test_administrator_legacy_transfer_requires_empty_destination(setup):
    c,p,session=setup
    from app.claim_legacy import claim
    c.post(DAY+'/foods',json={'foodPresetId':'whey','quantity':1,'unit':'scoop'})
    c.post(DAY+'/analyze',json={})
    register(c)
    c.get(DAY)
    with session() as db:
        assert claim(db,'female@example.com')==1
    migrated=c.get(DAY).json()
    assert migrated['food'][0]['displayName']=='Biozyme Whey'
    assert migrated['analysis']['snapshot']['userId']=='personal'
    assert c.patch('/api/foods/whey',json={'proteinG':26}).status_code==200
    with session() as db:
        with pytest.raises(ValueError,match='already has journal entries'):claim(db,'female@example.com')
