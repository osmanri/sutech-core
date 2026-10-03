"""Daily dashboard authentication, live balances and irrigation journal safety."""
import asyncio
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

from aiohttp import web
from bot import db,field_service
from bot.field_state import (get_field,list_daily_balances,list_irrigation_events,
                             make_field_key,upsert_managed_field)
from bot.webapp_fields import fields_today,water_field
import test_bot_platform as platform_tests


class WebappFieldsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patches=[patch.object(db,'DB_PATH',str(Path(self.temp.name)/'fields.db')),
                      patch.object(db,'DATABASE_URL',''),patch.dict('os.environ',{'DATABASE_URL':''})]
        for p in self.patches:p.start()
        db.init_db()
        self.weather=patch.object(field_service,'fetch_daily_weather',new=AsyncMock(return_value={
            'date':date.today().isoformat(),'timezone':'Asia/Qyzylorda','et0':4.,'rain':0.}))
        self.weather.start()
        self.field=self.create(10)
        self.other=self.create(11)

    def tearDown(self):
        self.weather.stop()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def create(self,user_id,deficit=20,day=30):
        return upsert_managed_field(user_id=user_id,field_key=make_field_key(44.85,65.5,.1,'tomato'),
            crop='tomato',soil='loam',irrigation='drip',planting_date=date.today()-timedelta(days=day),
            initial_deficit=deficit,latitude=44.85,longitude=65.5,area_ha=.1)[0]

    def request(self,user=10,**body):
        raw=json.dumps({'init_data':platform_tests.BotPlatformTests.signed_init_data(user),**body}).encode()
        return SimpleNamespace(content=SimpleNamespace(read=AsyncMock(return_value=raw)))

    async def card(self):
        response=await fields_today(self.request())
        return json.loads(response.text)['fields'][0]

    async def test_only_signed_owner_fields_are_returned_and_not_cached(self):
        response=await fields_today(self.request(user_id=11))
        body=json.loads(response.text)
        self.assertEqual([c['id'] for c in body['fields']],[self.field])
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn(body['fields'][0]['status'],('irrigate','critical'))
        self.assertGreater(body['fields'][0]['volume_m3'],0)
        self.assertEqual(body['fields'][0]['date'],date.today().isoformat())

    async def test_empty_new_user_and_low_deficit(self):
        response=await fields_today(self.request(user=200))
        self.assertEqual(json.loads(response.text)['fields'],[])
        self.create(12,deficit=0)
        response=await fields_today(self.request(user=12))
        card=json.loads(response.text)['fields'][0]
        self.assertEqual(card['status'],'deferred');self.assertEqual(card['volume_m3'],0)

    async def test_refresh_does_not_apply_daily_evaporation_twice(self):
        first=await self.card();second=await self.card()
        self.assertEqual(first['deficit'],second['deficit'])
        self.assertEqual(len(list_daily_balances(self.field,user_id=10)),1)

    async def test_confirmed_full_irrigation_updates_site_and_keeps_daily_audit(self):
        card=await self.card()
        response=await water_field(self.request(field_id=self.field,applied_m3=card['volume_m3'],expected_deficit=card['deficit']))
        updated=json.loads(response.text)['field']
        self.assertAlmostEqual(updated['deficit'],0,places=6)
        self.assertEqual(updated['status'],'deferred')
        self.assertEqual(updated['volume_m3'],0)
        self.assertEqual((await self.card())['status'],'deferred')
        self.assertEqual(len(list_daily_balances(self.field,user_id=10)),1)
        self.assertEqual(len(list_irrigation_events(self.field,user_id=10)),1)

    async def test_partial_water_reduces_deficit_by_method_efficiency(self):
        card=await self.card()
        response=await water_field(self.request(field_id=self.field,applied_m3=1.,expected_deficit=card['deficit']))
        updated=json.loads(response.text)['field']
        self.assertAlmostEqual(updated['deficit'],card['deficit']-.9)
        event=list_irrigation_events(self.field,user_id=10)[0]
        self.assertEqual(event['source'],'web_mini_app');self.assertEqual(event['applied_m3'],1)

    async def test_concurrent_double_click_records_only_once(self):
        card=await self.card()
        kwargs={'field_id':self.field,'applied_m3':1.,'expected_deficit':card['deficit']}
        responses=await asyncio.gather(water_field(self.request(**kwargs)),water_field(self.request(**kwargs)))
        self.assertEqual(sorted(r.status for r in responses),[200,409])
        self.assertEqual(len(list_irrigation_events(self.field,user_id=10)),1)

    async def test_cross_user_write_is_rejected(self):
        before=get_field(self.other,user_id=11)['accumulated_deficit']
        with self.assertRaises(web.HTTPNotFound):
            await water_field(self.request(field_id=self.other,applied_m3=1.,expected_deficit=before))
        self.assertEqual(get_field(self.other,user_id=11)['accumulated_deficit'],before)

    async def test_invalid_auth_and_expired_session_never_load_fields(self):
        for init in ('invalid',platform_tests.BotPlatformTests.signed_init_data(age_seconds=90000),platform_tests.BotPlatformTests.signed_init_data(age_seconds=-600)):
            with self.assertRaises(web.HTTPUnauthorized):
                await fields_today(self.request(init_data=init))

    async def test_invalid_volumes_and_ids_never_write(self):
        for data in ({'field_id':True,'applied_m3':1.,'expected_deficit':20.},
                     {'field_id':self.field,'applied_m3':-1.,'expected_deficit':20.},
                     {'field_id':self.field,'applied_m3':True,'expected_deficit':20.},
                     {'field_id':self.field,'applied_m3':float('nan'),'expected_deficit':20.},
                     {'field_id':self.field,'applied_m3':1.,'expected_deficit':0.}):
            with self.assertRaises(web.HTTPBadRequest):await water_field(self.request(**data))
        self.assertEqual(list_irrigation_events(self.field,user_id=10),[])

    async def test_weather_failure_does_not_show_stale_water_button(self):
        with patch.object(field_service,'fetch_daily_weather',side_effect=ConnectionError):
            card=await self.card()
        self.assertEqual(card['status'],'unavailable')
        self.assertNotIn('volume_m3',card)

    async def test_expired_crop_season_is_explicit(self):
        self.create(13,day=400)
        response=await fields_today(self.request(user=13))
        self.assertEqual(json.loads(response.text)['fields'][0]['status'],'season_ended')

    async def test_dashboard_cors_preflight_and_disallowed_origin(self):
        from bot.main import webapp_cors
        response=await webapp_cors(SimpleNamespace(path='/api/fields/today',method='OPTIONS',
            headers={'Origin':'https://frontend-2-mauve.vercel.app'}),AsyncMock())
        self.assertEqual(response.status,204)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'],'https://frontend-2-mauve.vercel.app')
        with self.assertRaises(web.HTTPForbidden):
            await webapp_cors(SimpleNamespace(path='/api/fields/water',method='POST',headers={'Origin':'https://bad.example'}),AsyncMock())
