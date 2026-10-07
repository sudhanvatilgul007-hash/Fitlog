import os
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .database import Session
from .models import UserSettings, FoodPreset, DailyLog, FoodEntry, ActivityEntry, DailyAnalysis
from .schemas import Settings, Food, FoodAdd, FoodEdit, Weight, TDEE, Activity, Analyze, AnalysisResponse
from .calculations import snapshot, snapshot_hash, averages, food_totals
from .provider import get_provider

app = FastAPI(title='fitlog')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173').split(','),allow_methods=['*'],allow_headers=['*'])
def session():
    with Session() as db:
        yield db

def settings(db):
    row=db.get(UserSettings,'personal')
    if not row:
        raise HTTPException(503,'Run migrations and seed first')
    return Settings.model_validate(row.data).model_dump()

def expenditure_config(s):
    return {'version':2,'referenceWeightKg':s['tdeeReferenceWeightKg'],'walkingCoefficient':s['walkingCoefficient']}

def get_log(db, day):
    log=db.scalar(select(DailyLog).where(DailyLog.date==day.isoformat(),DailyLog.user_id=='personal'))
    if not log:
        previous=db.scalar(select(DailyLog).where(DailyLog.date<day.isoformat()).order_by(DailyLog.date.desc()))
        s=settings(db)
        log=DailyLog(id=str(uuid4()),date=day.isoformat(),weight_kg=previous.weight_kg if previous else 95.5,profile='automatic',tdee=s['tdeeProfiles']['sedentary'],expenditure_config=expenditure_config(s))
        db.add(log)
        try: db.commit()
        except IntegrityError:
            db.rollback()
            log=db.scalar(select(DailyLog).where(DailyLog.date==day.isoformat(),DailyLog.user_id=='personal'))
    today=datetime.now(ZoneInfo(os.getenv('APP_TIMEZONE','Asia/Kolkata'))).date()
    if day>=today and (not log.expenditure_config or log.expenditure_config.get('version')==1):
        s=settings(db);log.expenditure_config=expenditure_config(s)
        if log.profile!='custom':log.profile='automatic';log.tdee=s['tdeeProfiles']['sedentary']
        db.commit()
    return log

def normalized(db, log):
    foods=[{'id':r.id,**r.data} for r in db.scalars(select(FoodEntry).where(FoodEntry.log_id==log.id))]
    activity=[{'id':r.id,**r.data} for r in db.scalars(select(ActivityEntry).where(ActivityEntry.log_id==log.id))]
    return snapshot(log,foods,activity,settings(db))

def analysis_data(row, current_hash):
    return {'id':row.id,'snapshotHash':row.snapshot_hash,'snapshot':row.snapshot,'response':row.response,'provider':row.provider,'model':row.model,'promptVersion':row.prompt_version,'createdAt':row.created_at.isoformat(),'stale':row.snapshot_hash!=current_hash}

def log_data(db,log):
    snap=normalized(db,log)
    latest=db.scalar(select(DailyAnalysis).where(DailyAnalysis.log_id==log.id,DailyAnalysis.status=='complete').order_by(DailyAnalysis.created_at.desc()))
    attempt=db.scalar(select(DailyAnalysis).where(DailyAnalysis.snapshot_hash==snapshot_hash(snap)))
    return {**snap,'analysisAttempt':attempt.status if attempt else None,'id':log.id,'snapshotHash':snapshot_hash(snap),'analysis':analysis_data(latest,snapshot_hash(snap)) if latest else None}

def owned_entry(db,cls,id,log):
    row=db.get(cls,id)
    if not row or row.log_id!=log.id: raise HTTPException(404,'Entry not found')
    return row

@app.get('/api/health')
def health(): return {'status':'ok','app':'fitlog'}
@app.get('/api/today')
def today(db=Depends(session)):
    day=datetime.now(ZoneInfo(os.getenv('APP_TIMEZONE','Asia/Kolkata'))).date()
    return log_data(db,get_log(db,day))
@app.get('/api/logs/{day}')
def read_log(day:date,db=Depends(session)): return log_data(db,get_log(db,day))
@app.put('/api/logs/{day}/weight')
def weight(day:date,body:Weight,db=Depends(session)):
    s=settings(db)
    if not s['weightMinKg']<=body.weightKg<=s['weightMaxKg']: raise HTTPException(422,'Weight outside configured range')
    log=get_log(db,day); log.weight_kg=body.weightKg
    if not log.expenditure_config or log.expenditure_config.get('version')==1:
        log.expenditure_config=expenditure_config(s)
        if log.profile!='custom':log.profile='automatic';log.tdee=s['tdeeProfiles']['sedentary']
    db.commit()
    return log_data(db,log)
@app.put('/api/logs/{day}/tdee')
def tdee(day:date,body:TDEE,db=Depends(session)):
    profiles=settings(db)['tdeeProfiles']
    if body.profile not in profiles and body.profile not in ('custom','automatic'): raise HTTPException(422,'Unknown TDEE profile')
    value=body.kcal if body.kcal is not None else profiles.get('sedentary' if body.profile=='automatic' else body.profile)
    if value is None: raise HTTPException(422,'Custom TDEE requires kcal')
    log=get_log(db,day);log.profile=body.profile;log.tdee=value;log.expenditure_config=expenditure_config(settings(db));db.commit()
    return log_data(db,log)
@app.get('/api/foods')
def foods(favorite:bool|None=None,db=Depends(session)):
    entries=list(db.scalars(select(FoodEntry)))
    usage={}
    for e in entries:
        id=e.data['foodPresetId']; usage[id]=usage.get(id,0)+1
    rows=[{'id':r.id,**r.data,'usageCount':usage.get(r.id,0)} for r in db.scalars(select(FoodPreset)) if r.data['active'] and (favorite is None or r.data['favorite']==favorite)]
    # Recent order uses daily log date plus entry insertion order below.
    for r in rows:
        matches=[e for e in entries if e.data['foodPresetId']==r['id']]
        r['lastUsed']=max((e.data.get('addedAt','') for e in matches),default='')
    return sorted(rows,key=lambda r:(-r['usageCount'],r['sortOrder'],r['name']))
@app.post('/api/foods',status_code=201)
def create_food(body:Food,db=Depends(session)):
    row=FoodPreset(id=str(uuid4()),data=body.model_dump());db.add(row);db.commit()
    return {'id':row.id,**row.data}
@app.patch('/api/foods/{id}')
def edit_food(id:str,body:dict,db=Depends(session)):
    row=db.get(FoodPreset,id)
    if not row: raise HTTPException(404,'Food not found')
    try: row.data=Food.model_validate({**row.data,**body}).model_dump()
    except ValueError as exc: raise HTTPException(422,'Invalid food values') from exc
    db.commit();return {'id':row.id,**row.data}
@app.delete('/api/foods/{id}')
def delete_food(id:str,db=Depends(session)):
    row=db.get(FoodPreset,id)
    if not row: raise HTTPException(404,'Food not found')
    row.data={**row.data,'active':False};db.commit();return {'ok':True}
@app.post('/api/logs/{day}/foods',status_code=201)
def add_food(day:date,body:FoodAdd,db=Depends(session)):
    log=get_log(db,day); preset=db.get(FoodPreset,body.foodPresetId)
    if not preset or not preset.data['active']:raise HTTPException(404,'Food not found')
    if body.unit!=preset.data['baseUnit']:raise HTTPException(422,'Use the preset unit; create a separate preset for a different unit')
    entry=FoodEntry(id=str(uuid4()),log_id=log.id,data={'foodPresetId':preset.id,'displayName':preset.data['name'],'quantity':body.quantity,'unit':body.unit,'nutrition':preset.data.copy(),'addedAt':datetime.now().isoformat()})
    db.add(entry);db.commit();return log_data(db,log)
@app.patch('/api/logs/{day}/foods/{id}')
def edit_entry(day:date,id:str,body:FoodEdit,db=Depends(session)):
    log=get_log(db,day);entry=owned_entry(db,FoodEntry,id,log)
    if body.unit!=entry.data['unit']:raise HTTPException(422,'Use the original unit')
    entry.data={**entry.data,**body.model_dump()};db.commit();return log_data(db,log)
@app.delete('/api/logs/{day}/foods/{id}')
def remove_food(day:date,id:str,db=Depends(session)):
    log=get_log(db,day);db.delete(owned_entry(db,FoodEntry,id,log));db.commit();return log_data(db,log)
@app.post('/api/logs/{day}/activities',status_code=201)
def add_activity(day:date,body:Activity,db=Depends(session)):
    log=get_log(db,day);db.add(ActivityEntry(id=str(uuid4()),log_id=log.id,data=body.model_dump()));db.commit();return log_data(db,log)
@app.patch('/api/logs/{day}/activities/{id}')
def edit_activity(day:date,id:str,body:Activity,db=Depends(session)):
    log=get_log(db,day);row=owned_entry(db,ActivityEntry,id,log);row.data=body.model_dump();db.commit();return log_data(db,log)
@app.delete('/api/logs/{day}/activities/{id}')
def remove_activity(day:date,id:str,db=Depends(session)):
    log=get_log(db,day);db.delete(owned_entry(db,ActivityEntry,id,log));db.commit();return log_data(db,log)
@app.get('/api/settings')
def read_settings(db=Depends(session)):return settings(db)
@app.put('/api/settings')
def put_settings(body:Settings,db=Depends(session)):
    row=db.get(UserSettings,'personal');row.data=body.model_dump()
    today=datetime.now(ZoneInfo(os.getenv('APP_TIMEZONE','Asia/Kolkata'))).date().isoformat()
    for log in db.scalars(select(DailyLog).where(DailyLog.date>=today)):
        log.expenditure_config=expenditure_config(row.data)
        if log.profile!='custom':log.tdee=row.data['tdeeProfiles'].get('sedentary' if log.profile=='automatic' else log.profile,log.tdee)
    db.commit();return row.data
@app.get('/api/logs/{day}/analysis')
def stored_analysis(day:date,db=Depends(session)):
    log=get_log(db,day);current=snapshot_hash(normalized(db,log))
    rows=list(db.scalars(select(DailyAnalysis).where(DailyAnalysis.log_id==log.id,DailyAnalysis.status=='complete').order_by(DailyAnalysis.created_at.desc())))
    return [analysis_data(row,current) for row in rows]
@app.post('/api/logs/{day}/analyze')
def analyze(day:date,body:Analyze,db=Depends(session)):
    log=get_log(db,day);snap=normalized(db,log);hash=snapshot_hash(snap)
    row=db.scalar(select(DailyAnalysis).where(DailyAnalysis.snapshot_hash==hash))
    if row and row.status=='complete':return analysis_data(row,hash)
    if row and row.status=='pending':raise HTTPException(409,'Analysis is in progress. Reopen stored analysis shortly; no extra call was made.')
    previous=db.scalar(select(DailyAnalysis).where(DailyAnalysis.log_id==log.id,DailyAnalysis.status=='complete'))
    if previous and not body.confirmReanalysis:raise HTTPException(409,'Re-analysis requires confirmation; it makes a new paid request')
    provider=get_provider()
    if row:
        if not body.retry:raise HTTPException(409,'Previous request failed. Use explicit retry.')
        claim=db.execute(update(DailyAnalysis).where(DailyAnalysis.id==row.id,DailyAnalysis.status=='failed').values(status='pending',provider=provider.name,model=provider.model))
        db.commit()
        if claim.rowcount!=1:raise HTTPException(409,'Analysis already in progress')
        db.refresh(row)
    else:
        row=DailyAnalysis(id=str(uuid4()),log_id=log.id,snapshot_hash=hash,snapshot=snap,provider=provider.name,model=provider.model,status='pending')
        db.add(row)
        try:db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Analysis already in progress; no additional provider request')
    try:
        row.response=AnalysisResponse.model_validate(provider.analyze(snap)).model_dump()
        row.status='complete';db.commit()
    except Exception:
        db.rollback();db.refresh(row);row.status='failed';db.commit()
        raise HTTPException(502,'Analysis failed or returned invalid JSON. Your log is saved. Check server provider configuration and explicitly retry.')
    db.refresh(log)
    return analysis_data(row,snapshot_hash(normalized(db,log)))
@app.get('/api/history')
def history(from_:date|None=Query(None,alias='from'),to:date|None=None,db=Depends(session)):
    end=to or datetime.now(ZoneInfo(os.getenv('APP_TIMEZONE','Asia/Kolkata'))).date()
    start=from_ or end-timedelta(days=29)
    if start>end:raise HTTPException(422,'Start date must precede end date')
    days=[]
    for log in db.scalars(select(DailyLog).where(DailyLog.date>=start.isoformat(),DailyLog.date<=end.isoformat()).order_by(DailyLog.date)):
        data=normalized(db,log);days.append({'date':log.date,'weightKg':log.weight_kg,**data['calculated']})
    last7=[d for d in days if d['date']>=(end-timedelta(days=6)).isoformat()]
    last30=[d for d in days if d['date']>=(end-timedelta(days=29)).isoformat()]
    return {'days':days,'averages':averages(days),'sevenDay':averages(last7),'thirtyDay':averages(last30),'proteinAdherence':{'meeting':sum(d['totalProteinG']>=settings(db)['proteinMinG'] for d in days),'total':len(days)}}

# Keep this last so API/documentation routes take priority over static files.
from .frontend import mount_frontend
mount_frontend(app)
