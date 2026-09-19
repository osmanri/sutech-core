"""Daily root-zone balance. Project policy built on FAO-56 TAW/RAW equations.

Crop/soil coefficients and irrigation thresholds are supplied by the project.
Stage calendars are editable examples, not local agronomic calibration.
No recommendation is treated as evidence that irrigation actually occurred.
"""
import math
from dataclasses import dataclass

SOILS = {'sand': (.12, .05), 'loam': (.33, .18), 'clay': (.45, .30)}
# p, minimum root depth, maximum root depth, Kc initial/mid/end, stage days
CROPS = {
    'wheat': (.55, .25, 1.25, (.30, 1.15, .35), (20, 25, 60, 30)),
    'cotton': (.65, .25, 1.35, (.35, 1.18, .65), (30, 50, 60, 55)),
    'corn': (.55, .25, 1.35, (.30, 1.20, .50), (20, 35, 40, 30)),
    'alfalfa': (.55, .30, 1.50, (.40, 1.20, 1.15), (10, 20, 20, 10)),
    'melon': (.45, .25, 1.15, (.45, 1.05, .75), (25, 35, 40, 20)),
    'tomato': (.40, .25, 1.10, (.60, 1.15, .80), (30, 40, 45, 30)),
    'potato': (.35, .20, .50, (.50, 1.15, .75), (25, 30, 45, 30)),
}
METHODS = {'drip': (5., .90), 'subsurface': (5., .90),
           'sprinkler': (20., .75), 'pivot': (20., .75), 'furrow': (40., .50)}


class BalanceInputError(ValueError):
    pass


def number(value, name, minimum=0., maximum=1e6):
    if isinstance(value, bool) or value is None:
        raise BalanceInputError(name)
    try:
        parsed = float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError):
        raise BalanceInputError(name) from None
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise BalanceInputError(name)
    return parsed


@dataclass(frozen=True)
class FieldInput:
    crop: str
    soil: str
    area_ha: float
    method: str
    day: int
    yesterday: float
    stages: tuple
    kc: float
    zr: float
    p: float
    stage: str
    field_type: str
    saline: bool
    power_price: float | None
    energy_per_m3: float | None
    greenhouse_et0: float | None


def crop_parameters(crop, day, stages):
    p, zmin, zmax, (ini, mid, end), _ = CROPS[crop]
    initial, development, middle, late = stages
    if day <= initial:
        kc, stage = ini, 'initial'
    elif day <= initial + development:
        kc = ini + (mid - ini) * (day - initial) / development
        stage = 'development'
    elif day <= initial + development + middle:
        kc, stage = mid, 'middle'
    else:
        kc = mid + (end - mid) * min((day - initial - development - middle) / late, 1.)
        stage = 'late'
    # Explicit modelling assumption: root depth grows linearly from planting
    # to the end of development, then stays at the supplied maximum.
    zr = zmin + (zmax - zmin) * min(day / (initial + development), 1.)
    return kc, zr, p, stage


def parse_field(data):
    if not isinstance(data, dict) or type(data.get('balance_version')) is not int or data.get('balance_version') != 1:
        raise BalanceInputError('version')
    crop = data.get('crop')
    if not isinstance(crop, str) or crop not in {*CROPS, 'rice', 'other'}:
        raise BalanceInputError('crop')
    soil, method = data.get('soil_type'), data.get('irrigation_type')
    if not isinstance(soil, str) or not isinstance(method, str) or soil not in SOILS or method not in METHODS:
        raise BalanceInputError('soil_method')
    unit = data.get('area_unit')
    area = number(data.get('area'), 'area', .000001, 50000)
    if area >= 50000 or unit not in ('hectare', 'sotka'):
        raise BalanceInputError('area')
    day = number(data.get('day_of_growth'), 'day', 0, 3650)
    if not day.is_integer():
        raise BalanceInputError('day')
    yesterday = number(data.get('yesterday_deficit'), 'deficit', 0, 3000)
    stages = data.get('stage_days', CROPS.get(crop, (None,) * 5)[4])
    if crop in CROPS:
        if not isinstance(stages, (list, tuple)) or len(stages) != 4:
            raise BalanceInputError('stages')
        stages = tuple(number(v, 'stages', 1, 730) for v in stages)
        if any(not v.is_integer() for v in stages):
            raise BalanceInputError('stages')
        if day > sum(stages):
            raise BalanceInputError('season_ended')
        kc, zr, p, stage = crop_parameters(crop, day, stages)
    elif crop == 'other':
        kc = number(data.get('custom_kc'), 'custom_kc', .05, 2)
        zr = number(data.get('custom_root_depth'), 'custom_root_depth', .05, 3)
        p = number(data.get('custom_p'), 'custom_p', .1, .8)
        stages, stage = (), 'custom'
    else:
        kc, zr, p, stages, stage = 0., 0., 0., (), 'rice'
    field_type = data.get('field_type', 'open')
    if field_type not in ('open', 'greenhouse') or data.get('is_saline', 'no') not in ('yes', 'no'):
        raise BalanceInputError('field')
    def optional(key, minimum, maximum):
        value = data.get(key)
        return None if value is None or value == '' else number(value, key, minimum, maximum)
    power = optional('power_price', 0, 10000)
    energy = optional('energy_kwh_m3', .000001, 100)
    greenhouse_et0 = optional('greenhouse_et0', 0, 50)
    if field_type == 'greenhouse' and greenhouse_et0 is None and crop != 'rice':
        raise BalanceInputError('greenhouse_et0')
    return FieldInput(crop, soil, area if unit == 'hectare' else area / 100, method,
                      int(day), yesterday, stages, kc, zr, p, stage, field_type,
                      data.get('is_saline') == 'yes', power, energy, greenhouse_et0)


def calculate_balance(field, et0, rain):
    if field.crop == 'rice':
        return {'status': 'rice'}  # Flooded paddy requires a separate balance.
    et0 = number(et0, 'et0', 0, 50)
    rain = number(rain, 'rain', 0, 3000)
    if field.field_type == 'greenhouse':
        et0, rain = field.greenhouse_et0, 0.
    fc, pwp = SOILS[field.soil]
    taw = 1000 * (fc - pwp) * field.zr
    raw = field.p * taw
    peff = 0. if rain < 5 else rain * .75
    etc = et0 * field.kc
    unbounded = field.yesterday + etc - peff
    deficit = min(taw, max(0., unbounded))
    threshold, efficiency = METHODS[field.method]
    status = 'critical' if deficit > raw else 'irrigate' if deficit >= threshold else 'deferred'
    potential_net = deficit * 10 * field.area_ha
    net = potential_net if status != 'deferred' else 0.
    gross = net / efficiency
    cost = None if field.power_price is None or field.energy_per_m3 is None else (
        gross * field.energy_per_m3 * field.power_price)
    return dict(status=status, taw=taw, raw=raw, deficit=deficit, unbounded=unbounded,
                overflow=max(0., unbounded-taw), rain_excess=max(0., -unbounded),
                et0=et0, rain=rain, peff=peff, etc=etc, kc=field.kc, zr=field.zr, p=field.p,
                threshold=threshold, efficiency=efficiency, net_m3=net, gross_m3=gross,
                cost=cost)
