// Plain-language setup texts kept apart from the generated planner-copy.js.
import {tr} from './i18n.js';
export const DEFAULTS={soil_type:'loam',moisture_condition:'normal',is_saline:'no',power_price:null,pump_power_kw:null,pump_productivity_m3h:null};
export const REFINE=['soil_type','moisture_condition','field_type','is_saline','pump'];
export const QUESTION={
  area:['Какой размер участка? Напишите, например: 6 соток, 600 м² или 0,06 га. Для прямоугольного участка можно написать длину и ширину в метрах: 20×30. Число без единицы считается гектарами.','Учаскенің ауданы қандай? Мысалы: 6 сотық, 600 м² немесе 0,06 га. Тік төртбұрышты учаске үшін метрмен ұзындығы мен енін жазыңыз: 20×30. Өлшем бірлігі көрсетілмесе, сан гектар деп алынады.','How big is the plot? Enter 6 sotkas, 600 m² or 0.06 ha. For a rectangular plot you can enter its length and width in metres: 20×30. A number without a unit means hectares.'],
  location:['Где участок? Если вы на нём, на телефоне нажмите скрепку в Telegram и отправьте текущую геопозицию. Если вы дома, найдите участок на карте и пришлите его координаты, например 47.12 51.88. Точка нужна, чтобы получить прогноз погоды.','Учаске қайда? Учаскеде болсаңыз, телефондағы Telegram-да қыстырғышты басып, ағымдағы орныңызды жіберіңіз. Үйде болсаңыз, учаскені картадан тауып, координаттарын жіберіңіз, мысалы 47.12 51.88. Бұл нүкте ауа райы болжамын алу үшін керек.','Where is the plot? If you are there, tap the paperclip in Telegram on your phone and send your current location. Otherwise, find the plot on a map and send its coordinates, for example 47.12 51.88. The bot uses the pin to fetch local weather.'],
  day_of_growth:['Если знаете дату посадки, напишите её, например 15.05. Можно написать и число дней с посадки.','Отырғызған күнді білсеңіз, жазыңыз, мысалы 15.05. Отырғызғаннан бері неше күн өткенін де жаза аласыз.','If you know the planting date, enter it, for example 15.05. You can also enter the number of days since planting.'],
  stage_pick:['Не помните дату? Выберите, как выглядит культура сейчас. Возраст будет приблизительным.','Күні есіңізде жоқ па? Дақылдың қазіргі кезеңін таңдаңыз. Жасы шамамен есептеледі.','Forgot the planting date? Pick what the crop looks like now. Its age will be approximate.'],
  growth_estimated:['Возраст приблизительный, выбран по стадии роста.','Дақылдың жасы өсу кезеңі бойынша шамамен алынды.','Crop age is approximate and was estimated from the growth stage.'],
  field_type:['Где растут растения? Для теплицы важно знать, растут ли корни в грунте и есть ли отопление. Для отдельных горшков этот расчёт не подходит.','Өсімдіктер қайда өседі? Жылыжайда тамырдың топырақта өсуі және жылыту жүйесінің болуы маңызды. Бұл есеп жеке құмыраларға жарамайды.','Where are the plants growing? In a greenhouse, soil versus substrate and heating matter. This calculation does not cover individual pots.'],
  heated_measurement:['Нужен показатель испарения внутри теплицы (ET₀). Если его измеряют в хозяйстве, спросите значение у агронома и введите в мм за сутки. Без него бот не выдаст совет по поливу.','Жылыжай ішіндегі эталондық булану көрсеткіші (ET₀) қажет. Шаруашылық оны өлшесе, агрономнан сұрап, тәулігіне мм мәнін енгізіңіз. Онсыз суару ұсынысы берілмейді.','If your farm has measured reference evapotranspiration (ET₀) inside this greenhouse, enter it in mm per day. The bot needs it to advise on a heated greenhouse.'],
  no_measurement:['У меня нет измерения','Өлшемім жоқ','I do not have a measurement'],
  soil_type_hint:['Приблизительная проверка: скатайте влажную землю в шнурок. Не скатывается — песок. Скатывается, но ломается — суглинок. Тонкий гладкий шнурок — глина. Если пропустите выбор, расчёт использует суглинок.','Шамамен тексеру үшін дымқыл топырақты жіпше етіп илеңіз. Иленбесе — құм. Иленіп, бірақ үзілсе — саздақ. Жіңішке тегіс жіпше шықса — саз. Таңдамасаңыз, есепте саздақ алынады.','A rough test: roll moist soil into a thread. It will not roll: sand. It rolls but breaks: loam. A thin smooth thread: clay. If you skip this choice, the calculation uses loam.'],
  assumed_title:['Мы предположили (можно уточнить)','Біз болжадық (нақтылауға болады)','We assumed (you can refine)'],
  refine:['Уточнить:','Нақтылау:','Refine:'],
  refining:['Уточнение','Нақтылау','Refinement'],
  done:['Готово: вернуться','Дайын: қайту','Done: go back']
};
export const q=(lang,key)=>tr(lang,...QUESTION[key]);
const MOIST={recent:['недавно поливали или был дождь','жақында суарылған немесе жаңбыр болған','recently watered or rain'],normal:['нормальная','қалыпты','normal'],dry:['сухая','құрғақ','dry']};
export const FIELD_LABELS={
  open:['Открытый участок','Ашық алқап','Open field'],
  unheated:['Теплица · грунт, без отопления','Жылыжай · топырақ, жылытылмайды','Greenhouse · soil, unheated'],
  heated:['Теплица · грунт, с отоплением','Жылыжай · топырақ, жылытылады','Greenhouse · soil, heated'],
  substrate:['Теплица · кокос, минвата или гидропоника','Жылыжай · кокос, минвата немесе гидропоника','Greenhouse · coco, rockwool or hydroponics']
};
export const STAGE_LABELS={
  initial:['Только взошли или приживаются','Жаңа көктеп шықты не жерсініп жатыр','Just sprouted or establishing'],
  development:['Активно растут, ряд ещё не закрылся','Белсенді өсуде, қатар арасы әлі ашық','Growing quickly, rows still open'],
  middle:['Куст или ряд уже разросся','Өсімдік өсті, қатар арасы жабылды','Full growth, rows have filled in'],
  late:['Созревают или листья стареют','Пісіп жатыр немесе жапырақтары солуда','Ripening or leaves are ageing']
};
export const fieldChoice=v=>v.field_type==='open'?'open':v.greenhouse_medium==='substrate'?'substrate':v.greenhouse_heated==='yes'?'heated':'unheated';
// What the bot will assume if the farmer does not refine anything. Every line names a value the farmer can still change.
export function assumedLines(lang,v,label) {
  const d={...DEFAULTS,...v},L=[];
  L.push(`${tr(lang,'Почва','Топырақ','Soil')}: ${label(lang,'soil_type',d.soil_type)}`);
  L.push(`${tr(lang,'Влажность сейчас','Қазіргі ылғал','Moisture now')}: ${tr(lang,...MOIST[d.moisture_condition])}`);
  L.push(`${tr(lang,'Засоление','Тұздану','Salinity')}: ${d.is_saline==='yes'?tr(lang,'есть (решает агроном)','бар (агроном шешеді)','yes (an agronomist decides)'):tr(lang,'не учтено','есепке алынбады','not included')}`);
  L.push(d.pump_power_kw===null||d.pump_power_kw===undefined?tr(lang,'Насос и тариф: не введены, стоимость не считается','Сорғы мен тариф: енгізілмеген, құны есептелмейді','Pump and tariff: not entered, cost is not calculated'):`${tr(lang,'Насос и тариф','Сорғы мен тариф','Pump and tariff')}: ${d.power_price} ₸/kWh, ${d.pump_power_kw} kW, ${d.pump_productivity_m3h} m³/h`);
  L.push(tr(lang,'Календарь стадий и коэффициенты: из каталога культур (FAO-56)','Даму кезеңдері мен коэффициенттер: дақыл каталогынан (FAO-56)','Stage calendar and coefficients: from the crop catalog (FAO-56)'));
  return L;
}
export const REFINE_LABEL={soil_type:['Почва','Топырақ','Soil'],moisture_condition:['Влажность','Ылғал','Moisture'],field_type:['Теплица / поле','Жылыжай / егістік','Greenhouse / field'],greenhouse_et0:['Измерение в теплице','Жылыжайдағы өлшем','Greenhouse measurement'],is_saline:['Засоление','Тұздану','Salinity'],pump:['Насос и тариф','Сорғы мен тариф','Pump and tariff']};
