"""Observable field-input help; stage-to-day mapping is an explicit calendar estimate."""
try:
    from water_balance import CROPS, BalanceInputError, number
except ImportError:
    from bot.water_balance import CROPS, BalanceInputError, number

STAGES = ('initial', 'development', 'middle', 'late')
STAGE_NAMES = {
    'ru': ('Начало', 'Активный рост', 'Основной сезон', 'Созревание / уборка'),
    'kz': ('Бастапқы кезең', 'Белсенді өсу', 'Негізгі кезең', 'Пісу / жинау'),
    'en': ('Early growth', 'Active growth', 'Main season', 'Ripening / harvest'),
}
SOIL_HELP = {
    'ru': ('Слегка увлажните небольшую пробу почвы без камней и разотрите пальцами.\n\n'
           'Песок: крупинки хорошо ощущаются, комок легко рассыпается.\n'
           'Суглинок: образует комок, короткая лента между пальцами рвется.\n'
           'Глина: липкая, образует прочный комок и длинную ленту.\n\n'
           'Это ориентир для трех вариантов модели. Если есть анализ почвы, используйте его.'),
    'kz': ('Тассыз шағын топырақ үлгісін аздап ылғалдандырып, саусақпен уқалаңыз.\n\n'
           'Құм: түйірлері сезіледі, кесегі оңай үгітіледі.\n'
           'Саздақ: кесек түзіледі, саусақ арасындағы қысқа таспа үзіледі.\n'
           'Саз: жабысқақ, берік кесек пен ұзын таспа түзіледі.\n\n'
           'Бұл модельдің үш нұсқасын таңдауға арналған бағдар. Топырақ талдауы бар болса, соны қолданыңыз.'),
    'en': ('Slightly moisten a small soil sample without stones and rub it between your fingers.\n\n'
           'Sand: gritty; the ball crumbles easily.\n'
           'Loam: forms a ball; a short ribbon breaks.\n'
           'Clay: sticky; forms a firm ball and a long ribbon.\n\n'
           'This is a guide to the three model options. Use a soil analysis if available.'),
}
STAGE_HELP = {
    'ru': ('Небольшие всходы или недавно высаженная рассада; между растениями видна почва.',
           'Появляются новые листья и побеги; растения быстро увеличиваются.',
           'Растения хорошо развиты; идет цветение или формирование урожая.',
           'Урожай созревает или приближается уборка.'),
    'kz': ('Шағын өскіндер немесе жақында отырғызылған көшет; араларында топырақ көрінеді.',
           'Жаңа жапырақтар мен өркендер пайда болып, өсімдіктер ұлғаяды.',
           'Өсімдіктер жақсы дамыған; гүлдеу немесе өнім қалыптасу кезеңі.',
           'Өнім пісіп жатыр немесе жинау жақындады.'),
    'en': ('Small seedlings or recent transplants; soil remains visible between plants.',
           'New leaves and shoots appear; plants are growing rapidly.',
           'Well-developed plants; flowering or crop formation.',
           'The crop is ripening or harvest is approaching.'),
}
MIDDLE_EXAMPLES = {
    'wheat': ('Колосья сформировались; идет цветение или налив зерна.', 'Масақтар қалыптасқан; гүлдеу немесе дән толысуы жүріп жатыр.', 'Heads have formed; flowering or grain filling.'),
    'cotton': ('Цветет; формируются и растут коробочки.', 'Гүлдеп жатыр; қауашақтар қалыптасып, өсуде.', 'Flowering; bolls are forming and growing.'),
    'corn': ('Метелки и початки сформировались; цветение или налив зерна.', 'Сіпсебас пен собықтар қалыптасқан; гүлдеу немесе дән толысуы.', 'Tassels and ears have formed; flowering or grain filling.'),
    'melon': ('Цветет; завязываются или растут плоды.', 'Гүлдеп жатыр; жемістер байланысып немесе өсіп жатыр.', 'Flowering; fruit is setting or growing.'),
    'tomato': ('Цветет; завязываются или растут плоды.', 'Гүлдеп жатыр; жемістер байланысып немесе өсіп жатыр.', 'Flowering; fruit is setting or growing.'),
    'potato': ('Развитая ботва; период формирования и роста клубней.', 'Ботвасы жақсы дамыған; түйнектер қалыптасып, өсетін кезең.', 'Well-developed foliage; tuber formation and growth.'),
    'alfalfa': ('Густой травостой; бутоны или начало цветения в первом цикле.', 'Қалың шөп; алғашқы циклде бүршіктену немесе гүлдеудің басы.', 'Dense stand; budding or early flowering in the first cycle.'),
}


def stage_options(crop, lang):
    language = lang if lang in STAGE_HELP else 'ru'
    index = {'ru': 0, 'kz': 1, 'en': 2}[language]
    descriptions = list(STAGE_HELP[language])
    if crop in MIDDLE_EXAMPLES:
        descriptions[2] = MIDDLE_EXAMPLES[crop][index]
    if crop == 'alfalfa':
        descriptions[3] = ('Приближается первый укос. Для отрастания после укоса нужны отдельные параметры.',
                           'Алғашқы орым жақындады. Орымнан кейінгі өсуге бөлек параметрлер қажет.',
                           'First cut is approaching. Regrowth after cutting needs separate settings.')[index]
    return tuple(zip(STAGES, STAGE_NAMES[language], descriptions))


def estimate_growth_day(crop, stage, stage_days=None):
    if crop not in CROPS or stage not in STAGES:
        raise BalanceInputError('growth_estimate')
    calendar = CROPS[crop][4] if stage_days is None else stage_days
    if not isinstance(calendar, (tuple, list)) or len(calendar) != 4:
        raise BalanceInputError('growth_estimate')
    lengths = [number(v, 'growth_estimate', 1, 730) for v in calendar]
    if any(not v.is_integer() for v in lengths):
        raise BalanceInputError('growth_estimate')
    index = STAGES.index(stage)
    # Later stages begin after the previous inclusive boundary used by crop_parameters.
    offset = max(1 if index else 0, int(lengths[index]) // 2)
    return int(sum(lengths[:index])) + offset


def growth_estimate_metadata(data, field):
    if data.get('growth_day_source') != 'stage':
        return {}
    stage = data.get('growth_stage')
    if field.day != estimate_growth_day(field.crop, stage, field.stages):
        raise BalanceInputError('growth_estimate')
    return {'age_estimated': True, 'age_estimation_stage': stage,
            'age_estimation_day': field.day, 'age_estimation_crop': field.crop}


def carry_growth_estimate(result, source):
    if source.get('age_estimated') and source.get('age_estimation_stage') in STAGES:
        for key in ('age_estimated', 'age_estimation_stage', 'age_estimation_day', 'age_estimation_crop'):
            if key in source:
                result[key] = source[key]
    return result
