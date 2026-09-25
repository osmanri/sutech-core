"""Report and immutable explanation for the daily water balance."""
from html import escape
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
    if result['cost'] is None:
        return t(lang, 'balance_econ_missing')
    text = t(
        lang, 'balance_econ_comparison',
        traditional=f"{result['traditional_cost']:.2f}",
        ai=f"{result['cost']:.2f}",
        savings=f"{result['savings']:.2f}",
        kwh=f"{result['saved_kwh']:.2f}",
    )
    if result['status'] == 'deferred':
        text += '\n' + t(lang, 'balance_econ_deferred')
    return text


def format_balance_report(lang, field, result, weather):
    crop_header = t(lang, 'balance_crop_header', crop=escape(t(lang, f'report_crop_{field.crop}')))
    if result['status'] == 'rice':
        input_line = t(lang, 'balance_rice_inputs', area=fmt_area(field.area_ha),
                       soil=escape(t(lang, f'balance_soil_{field.soil}')))
        return crop_header + '\n' + input_line + '\n' + t(lang, 'balance_rice',
            water_layer=result.get('water_layer_cm', 12),
            seepage=fmt(result.get('seepage', 6.0)),
            etc=fmt(result.get('etc', 0.0)),
            volume=fmt(result.get('gross_m3', 0.0)),
            economics=economics(lang, field, result),
            date=escape(weather.get('date', '')),
            timezone=escape(weather.get('timezone', '')),
        )
    text = t(lang, 'balance_report',
        status=t(lang, f"balance_status_{result['status']}"),
        raw=fmt(result['raw']), deficit=fmt(result['deficit']), threshold=fmt(result['threshold']),
        irrigation=t(lang, f'report_irrig_{field.method}'),
        volume=fmt(result['gross_m3']), efficiency=round(result['efficiency']*100),
        economics=economics(lang, field, result),
        date=escape(weather['date']), timezone=escape(weather['timezone']),
    )
    if result['overflow'] > 0:
        text += '\n' + t(lang, 'balance_overflow')
    if field.saline:
        text += '\n' + t(lang, 'balance_salinity')
    if field.field_type == 'greenhouse':
        text += '\n' + t(lang, 'balance_greenhouse')
    input_line = t(lang, 'balance_inputs',
                   area=fmt_area(field.area_ha),
                   soil=escape(t(lang, f'balance_soil_{field.soil}')),
                   day=field.day,
                   moisture=escape(t(lang, f'balance_moisture_{field.moisture_condition}')),
                   irrigation=escape(t(lang, f'report_irrig_{field.method}')))
    return crop_header + '\n' + input_line + '\n' + text


def format_balance_explanation(lang, field, result, weather):
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
        return text + '\n\n' + economics(lang, field, result)
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
    return text + '\n\n' + economics(lang, field, result)
