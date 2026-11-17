// Jury demo: a fixed model scenario computed live by the production balance engine.
// Nothing is stored and no weather request is made, so it works offline and cannot pollute a user's fields.
import {parseField,calculate,SOILS,METHODS,VERSION,PUMP_MAX_HOURS_PER_DAY} from './balance.js';
import {tr,esc,fmt} from './i18n.js';
import {button,keyboard,back,APP_URL} from './ui.js';
import {language} from './i18n.js';

export const DEMO_FIELD={balance_version:2,crop:'wheat',soil_type:'loam',irrigation_type:'drip',area:1,area_unit:'hectare',
  day_of_growth:60,moisture_condition:'dry',pump_power_kw:22,pump_productivity_m3h:60,power_price:25};
export const DEMO_WEATHER={et0:5,rain:0};

export function demoCalculation() {
  const field=parseField(DEMO_FIELD),result=calculate(field,DEMO_WEATHER.et0,DEMO_WEATHER.rain);
  return {field,result};
}
const kz0=(n,d=1)=>fmt(n,d);  // single numeric formatter for all three languages

export function demoScreen(lang) {
  const {field,result:r}=demoCalculation();
  const decision={critical:tr(lang,'Полив нужен: запас влаги ниже порога','Суару қажет: ылғал қоры шектен төмен','Water now: moisture is below the threshold'),
    irrigate:tr(lang,'Сегодня нужен полив','Бүгін суару қажет','Irrigation is needed today'),
    deferred:tr(lang,'Сегодня можно не поливать','Бүгін суармаса болады','No irrigation needed today')}[r.status];
  const text=[
   `<b>${tr(lang,'ДЕМО · модельный сценарий','ДЕМО · модельдік сценарий','DEMO · model scenario')}</b>`,
   tr(lang,'Ничего вводить не нужно: поле и погода заданы заранее.','Ештеңе енгізу қажет емес: алқап пен ауа райы алдын ала берілген.','Nothing to enter: the field and weather are preset.'),
   '',
   `🌾 ${tr(lang,'Пшеница','Бидай','Wheat')} · 1 ha · ${tr(lang,'суглинок','саз балшық','loam')} · ${tr(lang,'капельный полив','тамшылатып суару','drip')}`,
   `${tr(lang,'День роста','Өсу күні','Growth day')}: ${field.day} · ET0 ${fmt(DEMO_WEATHER.et0)} mm/day · ${tr(lang,'осадки','жауын','rain')} 0 mm`,
   '',
   `<b>${esc(decision)}</b>`,
   `<b>${tr(lang,'Подать воды','Берілетін су','Apply water')}: ${kz0(r.gross_m3,0)} m³</b>`,
   `${tr(lang,'Насос','Сорғы','Pump')}: ${kz0(r.ai_time_hours)} h · ${kz0(r.cost,0)} ₸`,
   ...(r.irrigation_days>1?[`⚠️ ${tr(lang,`Насос подаёт не больше ${kz0(r.max_daily_m3,0)} м³ за ${PUMP_MAX_HOURS_PER_DAY} ч в сутки: полив разделён на ${r.irrigation_days} дн.`,`Сорғы ${PUMP_MAX_HOURS_PER_DAY} сағатта ${kz0(r.max_daily_m3,0)} м³-ден артық бермейді: суару ${r.irrigation_days} күнге бөлінді.`,`The pump delivers at most ${kz0(r.max_daily_m3,0)} m³ in ${PUMP_MAX_HOURS_PER_DAY} h a day: the watering is split over ${r.irrigation_days} days.`)}`]:[]),
   '',
   `<i>${tr(lang,'Это расчёт по модели, а не измерение на реальном поле.','Бұл нақты алқаптағы өлшеу емес, модель есебі.','This is a model calculation, not a measurement on a real field.')}</i>`
  ].join('\n');
  return {text,markup:keyboard([
   [button(tr(lang,'Как это посчитано','Бұл қалай есептелді','How it is calculated'),'demo:steps','primary')],
   [{text:tr(lang,'Рассчитать своё поле','Өз алқабыңызды есептеу','Calculate your own field'),web_app:{url:`${APP_URL}?lang=${language(lang)}`}}],
   back(lang)])};
}

export function demoSteps(lang) {
  const {field,result:r}=demoCalculation();
  const [fc,pwp]=SOILS[field.soil],[,eff]=[0,METHODS[field.method][1]];
  const l=(ru,kk,en)=>tr(lang,ru,kk,en);
  const text=[
   `<b>${l('Как это посчитано (FAO-56)','Бұл қалай есептелді (FAO-56)','How it is calculated (FAO-56)')}</b>`,
   '',
   `<b>1. TAW</b> = 1000 × (θfc − θwp) × Zr\n= 1000 × (${fmt(fc,2)} − ${fmt(pwp,2)}) × ${fmt(field.zr,2)} = <b>${fmt(r.taw)} mm</b>`,
   `<b>2. RAW</b> = p × TAW\n= ${fmt(field.p,2)} × ${fmt(r.taw)} = <b>${fmt(r.raw)} mm</b>`,
   `<b>3. ETc</b> = Ks × Kc × ET0\n= ${fmt(r.ks,2)} × ${fmt(field.kc,2)} × ${fmt(r.et0)} = <b>${fmt(r.etc)} mm</b>\n<i>Ks = 1: ${l('вчера запас ещё не был ниже RAW','кеше қор әлі RAW-дан төмен болмаған','yesterday depletion had not yet passed RAW')}</i>`,
   `<b>4. ${l('Дефицит','Тапшылық','Deficit')}</b> = ${l('вчера','кеше','yesterday')} + ETc − ${l('осадки','жауын','rain')}\n= ${fmt(field.yesterday)} + ${fmt(r.etc)} − ${fmt(r.peff)} = <b>${fmt(r.deficit)} mm</b>`,
   `<b>5. ${l('Решение','Шешім','Decision')}</b>: ${fmt(r.deficit)} ${r.deficit>r.raw?'>':'≤'} RAW ${fmt(r.raw)} mm → <b>${r.status==='critical'?l('запас ниже порога стресса — поливать сейчас','ылғал стресс шегінен төмен — қазір суару','below the stress limit — water now'):r.status==='irrigate'?l('поливать','суару','irrigate'):l('ждать','күту','wait')}</b>`,
   `<b>6. ${l('Объём','Көлем','Volume')}</b> = ${l('дефицит','тапшылық','deficit')} × 10 × ${l('площадь','аудан','area')} ÷ η\n= ${fmt(r.deficit)} × 10 × ${fmt(field.area_ha)} ÷ ${fmt(eff,2)} = <b>${fmt(r.gross_m3)} m³</b>`,
   `<b>7. ${l('Насос','Сорғы','Pump')}</b>: ${fmt(r.gross_m3)} ÷ ${fmt(field.pump_productivity_m3h,0)} m³/h = ${fmt(r.ai_time_hours)} h;\n${fmt(r.ai_time_hours)} h × ${fmt(field.pump_power_kw,0)} kW × ${fmt(field.power_price,0)} ₸ = <b>${fmt(r.cost,0)} ₸</b>`,
   '',
   `<i>${l('Параметры почвы и культуры — значения проекта, не местная калибровка. ET0 здесь задана вручную; в боте она берётся из Open-Meteo.','Топырақ пен дақыл параметрлері — жоба мәндері, жергілікті калибрлеу емес. ET0 мұнда қолмен берілген; ботта Open-Meteo-дан алынады.','Soil and crop parameters are project values, not a local calibration. ET0 is preset here; in the bot it comes from Open-Meteo.')}</i>`,
   VERSION
  ].join('\n');
  return {text,markup:keyboard([[button(l('‹ Демо','‹ Демо','‹ Demo'),'demo')],back(lang)])};
}
