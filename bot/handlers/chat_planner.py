"""Deterministic chat alternative to the Mini App; never consumes Gemini quota."""

import asyncio
import secrets
from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.i18n import t
from bot.user_state import get_lang
from bot.water_balance import number, parse_field, BalanceInputError, CROPS
from bot.keyboards.reply import get_main_reply_keyboard
from bot.handlers.webapp import handle_field_payload
from bot.ai_i18n import AI_STRINGS


class ChatPlan(StatesGroup):
    collecting = State()
    calculating = State()


PLAN_BUTTON = {'ru':'💬 Расчёт без сайта', 'kz':'💬 Сайтсыз есептеу', 'en':'💬 Plan in chat'}
COPY = {
    'crop': ('Выберите культуру.', 'Дақылды таңдаңыз.', 'Choose a crop.'),
    'area': ('Введите площадь в гектарах. Например: 0.1', 'Ауданды гектармен жазыңыз. Мысалы: 0.1', 'Enter area in hectares. Example: 0.1'),
    'location': ('Отправьте геопозицию поля или широту и долготу через пробел: 44.85 65.50', 'Алқап геолокациясын немесе ендік пен бойлықты бос орынмен жіберіңіз: 44.85 65.50', 'Send the field location or latitude and longitude separated by a space: 44.85 65.50'),
    'day_of_growth': ('Сколько дней прошло после посадки? Введите целое число.', 'Егілгеннен бері қанша күн өтті? Бүтін сан жазыңыз.', 'How many days since planting? Enter a whole number.'),
    'soil_type': ('Выберите почву.', 'Топырақты таңдаңыз.', 'Choose soil type.'),
    'moisture_condition': ('Каково состояние почвы?', 'Топырақ күйі қандай?', 'What is the soil condition?'),
    'irrigation_type': ('Выберите способ полива.', 'Суару әдісін таңдаңыз.', 'Choose irrigation method.'),
    'field_type': ('Где растёт культура?', 'Дақыл қайда өседі?', 'Where is the crop grown?'),
    'is_saline': ('Есть ли засоление почвы?', 'Топырақ тұзданған ба?', 'Is the soil saline?'),
    'custom': ('Для другой культуры введите Kc, глубину корней в метрах и p через пробел. Например: 1.0 0.5 0.5', 'Басқа дақыл үшін Kc, тамыр тереңдігі (м) және p жазыңыз. Мысалы: 1.0 0.5 0.5', 'For a custom crop, enter Kc, root depth in metres and p. Example: 1.0 0.5 0.5'),
    'greenhouse_et0': ('Введите ET0 теплицы в мм/сутки или выберите оценку по наружной погоде × 0.70.', 'Жылыжай ET0 мәнін мм/күнмен жазыңыз немесе сыртқы ауа райы × 0.70 бағасын таңдаңыз.', 'Enter greenhouse ET0 in mm/day or choose outdoor weather × 0.70 screening estimate.'),
    'pump': ('Для расчёта электричества введите тариф ₸/кВт·ч, мощность кВт и производительность м³/ч через пробел. Или пропустите.', 'Электр есебі үшін тариф ₸/кВт·сағ, қуат кВт және өнімділік м³/сағ жазыңыз. Немесе өткізіңіз.', 'For electricity cost enter tariff ₸/kWh, power kW and productivity m³/h. Or skip.'),
    'confirm': ('Проверьте параметры и нажмите «Рассчитать». Расчёт и история работают так же, как на сайте.', 'Параметрлерді тексеріп, «Есептеу» басыңыз. Есеп пен тарих сайттағыдай жұмыс істейді.', 'Review and press Calculate. Calculation and history use the same engine as the website.'),
    'back': ('← Назад', '← Артқа', '← Back'),
    'cancel': ('Отмена', 'Бас тарту', 'Cancel'),
    'cancelled': ('Расчёт отменён. Вы в главном меню.', 'Есеп тоқтатылды. Басты мәзірдесіз.', 'Planning cancelled. Back to main menu.'),
    'invalid': ('Проверьте ввод и ответьте на текущий вопрос. Нужные единицы указаны выше.', 'Мәнді тексеріп, қазіргі сұраққа жауап беріңіз. Өлшем бірліктері жоғарыда көрсетілген.', 'Check your input and answer the current question using the units shown above.'),
    'skip': ('Пропустить', 'Өткізу', 'Skip'),
    'estimate': ('Оценка × 0.70', 'Баға × 0.70', 'Estimate × 0.70'),
    'calculate': ('Рассчитать', 'Есептеу', 'Calculate'),
    'working': ('Получаю погоду и считаю полив…', 'Ауа райын алып, суаруды есептеймін…', 'Fetching weather and calculating irrigation…'),
    'stale': ('Эта кнопка устарела. Используйте текущий шаг или /plan.', 'Бұл батырма ескірген. Қазіргі қадамды немесе /plan қолданыңыз.', 'This button is outdated. Use the current step or /plan.'),
}
BASE = ['crop','area','location','day_of_growth','soil_type','moisture_condition','irrigation_type','field_type','is_saline']
ENUMS = {'crop': [*CROPS, 'rice','other'], 'soil_type':['sand','loam','clay'],
         'moisture_condition':['recent','normal','dry'],
         'irrigation_type':['drip','sprinkler','pivot','furrow','subsurface'],
         'field_type':['open','greenhouse'], 'is_saline':['no','yes']}
_finish_lock = asyncio.Lock()


def phrase(lang, key):
    return COPY[key][{'ru':0,'kz':1,'en':2}.get(lang,0)]


def steps(values):
    return BASE + (['custom'] if values.get('crop') == 'other' else []) + (
        ['greenhouse_et0'] if values.get('field_type') == 'greenhouse' else []) + ['pump','confirm']


def option_label(lang, key, value):
    if key == 'crop': return t(lang, 'report_crop_' + value)
    if key == 'irrigation_type': return t(lang, 'report_irrig_' + value)
    return {
        'sand':('Песок','Құм','Sand'), 'loam':('Суглинок','Саздақ','Loam'), 'clay':('Глина','Саз','Clay'),
        'recent':('Недавно поливали / дождь','Жақында суарылды / жаңбыр','Recently watered / rain'),
        'normal':('Обычная влажность','Қалыпты ылғал','Normal moisture'), 'dry':('Сухая','Құрғақ','Dry'),
        'open':('Открытое поле','Ашық алқап','Open field'), 'greenhouse':('Теплица','Жылыжай','Greenhouse'),
        'no':('Нет','Жоқ','No'), 'yes':('Да','Иә','Yes'),
    }[value][{'ru':0,'kz':1,'en':2}.get(lang,0)]


def accept_input(key, raw, values):
    if key in ENUMS:
        if raw not in ENUMS[key]: raise ValueError(key)
        return {key: raw}
    if key == 'area':
        area = number(raw,'area',.000001,49999.999)
        return {'area':area}
    if key == 'day_of_growth':
        day=number(raw,'day',0,3650)
        if not day.is_integer() or (values['crop'] in CROPS and day > sum(CROPS[values['crop']][4])):
            raise ValueError('day')
        return {key:int(day)}
    if key == 'greenhouse_et0': return {key:None if raw == 'skip' else number(raw,key,0,50)}
    if key == 'pump' and raw == 'skip':
        return dict(power_price=None,pump_power_kw=None,pump_productivity_m3h=None)
    nums = str(raw).replace(';',' ').split()
    if key == 'location' and len(nums)==2:
        return dict(latitude=number(nums[0],'latitude',-90,90),longitude=number(nums[1],'longitude',-180,180))
    if key == 'custom' and len(nums)==3:
        return dict(custom_kc=number(nums[0],'Kc',.05,2), custom_root_depth=number(nums[1],'Zr',.05,3), custom_p=number(nums[2],'p',.1,.8))
    if key == 'pump' and len(nums)==3:
        return dict(power_price=number(nums[0],'tariff',0,10000), pump_power_kw=number(nums[1],'power',.000001,100000), pump_productivity_m3h=number(nums[2],'flow',.000001,1000000))
    raise ValueError(key)


def prompt(data, lang):
    flow=steps(data['values']); i=data['step']; key=flow[i]
    prefix=f"Su-Tech · {i+1}/{len(flow)}\n\n"
    text=prefix+phrase(lang,key)
    if key=='confirm':
        v=data['values']
        labels=[option_label(lang,'crop',v['crop']),f"{v['area']:g} ha",
                f"{v['latitude']:g}, {v['longitude']:g}",f"{v['day_of_growth']} d",
                option_label(lang,'soil_type',v['soil_type']),option_label(lang,'moisture_condition',v['moisture_condition']),
                option_label(lang,'irrigation_type',v['irrigation_type']),option_label(lang,'field_type',v['field_type']),
                f"{phrase(lang,'is_saline')} {option_label(lang,'is_saline',v['is_saline'])}"]
        for name in ('custom_kc','custom_root_depth','custom_p','greenhouse_et0','power_price','pump_power_kw','pump_productivity_m3h'):
            units={'custom_kc':'Kc','custom_root_depth':'Zr, m','custom_p':'p',
                   'greenhouse_et0':'ET0, mm/day','power_price':'₸/kWh','pump_power_kw':'kW','pump_productivity_m3h':'m³/h'}
            if v.get(name) is not None: labels.append(f"{units[name]}: {v[name]:g}")
        text+='\n\n'+'\n'.join(labels)
    def button(label,value):
        return InlineKeyboardButton(text=label, callback_data=f"plan:{data['token']}:{i}:{value}")
    rows=[[button(option_label(lang,key,value),value)] for value in ENUMS.get(key,[])]
    if key in ('pump','greenhouse_et0'): rows.append([button(phrase(lang,'skip' if key=='pump' else 'estimate'),'skip')])
    if key=='confirm': rows.append([button(phrase(lang,'calculate'),'calculate')])
    nav=[]
    if i: nav.append(button(phrase(lang,'back'),'back'))
    nav.append(button(phrase(lang,'cancel'),'cancel')); rows.append(nav)
    return text,InlineKeyboardMarkup(inline_keyboard=rows)


async def show_step(message, state, lang):
    data=await state.get_data(); text,markup=prompt(data,lang)
    # One editable prompt holds all wizard controls, rather than a new card per click.
    if data.get('prompt_id'):
        try:
            await message.bot.edit_message_text(text,chat_id=message.chat.id,message_id=data['prompt_id'],parse_mode=None,reply_markup=markup)
            return
        except Exception:
            pass
    sent=await message.answer(text,parse_mode=None,reply_markup=markup)
    await state.update_data(prompt_id=sent.message_id)


async def begin_plan(message: Message, state: FSMContext):
    # Explicitly leave saved AI mode; a planner response must not resume it later.
    from bot.handlers.agronomist import assistant
    from bot.services.agronomist import AIError
    try:
        await assistant.set_active(message.from_user.id,False)
    except AIError:
        pass
    previous_ui_id=(await state.get_data()).get('ai_ui_message_id')
    await state.clear()
    await state.set_state(ChatPlan.collecting)
    await state.update_data(token=secrets.token_hex(4),step=0,
                            prompt_id=previous_ui_id,
                            values={'balance_version':2,'area_unit':'hectare','lang':get_lang(message.from_user.id)})
    await show_step(message,state,get_lang(message.from_user.id))


async def cancel_plan(message: Message, state: FSMContext):
    data=await state.get_data()
    await state.clear()
    lang=get_lang(message.from_user.id)
    if data.get('prompt_id'):
        from bot.handlers.agronomist import AgronomistChat, assistant
        from bot.ai_i18n import ai_text
        try:
            await assistant.set_active(message.from_user.id,True)
            await state.set_state(AgronomistChat.active)
            await state.update_data(ai_ui_message_id=data['prompt_id'])
            await message.bot.edit_message_text(
                chat_id=message.chat.id,message_id=data['prompt_id'],
                text=phrase(lang,'cancelled'),parse_mode=None,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=ai_text(lang,'menu_button'),callback_data='ai_nav:menu')]]))
            return
        except Exception:
            await state.clear()
    await message.answer(phrase(lang,'cancelled'),parse_mode=None,reply_markup=get_main_reply_keyboard(lang))


async def plan_callback(callback: CallbackQuery, state: FSMContext):
    if not isinstance(callback.message,Message): return
    lang=get_lang(callback.from_user.id)
    msg=callback.message.model_copy(update={'from_user':callback.from_user}).as_(callback.bot)
    async with _finish_lock:
        data=await state.get_data()
        _,token,idx,value=callback.data.split(':',3)
        if (await state.get_state()!=ChatPlan.collecting.state or token!=data.get('token') or idx!=str(data.get('step'))):
            await callback.answer(phrase(lang,'stale')); return
        if value=='cancel':
            await callback.answer(); await cancel_plan(msg,state); return
        if value=='back':
            await state.update_data(step=max(0,data['step']-1))
            await callback.answer(); await show_step(msg,state,lang); return
        key=steps(data['values'])[data['step']]
        if key=='confirm' and value=='calculate':
            try: parse_field(data['values'])
            except BalanceInputError:
                await callback.answer(phrase(lang,'invalid'),show_alert=True); return
            await state.set_state(ChatPlan.calculating)
            await callback.answer()
            await callback.message.edit_text(phrase(lang,'working'),parse_mode=None,reply_markup=None)
        else:
            try: updates=accept_input(key,value,data['values'])
            except ValueError:
                await callback.answer(phrase(lang,'invalid')); return
            await state.update_data(values={**data['values'],**updates},step=data['step']+1)
            await callback.answer(); await show_step(msg,state,lang); return
    # Keep the shared handler's owner-scoped report/history/field persistence.
    await handle_field_payload(msg,state,data['values'])
    if data.get('prompt_id'):
        try: await msg.bot.delete_message(chat_id=msg.chat.id,message_id=data['prompt_id'])
        except Exception: pass
    await msg.answer('/ai · /plan',parse_mode=None,reply_markup=get_main_reply_keyboard(lang))


async def plan_input(message: Message, state: FSMContext):
    lang=get_lang(message.from_user.id); data=await state.get_data()
    key=steps(data['values'])[data['step']]
    raw=message.text or ''
    if key=='location' and message.location:
        raw=f"{message.location.latitude} {message.location.longitude}"
    if key in ENUMS:
        raw=next((value for value in ENUMS[key] if option_label(lang,key,value).casefold()==raw.casefold()),raw)
    try: updates=accept_input(key,raw,data['values'])
    except ValueError:
        await message.answer(phrase(lang,'invalid'),parse_mode=None); return
    await state.update_data(values={**data['values'],**updates},step=data['step']+1)
    await show_step(message,state,lang)


async def leave_plan_for_menu(message: Message,state: FSMContext):
    await state.clear()
    raise SkipHandler()


def register_chat_planner(router: Router):
    # Register ahead of AI's catch-all so wizard navigation never calls Gemini.
    router.message.register(begin_plan,Command('plan'))
    router.message.register(begin_plan,F.text.in_(set(PLAN_BUTTON.values())))
    router.callback_query.register(plan_callback,F.data.startswith('plan:'))
    router.message.register(cancel_plan,ChatPlan.collecting,Command('cancel','exit'))
    router.message.register(cancel_plan,ChatPlan.collecting,F.text.in_({'🔙 Назад','🔙 Артқа','🔙 Back'}))
    menu={t(lang,key) for lang in ('ru','kz','en')
          for key in ('btn_fields','btn_history','btn_more','btn_lang','btn_about','btn_help','btn_webapp')}
    menu.update(copy[key] for copy in AI_STRINGS.values()
                for key in ('button','photo_button','water_button','care_button','new_button','history_button'))
    router.message.register(leave_plan_for_menu,ChatPlan.collecting,
                            F.text.startswith('/') | F.text.in_(menu))
    router.message.register(plan_input,ChatPlan.collecting,
                            F.location | (F.text & ~F.text.startswith('/')),~F.web_app_data)
