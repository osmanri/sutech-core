"""Crop catalog (plan stage A): one source of truth, generated engines, values within FAO-56 limits."""
import json
import subprocess
import unittest
from pathlib import Path

from bot.water_balance import CROPS, SALT_TOLERANCE, calculate_balance, parse_field

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / 'crops' / 'catalog.json').read_text(encoding='utf-8'))['crops']


class CropCatalog(unittest.TestCase):
    def test_generated_files_are_up_to_date(self):
        done = subprocess.run(['python3', 'crops/build.py', '--check'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_every_crop_is_complete_and_sourced(self):
        keys = [c['key'] for c in CATALOG]
        self.assertEqual(len(keys), len(set(keys)))
        for c in CATALOG:
            with self.subTest(crop=c['key']):
                self.assertEqual(set(c['names']), {'ru', 'kz', 'en'})
                self.assertTrue(all(c['names'].values()))
                self.assertIn(c['status'], ('FAO-56', 'mixed'))
                self.assertTrue(c['source'].strip())
                if c['status'] == 'mixed':
                    self.assertTrue(c['note'].strip(), 'a project value must be explained')

    def test_values_are_within_physical_and_fao_limits(self):
        for c in CATALOG:
            with self.subTest(crop=c['key']):
                self.assertTrue(.1 <= c['p'] <= .8)
                zmin, zmax = c['root']
                self.assertTrue(.1 <= zmin < zmax <= 2.0)
                self.assertTrue(all(.1 <= k <= 1.5 for k in c['kc']))
                self.assertGreaterEqual(c['kc'][1], c['kc'][0])        # mid-season is the peak of the initial -> mid rise
                self.assertEqual(len(c['stages']), 4)
                self.assertTrue(all(isinstance(d, int) and 1 <= d <= 400 for d in c['stages']))
                self.assertTrue(40 <= sum(c['stages']) <= 365)
                if c['salt']:
                    thr, b = c['salt']
                    self.assertTrue(.5 <= thr <= 10 and 1 <= b <= 40)

    def test_engine_tables_equal_the_catalog(self):
        self.assertEqual(list(CROPS), [c['key'] for c in CATALOG])
        for c in CATALOG:
            p, zmin, zmax, kc, stages = CROPS[c['key']]
            self.assertEqual((p, zmin, zmax, list(kc), list(stages)), (c['p'], c['root'][0], c['root'][1], c['kc'], c['stages']))
            self.assertEqual(SALT_TOLERANCE.get(c['key']), tuple(c['salt']) if c['salt'] else None)

    def test_python_and_javascript_engines_agree_for_every_crop(self):
        script = ("import {CROPS,SALT_TOLERANCE} from './serverless/tgcloud/lib/balance.js';"
                  "console.log(JSON.stringify({c:CROPS,s:SALT_TOLERANCE}));")
        done = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        js = json.loads(done.stdout)
        for key, (p, zmin, zmax, kc, stages) in CROPS.items():
            self.assertEqual(js['c'][key], [p, zmin, zmax, list(kc), list(stages)], key)
        self.assertEqual({k: tuple(v) for k, v in js['s'].items()}, dict(SALT_TOLERANCE))

    def test_every_crop_gives_advice_through_the_whole_season(self):
        for key, (_, _, _, _, stages) in CROPS.items():
            for day in (0, sum(stages) // 2, sum(stages)):
                with self.subTest(crop=key, day=day):
                    f = parse_field(dict(balance_version=2, crop=key, soil_type='loam', irrigation_type='drip', area=1,
                                         area_unit='hectare', day_of_growth=day, moisture_condition='dry'))
                    r = calculate_balance(f, 6, 0)
                    self.assertIn(r['status'], ('irrigate', 'critical', 'deferred'))
                    self.assertGreaterEqual(r['gross_m3'], 0)

    def test_hand_computed_new_crop(self):
        # Sugar beet (Tables 11, 12, 22), furrow irrigation, hand-computed from the book values.
        f = parse_field(dict(balance_version=2, crop='sugar_beet', soil_type='loam', irrigation_type='furrow', area=1, area_unit='hectare',
                             day_of_growth=90, moisture_condition='normal'))
        # 90 = 50 initial + 40 development -> end of development: Kc = mid 1.20, roots at the maximum 0.95 m
        self.assertAlmostEqual(f.kc, 1.20)
        self.assertAlmostEqual(f.zr, 0.95)
        r = calculate_balance(f, 5, 0)
        self.assertAlmostEqual(r['taw'], 1000 * (0.25 - 0.10) * 0.95)      # 142.5 mm
        self.assertAlmostEqual(r['raw'], 0.55 * 142.5)                      # p = 0.55


if __name__ == '__main__':
    unittest.main()
