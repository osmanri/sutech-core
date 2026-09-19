"""Independent, deterministic verification of the supported Su-Tech model.

The oracle uses rational arithmetic and fixed project specifications. It does
not reuse the production profiles or its interpolation/calculation functions.
This verifies implementation, not field performance or local crop calibration.
"""
from fractions import Fraction as F
from itertools import product
from dataclasses import replace
import math
import unittest

from bot.water_balance import BalanceInputError, calculate_balance, parse_field


PROFILES = {
    'wheat': ('0.55', '0.25', '1.25', ('0.30', '1.15', '0.35'), (20, 25, 60, 30)),
    'cotton': ('0.65', '0.25', '1.35', ('0.35', '1.18', '0.65'), (30, 50, 60, 55)),
    'corn': ('0.55', '0.25', '1.35', ('0.30', '1.20', '0.50'), (20, 35, 40, 30)),
    'alfalfa': ('0.55', '0.30', '1.50', ('0.40', '1.20', '1.15'), (10, 20, 20, 10)),
    'melon': ('0.45', '0.25', '1.15', ('0.45', '1.05', '0.75'), (25, 35, 40, 20)),
    'tomato': ('0.40', '0.25', '1.10', ('0.60', '1.15', '0.80'), (30, 40, 45, 30)),
    'potato': ('0.35', '0.20', '0.50', ('0.50', '1.15', '0.75'), (25, 30, 45, 30)),
}
SOIL_STORAGE = {'sand': F('0.07'), 'loam': F('0.15'), 'clay': F('0.15')}
APPLICATION = {'drip': (5, F('0.9')), 'subsurface': (5, F('0.9')),
               'sprinkler': (20, F('0.75')), 'pivot': (20, F('0.75')),
               'furrow': (40, F('0.5'))}
MOISTURE = {'recent': F(0), 'normal': F('0.5'), 'dry': F(1)}
WEATHER = [(0, 0), (5, 0), (5, 4.999), (5, 5), (5, 8), (0, 3000), (50, 0)]


def inputs(**changes):
    data = dict(balance_version=2, crop='wheat', soil_type='loam', area='6,7',
                area_unit='hectare', irrigation_type='drip', day_of_growth=60,
                moisture_condition='normal', field_type='open', is_saline='no',
                power_price=25, pump_power_kw=22, pump_productivity_m3h=60)
    data.update(changes)
    return data


def reference_growth(crop, day, stages=None):
    p, low, high, coefficients, default_days = PROFILES[crop]
    durations = stages or default_days
    ini, development, middle, late = durations
    first, peak, last = map(F, coefficients)
    root = F(low) + (F(high) - F(low)) * min(F(day, ini + development), 1)
    if day <= ini:
        kc = first
    elif day <= ini + development:
        kc = first + (peak - first) * F(day - ini, development)
    elif day <= ini + development + middle:
        kc = peak
    else:
        kc = peak + (last - peak) * F(day - ini - development - middle, late)
    return kc, root, F(p)


def reference_balance(data, et0, rain):
    kc, root, p = reference_growth(data['crop'], data['day_of_growth'], data.get('stage_days'))
    taw = 1000 * SOIL_STORAGE[data['soil_type']] * root
    raw = p * taw
    previous = raw * MOISTURE[data['moisture_condition']]
    if data['field_type'] == 'greenhouse':
        et0, rain = data['greenhouse_et0'], 0
    etc = F(str(et0)) * kc
    effective = F(0) if rain < 5 else F(str(rain)) * F('0.75')
    deficit = min(taw, max(F(0), previous + etc - effective))
    tech, efficiency = APPLICATION[data['irrigation_type']]
    threshold = min(tech, raw)
    status = 'critical' if deficit > raw else 'irrigate' if deficit >= threshold else 'deferred'
    area = F(str(data['area']).replace(',', '.'))
    if data['area_unit'] == 'sotka':
        area /= 100
    # Independent dimensional route: mm * m² = litres, then litres / 1000 = m³.
    required_m3 = deficit * (area * 10000) / 1000
    gross = F(0) if status == 'deferred' else required_m3 / efficiency
    trad = required_m3 * F('2.7')
    power, flow, tariff = [F(str(data[k]).replace(',', '.')) for k in
                           ('pump_power_kw', 'pump_productivity_m3h', 'power_price')]
    cost = gross * power * tariff / flow
    traditional_cost = trad * power * tariff / flow
    return dict(kc=kc, zr=root, taw=taw, raw=raw, threshold=threshold, peff=effective,
                etc=etc, deficit=deficit, gross_m3=gross, traditional_m3=trad,
                cost=cost, traditional_cost=traditional_cost,
                savings=traditional_cost-cost, saved_kwh=(trad-gross)*power/flow,
                ai_time_hours=gross/flow, traditional_time_hours=trad/flow, status=status)


class CalculationAudit(unittest.TestCase):
    def test_supported_scenario_matrix_against_independent_reference(self):
        cases, negatives, failures = 0, 0, []
        for crop, profile in PROFILES.items():
            a, b, c, d = profile[-1]
            days = sorted({0, a, a+1, a+b-1, a+b, a+b+1, a+b+c, a+b+c+1, a+b+c+d})
            for day, soil, method, moisture, weather, greenhouse, unit in product(
                    days, SOIL_STORAGE, APPLICATION, MOISTURE, WEATHER,
                    (False, True), ('hectare', 'sotka')):
                data = inputs(crop=crop, day_of_growth=day, soil_type=soil,
                              irrigation_type=method, moisture_condition=moisture,
                              field_type='greenhouse' if greenhouse else 'open',
                              greenhouse_et0=2.5, area_unit=unit,
                              area='6,7' if unit == 'hectare' else '670')
                actual = calculate_balance(parse_field(data), *weather)
                expected = reference_balance(data, *weather)
                cases += 1
                negatives += actual['savings'] < 0
                bad = []
                for key, value in expected.items():
                    matches = actual[key] == value if key == 'status' else math.isclose(
                        actual[key], float(value), rel_tol=1e-10, abs_tol=1e-8)
                    if not matches:
                        bad.append((key, actual[key], str(value)))
                if bad and len(failures) < 12:
                    failures.append((crop, day, soil, method, moisture, weather, greenhouse, unit, bad))
        print(f'AUDIT: {cases} scenario combinations; negative savings: {negatives}')
        self.assertEqual(negatives, 0)
        self.assertFalse(failures, f'Independent reference mismatches: {failures}')

    def test_every_growth_day_default_and_custom_calendars(self):
        cases = 0
        for crop, profile in PROFILES.items():
            for calendar in [profile[-1], (1, 2, 3, 4), (30, 50, 60, 55)]:
                for day in range(sum(calendar)+1):
                    actual = parse_field(inputs(crop=crop, stage_days=list(calendar), day_of_growth=day))
                    kc, root, p = reference_growth(crop, day, calendar)
                    self.assertAlmostEqual(actual.kc, float(kc), places=12)
                    self.assertAlmostEqual(actual.zr, float(root), places=12)
                    self.assertEqual(actual.p, float(p))
                    cases += 1
        print(f'AUDIT: {cases} growth-day/calendar cases')

    def test_exact_raw_boundary_all_days_soils_and_methods(self):
        failures = []
        for crop, profile in PROFILES.items():
            for day, soil, method in product(range(sum(profile[-1])+1), SOIL_STORAGE, APPLICATION):
                field = parse_field(inputs(crop=crop, day_of_growth=day,
                    soil_type=soil, irrigation_type=method, moisture_condition='dry'))
                result = calculate_balance(field, 0, 0)
                if result['status'] != 'irrigate' and len(failures) < 12:
                    failures.append((crop, day, soil, method, field.yesterday, result['raw'], result['status']))
        self.assertFalse(failures, f'Dry starts at exactly RAW, not above/below it: {failures}')

    def test_structured_moisture_input_is_a_validation_error(self):
        for bad in ([], {}, ['dry'], {'state': 'dry'}):
            with self.subTest(value=bad):
                with self.assertRaises(BalanceInputError):
                    parse_field(inputs(moisture_condition=bad))

    def test_small_real_changes_around_raw_keep_their_meaning(self):
        field = parse_field(inputs(crop='potato', day_of_growth=0,
            soil_type='sand', moisture_condition='dry', irrigation_type='furrow'))
        raw = F('4.9')
        for offset, status in [(-1e-8, 'deferred'), (0, 'irrigate'), (1e-8, 'critical')]:
            initial = field.yesterday if not offset else float(raw) + offset
            self.assertEqual(calculate_balance(replace(field, yesterday=initial), 0, 0)['status'], status)

    def test_custom_crop_and_pump_extremes_against_exact_cost(self):
        count = 0
        for soil, method, p, root, area, unit, power, flow, tariff in product(
                SOIL_STORAGE, APPLICATION, ('0.1', '0.8'), ('0.05', '3'),
                ('0.000001', '6.7', '49999.99'), ('hectare', 'sotka'),
                ('0.000001', '22', '100000'), ('0.000001', '60', '1000000'),
                ('0', '25.5', '10000')):
            data = inputs(crop='other', custom_kc='1.1', custom_p=p,
                custom_root_depth=root, soil_type=soil, irrigation_type=method,
                moisture_condition='dry', area=area, area_unit=unit,
                pump_power_kw=power, pump_productivity_m3h=flow, power_price=tariff)
            result = calculate_balance(parse_field(data), 0, 0)
            deficit = F(p) * 1000 * SOIL_STORAGE[soil] * F(root)
            net = deficit * 10 * F(area) / (100 if unit == 'sotka' else 1)
            ai = net / APPLICATION[method][1] * F(power) * F(tariff) / F(flow)
            trad = net * F('2.7') * F(power) * F(tariff) / F(flow)
            for key, expected in [('cost', ai), ('traditional_cost', trad), ('savings', trad-ai)]:
                self.assertTrue(math.isfinite(result[key]))
                self.assertGreaterEqual(result[key], 0)
                self.assertTrue(math.isclose(result[key], float(expected), rel_tol=1e-10, abs_tol=1e-12),
                                (key, result[key], str(expected)))
            count += 1
        print(f'AUDIT: {count} custom-crop/pump/area/tariff boundary cases')

    def test_economy_scales_with_real_pump_units(self):
        base = calculate_balance(parse_field(inputs()), 5, 0)
        for change, factor in [({'area': 13.4}, 2), ({'pump_power_kw': 44}, 2),
                               ({'pump_productivity_m3h': 120}, .5), ({'power_price': 50}, 2)]:
            actual = calculate_balance(parse_field(inputs(**change)), 5, 0)
            for key in ('cost', 'traditional_cost', 'savings'):
                self.assertAlmostEqual(actual[key], base[key]*factor, places=8)


if __name__ == '__main__':
    unittest.main()
