"""Report and immutable explanation for the daily water balance."""
from html import escape
try:
    from i18n import t
except ImportError:
    from bot.i18n import t


def fmt(value):
    # Keep small non-zero recommended quantities visible.
    return f'{value:.6f}'.rstrip('0').rstrip('.')


def economics(lang, field, result):
    if result['status'] == 'deferred':
        return t(lang, 'balance_econ_deferred')
    if result['cost'] is None:
        return t(lang, 'balance_econ_missing')
    return t(lang, 'balance_econ_cost', volume=fmt(result['gross_m3']),
             energy=fmt(field.energy_per_m3), price=fmt(field.power_price),
             cost=f"{result['cost']:.2f}")


def format_balance_report(lang, field, result, weather):
    if result['status'] == 'rice':
        return t(lang, 'balance_rice')
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
    return text


def format_balance_explanation(lang, field, result, weather):
    if result['status'] == 'rice':
        return t(lang, 'balance_rice')
    from_values = dict(
        crop=t(lang, f'report_crop_{field.crop}'), day=field.day,
        soil=t(lang, f'balance_soil_{field.soil}'), area=fmt(field.area_ha),
        zr=fmt(field.zr), p=fmt(field.p), kc=fmt(field.kc),
        stages='/'.join(str(int(v)) for v in field.stages) or '—',
        yesterday=fmt(field.yesterday), et0=fmt(result['et0']),
        rain=fmt(result['rain']), peff=fmt(result['peff']), etc=fmt(result['etc']),
        taw=fmt(result['taw']), raw=fmt(result['raw']), deficit=fmt(result['deficit']),
        threshold=fmt(result['threshold']), efficiency=fmt(result['efficiency']),
        net=fmt(result['net_m3']), gross=fmt(result['gross_m3']),
        status=t(lang, f"balance_status_{result['status']}"),
    )
    text = t(lang, 'balance_explanation', **from_values)
    if field.crop == 'other':
        text += '\n' + t(lang, 'balance_custom')
    else:
        text += '\n' + t(lang, 'balance_calendar')
    return text + '\n\n' + economics(lang, field, result)
