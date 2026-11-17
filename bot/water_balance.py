"""Daily root-zone balance. Project policy built on FAO-56 TAW/RAW equations.

Crop/soil coefficients and irrigation thresholds are supplied by the project.
Stage calendars are editable examples, not local agronomic calibration.
No recommendation is treated as evidence that irrigation actually occurred.
"""
import math
from dataclasses import dataclass

CALCULATION_VERSION = 'fao56.9'

# Default screening model for a film-covered greenhouse when no calibrated
# indoor ET0 measurement is available. The farmer can still supply a measured
# value; otherwise Open-Meteo FAO-56 reference ET0 is reduced by the assumed
# 70% radiation transmission. Outdoor precipitation never reaches the crop.
GREENHOUSE_ET0_FACTOR = .70

# A pump cannot run all 24 hours: leave time for maintenance and electricity outages.
# A volume above one day's pumping is advised over several days instead of "today".
PUMP_MAX_HOURS_PER_DAY = 20.

# FAO-56 Table 19 midpoints: theta_FC and theta_WP lie inside the printed ranges, available water 0.07 / 0.15 / 0.15.
SOILS = {'sand': (.12, .05), 'loam': (.25, .10), 'clay': (.36, .21)}
# p, minimum root depth, maximum root depth, Kc initial/mid/end, stage days
CROPS = {
    'wheat': (.55, .25, 1.25, (.30, 1.15, .35), (20, 25, 60, 30)),
    'cotton': (.65, .25, 1.35, (.35, 1.18, .65), (30, 50, 60, 55)),
    'corn': (.55, .25, 1.35, (.30, 1.20, .50), (20, 35, 40, 30)),
    'alfalfa': (.55, .30, 1.50, (.40, 1.20, 1.15), (10, 20, 20, 10)),
    'melon': (.45, .25, 1.15, (.50, 1.05, .75), (25, 35, 40, 20)),
    'tomato': (.40, .25, 1.10, (.60, 1.15, .80), (30, 40, 45, 30)),
    'potato': (.35, .20, .50, (.50, 1.15, .75), (25, 30, 45, 30)),
}
# Salt tolerance: FAO-56 Table 23 (= FAO-29 Table 4): ECe threshold (dS/m) above which yield falls,
# and slope b (% yield loss per dS/m). Where the book gives a range the conservative end is used
# (lowest threshold, steepest slope). No values for melon in the book: no salinity estimate for it.
SALT_TOLERANCE = {
    'wheat': (6.0, 7.1), 'cotton': (7.7, 5.2), 'corn': (1.7, 12.0), 'alfalfa': (2.0, 7.3),
    'tomato': (0.9, 9.0), 'potato': (1.7, 12.0), 'rice': (3.0, 12.0),
}

# Fraction of the soil surface wetted by the irrigation system, FAO-56 Table 20.
# Trickle 0.3-0.4 (midpoint used; subsurface treated the same). Sprinkler, pivot and
# furrow are kept at 1.0: no reduction is applied (furrow is 0.3-1.0 in the book).
WETTED_FRACTION = {'drip': .35, 'subsurface': .35, 'sprinkler': 1., 'pivot': 1., 'furrow': 1.}
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
    moisture_condition: str
    stages: tuple
    kc: float
    zr: float
    p: float
    stage: str
    field_type: str
    saline: bool
    power_price: float | None
    pump_power_kw: float | None
    pump_productivity_m3h: float | None
    greenhouse_et0: float | None
    water_ec: float | None = None   # ECw of the irrigation water, dS/m (laboratory value)
    soil_ec: float | None = None    # ECe of the root zone, dS/m (saturation extract, laboratory value)
    greenhouse_medium: str = 'soil'      # 'soil' or 'substrate' (rockwool, coco)
    greenhouse_heated: bool = False


def crop_parameters(crop, day, stages, method='sprinkler'):
    p, zmin, zmax, (ini, mid, end), _ = CROPS[crop]
    # FAO-56 equation 60: with partial wetting, Kc ini = fw * Kc ini(Table 12).
    ini *= WETTED_FRACTION[method]
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


def stress_coefficient(depletion, taw, raw, p):
    """FAO-56 eq. 84: Ks = (TAW - Dr) / ((1 - p) TAW) once depletion exceeds RAW.

    Uses the depletion at the start of the day (FAO-56 recommends Dr,i-1).
    A stressed crop transpires less, so the deficit grows more slowly.
    """
    if taw <= 0 or depletion <= raw:
        return 1.
    return min(1., max(0., (taw - depletion) / ((1. - p) * taw)))


def root_zone_capacity(soil, zr, p):
    """Use identical arithmetic for the initial state and decision boundary."""
    fc, pwp = SOILS[soil]
    taw = 1000 * (fc - pwp) * zr
    return taw, p * taw


def parse_field(data):
    if not isinstance(data, dict) or type(data.get('balance_version')) is not int or data.get('balance_version') != 2:
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
    stages = data.get('stage_days', CROPS.get(crop, (None,) * 5)[4])
    if crop in CROPS:
        if not isinstance(stages, (list, tuple)) or len(stages) != 4:
            raise BalanceInputError('stages')
        stages = tuple(number(v, 'stages', 1, 730) for v in stages)
        if any(not v.is_integer() for v in stages):
            raise BalanceInputError('stages')
        if day > sum(stages):
            raise BalanceInputError('season_ended')
        kc, zr, p, stage = crop_parameters(crop, day, stages, method)
    elif crop == 'other':
        kc = number(data.get('custom_kc'), 'custom_kc', .05, 2)
        zr = number(data.get('custom_root_depth'), 'custom_root_depth', .05, 3)
        p = number(data.get('custom_p'), 'custom_p', .1, .8)
        stages, stage = (), 'custom'
    else:
        kc, zr, p, stages, stage = 0., 0., 0., (), 'rice'
    moisture_condition = data.get('moisture_condition')
    moisture_factors = {'recent': 0., 'normal': .5, 'dry': 1.}
    if not isinstance(moisture_condition, str) or moisture_condition not in moisture_factors:
        raise BalanceInputError('moisture_condition')
    # The farmer chooses an observable soil condition. Millimetres remain a
    # server-side value derived from the current root zone and soil profile.
    _, raw = root_zone_capacity(soil, zr, p)
    yesterday = raw * moisture_factors[moisture_condition]
    field_type = data.get('field_type', 'open')
    if field_type not in ('open', 'greenhouse') or data.get('is_saline', 'no') not in ('yes', 'no'):
        raise BalanceInputError('field')
    def optional(key, minimum, maximum):
        value = data.get(key)
        return None if value is None or value == '' else number(value, key, minimum, maximum)
    power = optional('power_price', 0, 10000)
    pump_power = optional('pump_power_kw', .000001, 100000)
    pump_productivity = optional('pump_productivity_m3h', .000001, 1000000)
    greenhouse_et0 = optional('greenhouse_et0', 0, 50)
    greenhouse_medium = data.get('greenhouse_medium', 'soil')
    greenhouse_heated = data.get('greenhouse_heated', 'no')
    if greenhouse_medium not in ('soil', 'substrate') or greenhouse_heated not in ('yes', 'no'):
        raise BalanceInputError('greenhouse')
    water_ec = optional('water_ec', 0, 25)
    soil_ec = optional('soil_ec', 0, 50)
    return FieldInput(crop, soil, area if unit == 'hectare' else area / 100, method,
                      int(day), yesterday, moisture_condition, stages, kc, zr, p, stage, field_type,
                      data.get('is_saline') == 'yes', power, pump_power,
                      pump_productivity, greenhouse_et0, water_ec, soil_ec,
                      greenhouse_medium, greenhouse_heated == 'yes')


def salinity(field, efficiency):
    """Leaching and salt yield loss from measured salinity (FAO-29 eq. 9 and FAO-56 eq. 87-90).

    Needs the irrigation water salinity ECw (dS/m). The leaching requirement for surface-type irrigation is
    LR = ECw / (5 ECe_threshold - ECw) (FAO-29, checked on its worked example 3). Usual irrigation losses
    already leach: the applied volume is net / min(efficiency, 1 - LR), the larger of the two needs.
    The yield loss needs the measured root-zone ECe: b * (ECe - threshold) percent.
    Without ECw nothing is invented: every value is None and the volume is unchanged.
    """
    out = dict(effective_efficiency=efficiency, leaching_fraction=None, leaching_impossible=False, salinity_yield_loss_pct=None)
    tolerance = SALT_TOLERANCE.get(field.crop)
    if tolerance is None:
        return out
    threshold, slope = tolerance
    if field.water_ec is not None:
        if 5 * threshold - field.water_ec <= 0:
            out['leaching_impossible'] = True   # the water is too salty for this crop to be leached in the usual way
        else:
            lr = field.water_ec / (5 * threshold - field.water_ec)
            out['leaching_fraction'] = lr
            if lr < 1:
                out['effective_efficiency'] = min(efficiency, 1 - lr)
            else:
                out['leaching_impossible'] = True
    if field.soil_ec is not None:
        out['salinity_yield_loss_pct'] = min(100., max(0., slope * (field.soil_ec - threshold)))
    return out


def greenhouse_unsupported(field):
    """Reason why no advice is given for a greenhouse, or None.

    The balance describes water in a soil root zone driven by outdoor weather. It does not describe a
    substrate (rockwool, coco: managed by drainage fraction) nor a heated greenhouse where the crop's water
    use follows heating and light, not outdoor weather, unless the farmer supplies a measured ET0.
    """
    if field.field_type != 'greenhouse':
        return None
    if field.greenhouse_medium == 'substrate':
        return 'substrate'
    if field.greenhouse_heated and field.greenhouse_et0 is None:
        return 'heated_needs_measurement'
    return None


def calculate_economics(ai_gross_volume, current_deficit_mm, area_ha,
                        power_price, pump_power_kw=22, pump_productivity_m3h=60):
    """Compare pumping the same root-zone deficit with both systems.

    Keep full precision here; report formatting rounds displayed values only.
    Missing pump data leaves the water recommendation available without a cost.
    """
    ai_gross_volume = number(ai_gross_volume, 'ai_gross_volume', 0, math.inf)
    current_deficit_mm = number(current_deficit_mm, 'current_deficit_mm', 0, 3000)
    area_ha = number(area_ha, 'area_ha', .00000001, 50000)
    # Furrow baseline: the same net deficit at the configured 50% efficiency.
    # Method efficiency already includes delivery losses; no extra overwatering.
    trad_gross_volume = (current_deficit_mm * 10 * area_ha) / METHODS['furrow'][1]
    if any(v is None for v in (power_price, pump_power_kw, pump_productivity_m3h)):
        return dict(traditional_m3=trad_gross_volume, ai_time_hours=None,
                    traditional_time_hours=None, cost=None, traditional_cost=None,
                    savings=None, saved_kwh=None, max_daily_m3=None, irrigation_days=None)

    tariff = number(power_price, 'power_price', 0, 10000)
    pump_power = number(pump_power_kw, 'pump_power_kw', .000001, 100000)
    pump_productivity = number(pump_productivity_m3h, 'pump_productivity_m3h', .000001, 1000000)
    ai_time_hours = ai_gross_volume / pump_productivity
    ai_cost = ai_time_hours * pump_power * tariff
    trad_time_hours = trad_gross_volume / pump_productivity
    trad_cost = trad_time_hours * pump_power * tariff
    savings = trad_cost - ai_cost
    saved_kwh = (trad_time_hours - ai_time_hours) * pump_power
    max_daily_m3 = pump_productivity * PUMP_MAX_HOURS_PER_DAY
    irrigation_days = max(1, math.ceil(ai_gross_volume / max_daily_m3 - 1e-9)) if ai_gross_volume > 0 else 0
    return dict(traditional_m3=trad_gross_volume, ai_time_hours=ai_time_hours,
                traditional_time_hours=trad_time_hours, cost=ai_cost,
                traditional_cost=trad_cost, savings=savings, saved_kwh=saved_kwh,
                max_daily_m3=max_daily_m3, irrigation_days=irrigation_days)


def calculate_balance(field, et0, rain):
    et0 = number(et0, 'et0', 0, 50)
    rain = number(rain, 'rain', 0, 3000)
    if field.field_type == 'greenhouse':
        et0 = field.greenhouse_et0 if field.greenhouse_et0 is not None else et0 * GREENHOUSE_ET0_FACTOR
        rain = 0.
    if field.crop == 'rice':
        seepage_map = {'clay': 3.0, 'loam': 6.0, 'sand': 12.0}
        seepage = seepage_map.get(field.soil, 6.0)
        etc = round(et0 * 1.25, 2)
        peff = 0. if rain < 5 else rain * .85
        net_mm = max(0.0, etc + seepage - peff)
        efficiency = 0.50
        net_m3 = net_mm * 10 * field.area_ha
        gross_m3 = net_m3 / efficiency
        economy = calculate_economics(gross_m3, net_mm, field.area_ha, field.power_price,
                                      field.pump_power_kw, field.pump_productivity_m3h)
        return dict(status='rice', is_rice=True, water_layer_cm=12, seepage=seepage,
                    etc=etc, et0=et0, rain=rain, peff=peff, net_mm=net_mm,
                    efficiency=efficiency, net_m3=net_m3, gross_m3=gross_m3,
                    raw=0.0, deficit=net_mm, threshold=net_mm, **economy)
    taw, raw = root_zone_capacity(field.soil, field.zr, field.p)
    peff = 0. if rain < 5 else rain * .75
    ks = stress_coefficient(field.yesterday, taw, raw, field.p)
    etc = et0 * field.kc * ks
    # Preserve RAW equality when equal evaporation/rain cancel. Sequential
    # additions can otherwise fabricate a one-ULP stress excursion.
    unbounded = math.fsum((field.yesterday, etc, -peff))
    deficit = min(taw, max(0., unbounded))
    tech_threshold, efficiency = METHODS[field.method]
    # A delivery-system limit must never postpone irrigation beyond the crop's
    # stress limit. This matters most for shallow roots and furrow irrigation.
    threshold = min(tech_threshold, raw)
    # Database round-trips and binary arithmetic can differ at RAW by one ULP.
    # Treat that microscopic difference as equality, never as crop stress.
    above_raw = deficit > raw and not math.isclose(deficit, raw, rel_tol=0, abs_tol=1e-9)
    at_threshold = deficit >= threshold or math.isclose(deficit, threshold, rel_tol=0, abs_tol=1e-9)
    status = 'critical' if above_raw else 'irrigate' if at_threshold else 'deferred'
    potential_net = deficit * 10 * field.area_ha
    net = potential_net if status != 'deferred' else 0.
    salt = salinity(field, efficiency)
    gross = net / salt['effective_efficiency']
    economy = calculate_economics(gross, deficit, field.area_ha, field.power_price,
                                  field.pump_power_kw, field.pump_productivity_m3h)
    reason = greenhouse_unsupported(field)
    if reason:
        status, net, gross = 'unsupported', 0., 0.
        economy = calculate_economics(0., deficit, field.area_ha, field.power_price,
                                      field.pump_power_kw, field.pump_productivity_m3h)
    return dict(status=status, taw=taw, raw=raw, deficit=deficit, unbounded=unbounded,
                overflow=max(0., unbounded-taw), rain_excess=max(0., -unbounded),
                et0=et0, rain=rain, peff=peff, etc=etc, ks=ks, kc=field.kc, zr=field.zr, p=field.p,
                threshold=threshold, tech_threshold=tech_threshold,
                efficiency=efficiency, net_m3=net, gross_m3=gross,
                unsupported_reason=reason, leaching_fraction=salt['leaching_fraction'], leaching_impossible=salt['leaching_impossible'],
                salinity_yield_loss_pct=salt['salinity_yield_loss_pct'],
                **economy)
