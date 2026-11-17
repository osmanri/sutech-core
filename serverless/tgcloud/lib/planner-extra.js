// Texts of the short setup path ("five questions" + "We assumed"). Hand-written, kept apart from the generated planner-copy.js.
import {tr,t} from './i18n.js';
export const DEFAULTS={soil_type:'loam',moisture_condition:'normal',field_type:'open',is_saline:'no',power_price:null,pump_power_kw:null,pump_productivity_m3h:null};
export const REFINE=['soil_type','moisture_condition','field_type','is_saline','pump'];
export const QUESTION={
  day_of_growth:['Когда посадили? Напишите дату (например 15.05 или 15.05.2026) или число дней с посадки.','Қашан отырғыздыңыз? Күнін жазыңыз (мысалы 15.05 немесе 15.05.2026) немесе отырғызғаннан бергі күн санын.','When was it planted? Write the date (for example 15.05 or 15.05.2026) or the number of days since planting.'],
  soil_type_hint:['Приблизительная проверка: скатайте влажную землю в шнурок. Не скатывается: песок. Скатывается, но ломается: суглинок. Тонкий гладкий шнурок: глина. Если не уверены, оставьте суглинок: это самое частое.','Шамамен тексеру: дымқыл топырақты жіп қылып жалпайтыңыз. Домалақталмаса: құм. Домалақталады, бірақ сынады: саздақ. Жұқа тегіс жіп: саз. Сенімсіз болсаңыз, саздақты қалдырыңыз: ең жиі кездеседі.','A rough test: roll moist soil into a thread. It will not roll: sand. It rolls but breaks: loam. A thin smooth thread: clay. If unsure, keep loam: it is the most common.'],
  assumed_title:['Мы предположили (можно уточнить)','Біз болжадық (нақтылауға болады)','We assumed (you can refine)'],
  refine:['Уточнить:','Нақтылау:','Refine:'],
  refining:['Уточнение','Нақтылау','Refinement'],
  done:['Готово: вернуться','Дайын: қайту','Done: go back']
};
export const q=(lang,key)=>tr(lang,...QUESTION[key]);
const MOIST={recent:['недавно поливали или был дождь','жақында суарылған немесе жаңбыр болған','recently watered or rain'],normal:['нормальная','қалыпты','normal'],dry:['сухая','құрғақ','dry']};
const FIELD={open:['открытый грунт','ашық топырақ','open field'],greenhouse:['теплица','жылыжай','greenhouse']};
// What the bot will assume if the farmer does not refine anything. Every line names a value the farmer can still change.
export function assumedLines(lang,v,label) {
  const d={...DEFAULTS,...v},L=[];
  L.push(`${tr(lang,'Почва','Топырақ','Soil')}: ${label(lang,'soil_type',d.soil_type)}`);
  L.push(`${tr(lang,'Влажность сейчас','Қазіргі ылғал','Moisture now')}: ${tr(lang,...MOIST[d.moisture_condition])}`);
  L.push(`${tr(lang,'Где растёт','Қайда өседі','Where it grows')}: ${tr(lang,...FIELD[d.field_type])}`);
  L.push(`${tr(lang,'Засоление','Тұздану','Salinity')}: ${d.is_saline==='yes'?tr(lang,'есть (решает агроном)','бар (агроном шешеді)','yes (an agronomist decides)'):tr(lang,'нет','жоқ','none')}`);
  L.push(d.pump_power_kw===null||d.pump_power_kw===undefined?tr(lang,'Насос и тариф: не введены, стоимость не считается','Сорғы мен тариф: енгізілмеген, құны есептелмейді','Pump and tariff: not entered, cost is not calculated'):`${tr(lang,'Насос и тариф','Сорғы мен тариф','Pump and tariff')}: ${d.power_price} ₸/kWh, ${d.pump_power_kw} kW, ${d.pump_productivity_m3h} m³/h`);
  L.push(tr(lang,'Календарь стадий и коэффициенты: из каталога культур (FAO-56)','Даму кезеңдері мен коэффициенттер: дақыл каталогынан (FAO-56)','Stage calendar and coefficients: from the crop catalog (FAO-56)'));
  return L;
}
export const REFINE_LABEL={soil_type:['Почва','Топырақ','Soil'],moisture_condition:['Влажность','Ылғал','Moisture'],field_type:['Теплица / поле','Жылыжай / егістік','Greenhouse / field'],is_saline:['Засоление','Тұздану','Salinity'],pump:['Насос и тариф','Сорғы мен тариф','Pump and tariff']};
void t;
