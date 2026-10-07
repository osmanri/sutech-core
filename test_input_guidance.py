"""Field guidance must map to real model stages and keep estimated-age provenance."""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bot import db
from bot.balance_report import format_balance_report
from bot.field_guidance import STAGES, SOIL_HELP, stage_options, estimate_growth_day, growth_estimate_metadata
from bot.field_service import calculate_saved_field, persist_webapp_field
from bot.field_state import record_irrigation
from bot.services.field_manager import FieldService
from bot.water_balance import BalanceInputError, CROPS, parse_field, calculate_balance
from bot.handlers import chat_planner
from bot.i18n import t
from test_water_balance import payload
import test_project_assistant as planner_tests


class GuidanceModelTests(unittest.TestCase):
    def test_every_stage_maps_to_the_model_stage_in_default_and_short_calendars(self):
        for crop in CROPS:
            for calendar in (CROPS[crop][4], (1, 1, 1, 1), (10, 20, 40, 20)):
                for stage in STAGES:
                    day = estimate_growth_day(crop, stage, calendar)
                    field = parse_field(payload(crop=crop, day_of_growth=day, stage_days=calendar))
                    self.assertEqual(field.stage, stage, (crop, stage, calendar, day))
                    metadata = growth_estimate_metadata(
                        {'growth_day_source': 'stage', 'growth_stage': stage}, field)
                    self.assertTrue(metadata['age_estimated'])

    def test_rejects_unsupported_crops_invalid_calendars_and_mismatched_age(self):
        for crop, stage, calendar in [('rice','middle',None), ('other','initial',None),
                ('wheat','unknown',None), ('wheat','middle',[1,2,3]),
                ('wheat','middle',[0,20,30,10]), ('wheat','middle',[1,2,3.5,4]),
                ('wheat','middle',[True,2,3,4])]:
            with self.assertRaises(BalanceInputError):
                estimate_growth_day(crop, stage, calendar)
        field = parse_field(payload(day_of_growth=30))
        with self.assertRaises(BalanceInputError):
            growth_estimate_metadata({'growth_day_source':'stage','growth_stage':'middle'}, field)
        self.assertEqual(growth_estimate_metadata({}, field), {})

    def test_localized_help_has_crop_examples_and_alfalfa_first_cut(self):
        for lang in ('ru','kz','en'):
            self.assertTrue(SOIL_HELP[lang])
            for crop in CROPS:
                options = stage_options(crop, lang)
                self.assertEqual(len(options), 4)
                self.assertTrue(all(name and description for _, name, description in options))
                if lang == 'en':
                    self.assertFalse(any('\u0400' <= ch <= '\u04ff' for _, name, desc in options for ch in name+desc))
            self.assertIn({'ru':'первый укос','kz':'Алғашқы орым','en':'First cut'}[lang],
                          stage_options('alfalfa', lang)[-1][2])


class PlannerGuidanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.guidance_temp = tempfile.TemporaryDirectory()
        self.guidance_db_patches = [patch.object(db,'DB_PATH',str(Path(self.guidance_temp.name)/'planner.db')),
                                   patch.object(db,'DATABASE_URL',''), patch.dict('os.environ',{'DATABASE_URL':''})]
        for p in self.guidance_db_patches: p.start()
        db.init_db()
        await planner_tests.ChatPlannerTests.asyncSetUp(self)

    async def asyncTearDown(self):
        await planner_tests.ChatPlannerTests.asyncTearDown(self)
        for p in reversed(self.guidance_db_patches): p.stop()
        self.guidance_temp.cleanup()
    message = planner_tests.ChatPlannerTests.message
    transport = planner_tests.ChatPlannerTests.transport
    send = planner_tests.ChatPlannerTests.send
    choose = planner_tests.ChatPlannerTests.choose

    async def begin_at_age(self):
        await self.send('/plan'); await self.choose('wheat')
        await self.send('0.1'); await self.send('44.85 65.50')

    async def test_guidance_is_in_place_localized_and_uses_no_ai(self):
        for lang in ('ru','kz','en'):
            self.lang = lang
            await self.begin_at_age()
            await self.choose('help_growth')
            self.assertEqual((await self.state.get_data())['step'], 3)
            self.assertIn(chat_planner.phrase(lang,'stage_help'), self.sent[-1].text)
            self.assertEqual(type(self.sent[-1]).__name__, 'EditMessageText')
            await self.choose('back')
            self.assertEqual((await self.state.get_data())['step'], 3)
            await self.choose('help_growth'); await self.choose('stage_middle')
            values = (await self.state.get_data())['values']
            self.assertEqual(values['day_of_growth'], 75)
            self.assertEqual(values['growth_day_source'], 'stage')
            await self.choose('help_soil')
            self.assertEqual((await self.state.get_data())['step'], 4)
            self.assertIn(SOIL_HELP[lang], self.sent[-1].text)
            await self.choose('loam'); await self.choose('normal')
            await self.choose('drip'); await self.choose('open'); await self.choose('no')
            await self.choose('skip')
            self.assertIn(chat_planner.phrase(lang,'estimated').format(day=75), self.sent[-1].text)
            self.persist.reset_mock()
            await self.choose('calculate')
            self.assertTrue(self.persist.await_args.args[5]['age_estimated'])
            self.assertTrue(any(t(lang,'decision_age_estimated') in (getattr(m,'text',None) or '') for m in self.sent))
        self.service.reply.assert_not_awaited()

    async def test_exact_age_replaces_the_estimate_after_back_navigation(self):
        await self.begin_at_age()
        await self.choose('help_growth'); await self.choose('stage_middle')
        await self.choose('back'); await self.send('62')
        values = (await self.state.get_data())['values']
        self.assertEqual(values['day_of_growth'], 62)
        self.assertEqual(values['growth_day_source'], 'days')
        self.assertIsNone(values['growth_stage'])


class GuidancePersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(db, 'DB_PATH', str(Path(self.temp.name)/'guidance.db')),
                        patch.object(db, 'DATABASE_URL', ''), patch.dict('os.environ', {'DATABASE_URL':''})]
        for p in self.patches: p.start()
        db.init_db()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    async def test_estimation_survives_next_day_and_irrigation_then_exact_input_clears_it(self):
        user = 54917
        weather = {'date':date.today().isoformat(),'timezone':'Asia/Qyzylorda','et0':5,'rain':0}
        data = payload(day_of_growth=75, growth_day_source='stage', growth_stage='middle')
        field = parse_field(data)
        result = calculate_balance(field, 5, 0)
        result.update(growth_estimate_metadata(data,field))
        fid = await persist_webapp_field(user,data,field,44.85,65.49,result,weather)
        tomorrow = {**weather,'date':(date.today()+timedelta(days=1)).isoformat()}
        with patch('bot.field_service.fetch_daily_weather', AsyncMock(return_value=tomorrow)):
            f, updated, forecast, _ = await calculate_saved_field(fid,user)
            self.assertTrue(updated['age_estimated'])
            self.assertEqual(f.day,76)
            for lang in ('ru','kz','en'):
                self.assertIn(t(lang,'decision_age_estimated'),format_balance_report(lang,f,updated,forecast))
            record_irrigation(fid,user_id=user)
            _, _, irrigated, _ = await FieldService.recommendation_today(fid,user)
            self.assertEqual(irrigated['gross_m3'],0)
            self.assertTrue(irrigated['age_estimated'])
            # Same plot, corrected exact planting age: replace config and today's snapshot.
            exact = payload(day_of_growth=76)
            exact_field = parse_field(exact)
            await persist_webapp_field(user,exact,exact_field,44.85,65.49,
                                      calculate_balance(exact_field,5,0),tomorrow)
            _, corrected, _, _ = await calculate_saved_field(fid,user)
            self.assertNotIn('age_estimated',corrected)


if __name__ == '__main__': unittest.main()
