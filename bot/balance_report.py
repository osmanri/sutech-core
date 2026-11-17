"""Report and immutable explanation for the daily water balance."""
from html import escape
from datetime import date
try:
    from i18n import t
except ImportError:
    from bot.i18n import t


def fmt(value):
    # Round only for display so stress thresholds use the original precision.
    rounded = round(value, 2)
    return f'{0.0 if rounded == 0 else rounded:.2f}'.rstrip('0').rstrip('.')


def fmt_area(value):
    """Keep the precision of a submitted hectare/sotka area in bot reports."""
    return f'{value:.10f}'.rstrip('0').rstrip('.')


def economics(lang, field, result):
    if result['status'] == 'deferred':
        # Zero pumping today is a postponed expense, not a method/season saving.
        text = t(lang, 'balance_econ_deferred')
        if result['cost'] is not None:
            text += '\n' + t(lang, 'balance_econ_today', ai=f"{result['cost']:.2f}")
        return text
    text = t(lang, 'balance_water_comparison',
             traditional=fmt(result['traditional_m3']), volume=fmt(result['gross_m3']),
             efficiency=fmt(result['efficiency'] * 100))
    if result['cost'] is None:
        return text + '\n' + t(lang, 'balance_econ_missing')
    text += '\n' + t(
        lang, 'balance_econ_comparison',
        traditional=f"{result['traditional_cost']:.2f}",
        ai=f"{result['cost']:.2f}",
        savings=f"{result['savings']:.2f}",
        kwh=f"{result['saved_kwh']:.2f}",
    )
    return text


def display_volume(lang, cubic_metres):
    """Small positive quantities remain visible rather than rounding to zero m³."""
    unit = 'm³' if lang == 'en' else 'м³'
    value = cubic_metres
    if 0 < value < 1:
        value *= 1000
        unit = 'L' if lang == 'en' else 'л'
        number = '<0.01' if value < .01 else fmt(value)
    else:
        number = fmt(value)
    if lang in ('ru', 'kz'):
        number = number.replace('.', ',')
    return escape(f'{number} {unit}')


def salinity_notes(lang, field, result):
    """Leaching and salt-loss lines, only from measured salinity (engine: water_balance.salinity)."""
    lines = []
    if result.get('leaching_impossible'):
        lines.append(t(lang, 'balance_salt_impossible', ecw=fmt(field.water_ec)))
    elif result.get('leaching_fraction') is not None:
        lines.append(t(lang, 'balance_salt_leach', ecw=fmt(field.water_ec), lr=fmt(result['leaching_fraction'] * 100)))
    if result.get('salinity_yield_loss_pct') is not None:
        lines.append(t(lang, 'balance_salt_loss', ece=fmt(field.soil_ec), loss=fmt(result['salinity_yield_loss_pct'])))
    return '\n'.join(lines)


def pump_limit_note(lang, result):
    """Warn when one day of pumping cannot deliver the advised volume (engine: PUMP_MAX_HOURS_PER_DAY)."""
    days = result.get('irrigation_days')
    if not days or days <= 1:
        return ''
    try:
        from water_balance import PUMP_MAX_HOURS_PER_DAY
    except ImportError:
        from bot.water_balance import PUMP_MAX_HOURS_PER_DAY
    return t(lang, 'balance_pump_limit', max_daily=fmt(result['max_daily_m3']), hours=fmt(PUMP_MAX_HOURS_PER_DAY),
             days=days, per_day=fmt(result['gross_m3'] / days))


def format_balance_report(lang, field, result, weather):
    """One decision card; formulas and economics live in its saved explanation."""
    status = result['status']
    if status == 'rice':
        decision = 'rice' if result['gross_m3'] > 0 else 'rice_deferred'
    else:
        decision = status
    reason = decision
    if status == 'deferred' and result.get('peff', 0) > 0:
        reason = 'rain'
    raw_date = str(weather.get('date', ''))
    try:
        report_date = date.fromisoformat(raw_date).strftime('%d.%m.%Y')
    except ValueError:
        report_date = raw_date or '—'
    text = t(lang, 'decision_card',
        decision=t(lang, f'decision_{decision}'),
        crop=escape(t(lang, f'report_crop_{field.crop}')),
        area=fmt_area(field.area_ha),
        unit='ha' if lang == 'en' else 'га',
        method=escape(t(lang, 'decision_rice_method' if status == 'rice' else f'report_irrig_{field.method}')),
        volume=display_volume(lang, result['gross_m3']),
        reason=t(lang, f'decision_reason_{reason}'),
        date=escape(report_date),
        timezone=escape(str(weather.get('timezone', ''))),
    )
    note = pump_limit_note(lang, result)
    if note:
        text += '\n\n' + note
    notes = salinity_notes(lang, field, result)
    if notes:
        text += '\n\n' + notes
    if field.saline:
        text += '\n\n' + t(lang, 'decision_saline')
    if field.field_type == 'greenhouse':
        text += '\n\n' + t(lang, 'decision_greenhouse')
    if result.get('age_estimated'):
        text += '\n\n' + t(lang, 'decision_age_estimated')
    return text


def format_balance_explanation(lang, field, result, weather):
    inputs = t(lang, 'balance_rice_inputs', area=fmt_area(field.area_ha),
               soil=escape(t(lang, f'balance_soil_{field.soil}'))) if result['status'] == 'rice' else t(
        lang, 'balance_inputs', area=fmt_area(field.area_ha),
        soil=escape(t(lang, f'balance_soil_{field.soil}')), day=field.day,
        moisture=escape(t(lang, f'balance_moisture_{field.moisture_condition}')),
        irrigation=escape(t(lang, f'report_irrig_{field.method}')))
    input_header = t(lang, 'balance_crop_header', crop=escape(t(lang, f'report_crop_{field.crop}'))) + '\n' + inputs + '\n\n'
    if result.get('age_estimated'):
        input_header += t(lang, 'decision_age_estimated') + '\n\n'
    if result['status'] == 'rice':
        text = t(lang, 'balance_rice_explanation',
            area=fmt_area(field.area_ha),
            soil=t(lang, f'balance_soil_{field.soil}'),
            water_layer=result.get('water_layer_cm', 12),
            etc=fmt(result.get('etc', 0.0)),
            seepage=fmt(result.get('seepage', 6.0)),
            peff=fmt(result.get('peff', 0.0)),
            net_mm=fmt(result.get('net_mm', 0.0)),
            net=fmt(result.get('net_m3', 0.0)),
            gross=fmt(result.get('gross_m3', 0.0)),
        )
        if result.get('cost') is not None:
            text += '\n\n' + t(lang, 'balance_pump_breakdown',
                power=fmt(field.pump_power_kw), flow=fmt(field.pump_productivity_m3h),
                tariff=fmt(field.power_price), ai_volume=fmt(result['gross_m3']),
                traditional_volume=fmt(result['traditional_m3']),
                ai_hours=fmt(result['ai_time_hours']),
                traditional_hours=fmt(result['traditional_time_hours']),
                deficit=fmt(result['deficit']), area=fmt_area(field.area_ha))
        if field.saline:
            text += '\n' + t(lang, 'balance_salinity')
        if field.field_type == 'greenhouse':
            text += '\n' + t(lang, 'balance_greenhouse')
        return input_header + text + '\n\n' + economics(lang, field, result)
    from_values = dict(
        crop=t(lang, f'report_crop_{field.crop}'), day=field.day,
        soil=t(lang, f'balance_soil_{field.soil}'), area=fmt_area(field.area_ha),
        zr=fmt(field.zr), p=fmt(field.p), kc=fmt(field.kc),
        stages='/'.join(str(int(v)) for v in field.stages) or '—',
        yesterday=fmt(field.yesterday), et0=fmt(result['et0']),
        rain=fmt(result['rain']), peff=fmt(result['peff']), etc=fmt(result['etc']),
        taw=fmt(result['taw']), raw=fmt(result['raw']), deficit=fmt(result['deficit']),
        threshold=fmt(result['threshold']), tech_threshold=fmt(result['tech_threshold']),
        moisture=t(lang, f"balance_moisture_{field.moisture_condition}"),
        efficiency=fmt(result['efficiency']),
        net=fmt(result['net_m3']), gross=fmt(result['gross_m3']),
        status=t(lang, f"balance_status_{result['status']}"),
    )
    text = t(lang, 'balance_explanation', **from_values)
    if result.get('overflow', 0) > 0:
        text += '\n' + t(lang, 'balance_overflow')
    if field.saline:
        text += '\n' + t(lang, 'balance_salinity')
    if field.field_type == 'greenhouse':
        text += '\n' + t(lang, 'balance_greenhouse')
    if field.crop == 'other':
        text += '\n' + t(lang, 'balance_custom')
    else:
        text += '\n' + t(lang, 'balance_calendar')
    if result['cost'] is not None:
        text += '\n\n' + t(lang, 'balance_pump_breakdown',
            power=fmt(field.pump_power_kw), flow=fmt(field.pump_productivity_m3h),
            tariff=fmt(field.power_price), ai_volume=fmt(result['gross_m3']),
            traditional_volume=fmt(result['traditional_m3']),
            ai_hours=fmt(result['ai_time_hours']),
            traditional_hours=fmt(result['traditional_time_hours']),
            deficit=fmt(result['deficit']), area=fmt_area(field.area_ha))
    return input_header + text + '\n\n' + economics(lang, field, result)
