"""Password hashing and opaque, revocable cookie sessions; no browser token storage."""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import Field, field_validator
from typing import Literal
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from .database import Session
from .models import User, AuthSession, DailyLog
from .schemas import StrictModel
from .seed import seed_user

router=APIRouter(prefix='/api/auth')
COOKIE='fitlog_session'
class Profile(StrictModel):
    gender: Literal['male','female']
    age: int = Field(ge=18,le=100)
    heightCm: float = Field(ge=100,le=250)
    weightKg: float = Field(ge=20,le=350)
class Credentials(StrictModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=10,max_length=128)
    @field_validator('email')
    @classmethod
    def email_format(cls,v):
        v=v.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v): raise ValueError('Enter a valid email')
        return v
class Signup(Credentials,Profile): pass

def raw_session():
    with Session() as db: yield db

def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def hash_password(password):
    salt=secrets.token_bytes(16)
    return salt.hex()+':'+hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()
def verify_password(password,stored):
    salt,key=stored.split(':')
    return hmac.compare_digest(hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex(),key)
DUMMY=hash_password('dummy-password-for-timing')

def authenticate(request,db):
    row=db.get(AuthSession,digest(request.cookies.get(COOKIE,'')))
    if not row or row.expires_at.replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc):
        raise HTTPException(401,'Please log in to continue')
    if request.method not in ('GET','HEAD','OPTIONS') and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),row.csrf):
        raise HTTPException(403,'Session verification failed. Refresh and try again.')
    user=db.get(User,row.user_id)
    if not user: raise HTTPException(401,'Please log in to continue')
    db.info['user_id']=user.id
    db.info['user']=user
    return user,row

def public_user(user): return {'id':user.id,'email':user.email,**user.profile}
def issue(user,db,response):
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
    db.execute(delete(AuthSession).where(AuthSession.expires_at<datetime.now(timezone.utc)))
    db.add(AuthSession(token_hash=digest(token),user_id=user.id,csrf=csrf,expires_at=datetime.now(timezone.utc)+timedelta(days=7)))
    db.commit()
    response.set_cookie(COOKIE,token,httponly=True,secure=os.getenv('APP_ENV')=='production' or bool(os.getenv('RAILWAY_ENVIRONMENT')),samesite='lax',max_age=604800,path='/')
    response.headers['Cache-Control']='no-store'
    return {'user':public_user(user),'csrfToken':csrf}

# Limit password work per client in this single-worker deployment.
_attempts={};_lock=threading.Lock()
def limit(request):
    key=request.client.host if request.client else 'unknown';now=time.monotonic()
    with _lock:
        for k in list(_attempts):
            if now-_attempts[k][0]>900: del _attempts[k]
        start,count=_attempts.get(key,(now,0))
        if count>=20: raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')
        _attempts[key]=(start,count+1)

def json_only(request):
    if request.headers.get('content-type','').split(';')[0]!='application/json': raise HTTPException(415,'Use application/json')

@router.post('/signup',status_code=201)
def signup(body:Signup,request:Request,response:Response,db=Depends(raw_session)):
    json_only(request);limit(request)
    user=User(id=str(uuid4()),email=body.email,password_hash=hash_password(body.password),profile=Profile.model_validate({k:getattr(body,k) for k in Profile.model_fields}).model_dump())
    try:
        db.add(user);db.flush();seed_user(db,user.id);db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Unable to create this account. Try logging in instead.')
    return issue(user,db,response)

@router.post('/login')
def login(body:Credentials,request:Request,response:Response,db=Depends(raw_session)):
    json_only(request);limit(request)
    user=db.scalar(select(User).where(User.email==body.email))
    valid=verify_password(body.password,user.password_hash if user else DUMMY)
    if not user or not valid: raise HTTPException(401,'Email or password is incorrect')
    return issue(user,db,response)

@router.get('/me')
def me(request:Request,response:Response,db=Depends(raw_session)):
    user,row=authenticate(request,db);response.headers['Cache-Control']='no-store'
    return {'user':public_user(user),'csrfToken':row.csrf}

@router.post('/logout')
def logout(request:Request,response:Response,db=Depends(raw_session)):
    _,row=authenticate(request,db);db.delete(row);db.commit();response.delete_cookie(COOKIE,path='/')
    return {'ok':True}

@router.put('/profile')
def profile(body:Profile,request:Request,db=Depends(raw_session)):
    user,_=authenticate(request,db)
    changed_weight=body.weightKg!=user.profile['weightKg']
    user.profile=body.model_dump()
    # Snapshot new profile inputs on today's/future logs; past inputs stay unchanged.
    from .main import expenditure_config
    from .models import UserSettings
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo(os.getenv('APP_TIMEZONE','Asia/Kolkata'))).date().isoformat()
    from .schemas import Settings
    settings=Settings.model_validate(db.get(UserSettings,user.id).data).model_dump()
    for log in db.scalars(select(DailyLog).where(DailyLog.user_id==user.id,DailyLog.date>=today)):
        log.expenditure_config=expenditure_config(settings,user.profile)
        if changed_weight and log.date==today: log.weight_kg=body.weightKg
    db.commit();return public_user(user)
