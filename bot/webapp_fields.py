"""Owner-scoped daily field cards for the Telegram Mini App."""
import asyncio
import json
import logging
import math
import time
from datetime import timezone

from aiohttp import web
from aiogram.utils.web_app import safe_parse_webapp_init_data

from bot.config import BOT_TOKEN
from bot.field_service import calculate_saved_field
from bot.field_state import (FieldNotFoundError, IrrigationConflictError,
                             get_field, list_user_fields, record_irrigation)
from bot.water_balance import METHODS, BalanceInputError

logger=logging.getLogger(__name__)


async def authenticated_body(request):
    raw = await request.content.read(8193)
    if len(raw) > 8192:
        raise web.HTTPRequestEntityTooLarge(max_size=8192,actual_size=len(raw))
    try:
        body = json.loads(raw)
    except (ValueError,UnicodeDecodeError):
        raise web.HTTPBadRequest() from None
    if not isinstance(body,dict):
        raise web.HTTPBadRequest()
    init_data = body.get('init_data')
    if not isinstance(init_data,str) or not init_data or len(init_data)>4096:
        raise web.HTTPUnauthorized()
    try:
        auth=safe_parse_webapp_init_data(BOT_TOKEN,init_data)
    except (ValueError,TypeError):
        raise web.HTTPUnauthorized() from None
    stamp=auth.auth_date
    if stamp.tzinfo is None:
        stamp=stamp.replace(tzinfo=timezone.utc)
    age=time.time()-stamp.timestamp()
    if auth.user is None or auth.user.id<=0 or age < -300 or age>86400:
        raise web.HTTPUnauthorized()
    return auth.user.id,body


async def field_card(record,user_id):
    """Keep journal snapshots intact; show the live deficit after watering."""
    card={'id':int(record['id']),'name':record.get('name') or '',
          'crop':record['crop_type'],'area_ha':float(record.get('area_ha') or 0)}
    try:
        _,result,weather,_=await calculate_saved_field(card['id'],user_id)
        live=await asyncio.to_thread(get_field,card['id'],user_id=user_id)
        deficit=float(live['accumulated_deficit'])
        raw,threshold=float(result['raw']),float(result['threshold'])
        critical=deficit>raw and not math.isclose(deficit,raw,abs_tol=1e-9,rel_tol=0)
        due=deficit>=threshold or math.isclose(deficit,threshold,abs_tol=1e-9,rel_tol=0)
        status='critical' if critical else 'irrigate' if due else 'deferred'
        volume=deficit*10*card['area_ha']/METHODS[live['irrigation_method']][1] if status!='deferred' else 0.
        card.update(status=status,date=weather['date'],timezone=weather['timezone'],
                    deficit=deficit,raw=raw,threshold=threshold,volume_m3=volume,
                    rain_mm=float(result['rain']),etc_mm=float(result['etc']))
    except BalanceInputError as exc:
        card.update(status='season_ended' if str(exc)=='season_ended' else 'unavailable')
    except FieldNotFoundError:
        card.update(status='unavailable')
    except Exception as exc:
        # No stale snapshot is presented as a fresh recommendation.
        logger.warning('Daily field card unavailable (%s)',type(exc).__name__)
        card.update(status='unavailable')
    return card


def private_json(body,status=200):
    return web.json_response(body,status=status,headers={'Cache-Control':'no-store'})


async def fields_today(request):
    user_id,_=await authenticated_body(request)
    records=await asyncio.to_thread(list_user_fields,user_id)
    semaphore=asyncio.Semaphore(4)
    async def load(record):
        async with semaphore:
            return await field_card(record,user_id)
    cards=await asyncio.gather(*(load(record) for record in records))
    cards.sort(key=lambda c:({'critical':0,'irrigate':1,'deferred':2}.get(c['status'],3),c['id']))
    return private_json({'ok':True,'fields':cards})


async def water_field(request):
    user_id,body=await authenticated_body(request)
    field_id=body.get('field_id')
    volume,expected=body.get('applied_m3'),body.get('expected_deficit')
    if (type(field_id) is not int or field_id<=0 or
        type(volume) not in (int,float) or not math.isfinite(volume) or not 0<volume<=1e9 or
        type(expected) not in (int,float) or not math.isfinite(expected) or expected<=0):
        raise web.HTTPBadRequest()
    try:
        await asyncio.to_thread(record_irrigation,field_id,user_id=user_id,applied_m3=volume,
                                expected_deficit=expected,source='web_mini_app')
        record=await asyncio.to_thread(get_field,field_id,user_id=user_id)
    except FieldNotFoundError:
        raise web.HTTPNotFound() from None
    except IrrigationConflictError:
        return private_json({'ok':False,'error':'balance_changed'},409)
    return private_json({'ok':True,'field':await field_card(record,user_id)})
