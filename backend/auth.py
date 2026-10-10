"""Optional single-operator session gate for cloud deployments."""
import hashlib
import hmac
import os
import secrets
import time
from collections import deque

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()
COOKIE = 'wildfirewatch_session'
TTL = 8 * 3600
attempts = deque()


def enabled():return bool(os.environ.get('OPERATOR_PASSWORD'))


def signature(value):
    return hmac.new(os.environ.get('OPERATOR_PASSWORD','').encode(),value.encode(),hashlib.sha256).hexdigest()


def authorized(cookies):
    if not enabled():return True
    try:
        value,mac=cookies.get(COOKIE,'').rsplit('.',1)
        expires=int(value.split('.')[0])
        return time.time()<expires<=time.time()+TTL+60 and hmac.compare_digest(signature(value),mac)
    except (ValueError,TypeError):return False


@router.get('/api/auth/status')
async def status(request:Request):return {'required':enabled(),'authenticated':authorized(request.cookies)}


class Login(BaseModel):
    password:str=Field(max_length=256)


@router.post('/api/auth/login')
async def login(data:Login):
    now=time.monotonic()
    while attempts and now-attempts[0]>60:attempts.popleft()
    if len(attempts)>=10:raise HTTPException(429,'Too many login attempts. Wait one minute.')
    if not enabled():return {'authenticated':True}
    attempts.append(now)
    if not secrets.compare_digest(hashlib.sha256(data.password.encode()).digest(),
            hashlib.sha256(os.environ['OPERATOR_PASSWORD'].encode()).digest()):
        raise HTTPException(401,'Incorrect operator password')
    value=f'{int(time.time())+TTL}.{secrets.token_urlsafe(24)}'
    response=JSONResponse({'authenticated':True})
    response.set_cookie(COOKIE,value+'.'+signature(value),max_age=TTL,httponly=True,
        secure=os.environ.get('SESSION_COOKIE_SECURE','true').lower()!='false',samesite='lax')
    response.headers['Cache-Control']='no-store'
    return response


@router.post('/api/auth/logout')
async def logout():
    response=JSONResponse({'authenticated':False});response.delete_cookie(COOKIE)
    return response
