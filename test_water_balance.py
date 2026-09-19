import unittest
from dataclasses import replace
from bot.water_balance import parse_field, calculate_balance, BalanceInputError, CROPS, METHODS, SOILS
from bot.balance_report import format_balance_report, format_balance_explanation


def payload(**kwargs):
    data = dict(balance_version=2, crop='wheat', soil_type='loam', area=1,
                area_unit='hectare', irrigation_type='drip', day_of_growth=60,
                moisture_condition='recent', field_type='open', is_saline='no')
    data.update(kwargs)
    return data


class BalanceTests(unittest.TestCase):
    def test_moisture_condition_is_mapped_to_raw_on_server(self):
        recent = parse_field(payload(moisture_condition='recent', yesterday_deficit=999))
        normal = parse_field(payload(moisture_condition='normal', yesterday_deficit=999))
        dry = parse_field(payload(moisture_condition='dry', yesterday_deficit=999))
        raw = calculate_balance(recent, 0, 0)['raw']
        self.assertEqual(recent.yesterday, 0)
        self.assertAlmostEqual(normal.yesterday, .5 * raw)
        self.assertAlmostEqual(dry.yesterday, raw)

    def test_reference_balance_and_cost(self):
        field = parse_field(payload(moisture_condition='normal', area='6,7', power_price=25, energy_kwh_m3=.2))
        r = calculate_balance(field, 5, 8)
        self.assertAlmostEqual(r['taw'], 187.5)
        self.assertAlmostEqual(r['raw'], 103.125)
        self.assertAlmostEqual(r['peff'], 6)
        self.assertAlmostEqual(field.yesterday, r['raw'] * .5)
        self.assertAlmostEqual(r['deficit'], field.yesterday + 5 * field.kc - 6)
        self.assertAlmostEqual(r['gross_m3'], r['deficit'] * 10 * 6.7 / .9)
        self.assertAlmostEqual(r['cost'], r['gross_m3'] * .2 * 25)
        self.assertAlmostEqual(r['traditional_m3'], r['etc'] * 1.35 / .5 * 10 * 6.7)
        self.assertAlmostEqual(r['savings'], r['traditional_cost'] - r['cost'])
        self.assertAlmostEqual(r['saved_kwh'], (r['traditional_m3'] - r['gross_m3']) * .2)

    def test_all_method_thresholds_and_raw_priority(self):
        for method, (threshold, eta) in METHODS.items():
            for d, status in [(threshold-.01,'deferred'),(threshold,'irrigate'),(threshold+.01,'irrigate')]:
                base = parse_field(payload(irrigation_type=method))
                actual = min(threshold, base.p * 1000 * (SOILS[base.soil][0]-SOILS[base.soil][1]) * base.zr)
                d = actual + (d - threshold)
                r = calculate_balance(replace(base, yesterday=d),0,0)
                self.assertEqual(r['status'], status)
                self.assertAlmostEqual(r['gross_m3'], 0 if status == 'deferred' else d*10/eta)
        f = parse_field(payload(soil_type='sand',day_of_growth=0,irrigation_type='furrow',moisture_condition='dry'))
        raw = calculate_balance(f,0,0)['raw']
        self.assertEqual(calculate_balance(f,0,0)['threshold'], raw)
        self.assertEqual(calculate_balance(f,0,0)['status'], 'irrigate')
        f = replace(f, yesterday=raw + .01)
        self.assertEqual(calculate_balance(f,0,0)['status'], 'critical')

    def test_rain_cutoff_clamping_and_repeatability(self):
        f = replace(parse_field(payload()), yesterday=10)
        self.assertEqual(calculate_balance(f,0,4.999)['peff'],0)
        self.assertEqual(calculate_balance(f,0,5)['peff'],3.75)
        self.assertEqual(calculate_balance(f,0,100)['deficit'],0)
        self.assertEqual(calculate_balance(f,5,0),calculate_balance(f,5,0))
        r = calculate_balance(replace(parse_field(payload()), yesterday=1000),0,0)
        self.assertEqual(r['deficit'],r['taw'])
        self.assertGreater(r['overflow'],0)

    def test_stages_and_root_limits_all_crops(self):
        for crop, (p,zmin,zmax,kcs,stages) in CROPS.items():
            start = parse_field(payload(crop=crop,day_of_growth=0))
            mid = parse_field(payload(crop=crop,day_of_growth=stages[0]+stages[1]))
            end = parse_field(payload(crop=crop,day_of_growth=sum(stages)))
            self.assertEqual(start.kc,kcs[0]); self.assertEqual(start.zr,zmin)
            self.assertAlmostEqual(mid.kc,kcs[1]); self.assertAlmostEqual(mid.zr,zmax)
            self.assertAlmostEqual(end.kc,kcs[2]); self.assertAlmostEqual(end.zr,zmax)
            with self.assertRaises(BalanceInputError):
                parse_field(payload(crop=crop,day_of_growth=sum(stages)+1))
        custom = parse_field(payload(day_of_growth=20,stage_days=[10,20,40,20]))
        self.assertAlmostEqual(custom.kc,.725)

    def test_bad_inputs_and_missing_fields(self):
        for key in ['soil_type','day_of_growth','moisture_condition','balance_version']:
            d=payload(); del d[key]
            with self.assertRaises(BalanceInputError): parse_field(d)
        for value in [None,True,'NaN','inf','-1','6,7,8','']:
            with self.assertRaises(BalanceInputError): parse_field(payload(moisture_condition=value))
        for stages in [[],[0,20,30,10],[1,2,3.5,4], '30,50,60,55']:
            with self.assertRaises(BalanceInputError): parse_field(payload(stage_days=stages))
        with self.assertRaises(BalanceInputError): parse_field(payload(day_of_growth=1.5))
        with self.assertRaises(BalanceInputError): parse_field(payload(area=50000))
        for key in ['crop', 'soil_type', 'irrigation_type']:
            for value in [[], {}, None]:
                with self.assertRaises(BalanceInputError): parse_field(payload(**{key:value}))
        with self.assertRaises(BalanceInputError): parse_field(payload(balance_version=True))
        # Client legacy coefficients cannot mutate server profiles.
        self.assertEqual(parse_field(payload(kc=99,irrigation_eff=99)).kc,1.15)

    def test_units_greenhouse_saline_custom_rice(self):
        a=calculate_balance(parse_field(payload(area=1,moisture_condition='normal')),5,0)
        b=calculate_balance(parse_field(payload(area=100,area_unit='sotka',moisture_condition='normal')),5,0)
        self.assertEqual(a,b)
        with self.assertRaises(BalanceInputError): parse_field(payload(field_type='greenhouse'))
        g=parse_field(payload(field_type='greenhouse',greenhouse_et0=2))
        r=calculate_balance(g,5,40)
        self.assertEqual(r['rain'],0); self.assertEqual(r['et0'],2)
        sal=calculate_balance(parse_field(payload(area=1,moisture_condition='normal',is_saline='yes')),5,0)
        self.assertEqual(a,sal)
        self.assertEqual(calculate_balance(parse_field(payload(crop='rice')),0,0)['status'],'rice')
        with self.assertRaises(BalanceInputError): parse_field(payload(crop='other'))
        f=parse_field(payload(crop='other',custom_kc=1.1,custom_p=.4,custom_root_depth=.5))
        self.assertEqual(f.zr,.5)

    def test_reports_both_languages_all_statuses(self):
        weather={'date':'2026-09-19','timezone':'Asia/Almaty'}
        for lang in ['ru','kz']:
            for d in [0,20,120]:
                f=replace(parse_field(payload()), yesterday=d)
                r=calculate_balance(f,0,0)
                for text in [format_balance_report(lang,f,r,weather),format_balance_explanation(lang,f,r,weather)]:
                    self.assertNotIn('{',text); self.assertLess(len(text),4096)
                self.assertIsNone(r['cost'])

    def test_economics_report_compares_traditional_and_ai_costs(self):
        weather={'date':'2026-09-19','timezone':'Asia/Almaty'}
        f=parse_field(payload(moisture_condition='recent', power_price=25, energy_kwh_m3=.2))
        r=calculate_balance(f,5,0)
        for lang, labels in [('ru', ('Традиционный', 'Экономия')), ('kz', ('Дәстүрлі', 'Үнем'))]:
            report=format_balance_report(lang,f,r,weather)
            self.assertIn(labels[0], report)
            self.assertIn(labels[1], report)
            self.assertIn('кВт', report)


if __name__ == '__main__': unittest.main()
