// Su-Tech pitch deck, Canva edition: same slides as deck7.js, built only from objects Canva imports cleanly.
//   - every colour is a hex value and every font is named explicitly (Manrope bold / Inter), no theme references;
//   - no slide masters, placeholders, charts, tables, flipped lines, letter spacing or shape/image transparency:
//     transparency is baked into PNGs (prep_canva.py), charts are images or plain rectangles;
//   - photos and the dark background are ordinary full-slide images, so they can be swapped in Canva.
//   - no zero-size shapes: Canva rejects the whole file as damaged if a line has width or height 0.
// PowerPoint animations do not survive a Canva import; animate in Canva itself.
const pptxgen = require('pptxgenjs');
const nodePath = require('path');
const OUT = process.env.OUT || 'Su-Tech-Canva.pptx';
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'Su-Tech — умный полив';
pres.author = 'Осман Толобек';

const WHITE = 'FFFFFF', DEEP = '00382A', LIME = '81CA2A', PALE = 'B9E07A', MUTED = '8FAE9F', RED = 'E53935';
const SEP = '4F7466';           // white at ~72% transparency over the dark green, as a solid colour
const HEAD = 'Manrope', BODY = 'Inter';
const TOTAL = 16;
let shown = 0, uid = 0;

function T(s, text, o) {
  const head = o.head; delete o.head;
  s.addText(text, Object.assign({ margin: 0, valign: 'top', isTextBox: true, color: WHITE, fontSize: 14, fontFace: head ? HEAD : BODY, bold: !!head }, o));
}
const icon = (s, n, c, x, y, size) => s.addImage({ path: `m/${n}-${c}.png`, x, y, w: size, h: size, altText: '' });
function hline(s, x1, x2, y, color = SEP, width = 1) { s.addShape(pres.shapes.LINE, { x: x1, y, w: x2 - x1, h: 0.001, line: { color, width } }); }
function vline(s, x, y1, y2, color = SEP, width = 1) { s.addShape(pres.shapes.LINE, { x, y: y1, w: 0.001, h: y2 - y1, line: { color, width } }); }
function dashed(s, x, y, w, h, label, round) {
  s.addShape(round ? pres.shapes.OVAL : pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: '0D3D2E' }, line: { color: PALE, width: 1.25, dashType: 'dash' } });
  T(s, label, { x, y: y + h / 2 - 0.18, w, h: 0.36, align: 'center', valign: 'middle', fontSize: 12, color: PALE });
}
function slide(o) {
  const s = pres.addSlide();
  shown++;
  s.background = { color: '002A20' };
  s.addImage({ path: o.photo ? `m/full-${o.photo}.jpg` : 'm/base.jpg', x: 0, y: 0, w: 13.333, h: 7.5, altText: '' });
  const [ax, ay, aw, bx, by, bw] = o.glow;
  s.addImage({ path: 'm/glow-lime.png', x: ax, y: ay, w: aw, h: aw, altText: '' });
  s.addImage({ path: 'm/glow-green.png', x: bx, y: by, w: bw, h: bw, altText: '' });
  const sets = [['drop-half', 'thermometer', 'sun'], ['waves', 'leaf', 'drop'], ['sparkle', 'drop', 'leaf'], ['wind', 'cloud-rain', 'drop'],
    ['map-trifold', 'leaf', 'drop'], ['flask', 'drop', 'leaf'], ['chart-line-up', 'drop', 'leaf'], ['warning-circle', 'drop', 'leaf'],
    ['tractor', 'grains', 'drop'], ['scales', 'leaf', 'drop'], ['users-three', 'leaf', 'drop'], ['calendar-check', 'leaf', 'drop'], ['cpu', 'lightning', 'drop']];
  const [n1, n2, n3] = sets[(shown + uid++) % sets.length];
  const put = (n, k, x, y, w) => s.addImage({ path: `c/d-${n}-${k}.png`, x, y, w, h: w, altText: '' });
  if (!o.blank) {
    put(n1, 'big', 11.9, 0, 1.25); put(n2, 'small', 11.2, 0.95, 0.4); put(n3, 'small', 12.6, 1.3, 0.34);
    s.addImage({ path: 'c/dots.png', x: 0.6, y: 6.5, w: 1.45, h: 0.9, altText: '' });
  } else {
    put(n1, 'big', 11.9, 5.6, 1.25); put(n2, 'small', 11.1, 6.45, 0.4);
    s.addImage({ path: 'c/dots.png', x: 11.2, y: 0.95, w: 1.45, h: 0.9, altText: '' });
  }
  hline(s, 0.6, 12.73, 7.135, '2B5546', 2);
  s._after = () => {
    const L = o.logo || { x: 0.6, y: 0.36, d: 0.52 };
    s.addShape(pres.shapes.OVAL, { x: L.x, y: L.y, w: L.d, h: L.d, fill: { color: WHITE }, line: { color: WHITE, width: 0 } });
    s.addImage({ path: 'm/logo.png', x: L.x + L.d * 0.14, y: L.y + L.d * 0.14, w: L.d * 0.72, h: L.d * 0.72, altText: 'Логотип Su-Tech' });
    if (!o.logo) T(s, 'Su-Tech', { x: 1.24, y: 0.36, w: 2, h: 0.52, valign: 'middle', fontSize: 15, head: true });
    T(s, o.appendix ? o.section.toUpperCase() : `${String(shown).padStart(2, '0')} / ${TOTAL}  ·  ${o.section.toUpperCase()}`, { x: 7.7, y: 0.36, w: 5.03, h: 0.52, align: 'right', valign: 'middle', fontSize: 10.5, bold: true, color: PALE });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 7.105, w: Math.max(0.2, 12.13 * Math.min(shown, TOTAL) / TOTAL), h: 0.06, fill: { color: LIME }, line: { color: LIME, width: 0 } });
  };
  return s;
}
const title = (s, a, b) => T(s, [{ text: a.toUpperCase() }, { text: (b || '').toUpperCase(), options: { color: LIME } }],
  { x: 0.6, y: 1.0, w: 12.13, h: 0.85, fontSize: 38, head: true });
const credit = (s, t, y = 6.82) => T(s, t, { x: 0.6, y, w: 12, h: 0.22, fontSize: 8.5, color: MUTED });

// 1. ПРОБЛЕМА ВОДЫ
let s = slide({ section: 'Проблема', blank: true, photo: 'aral', glow: [-2.8, -3.0, 7, 9, 4.2, 6] });
{
  const TW = 8.3, BADGE = 1.1, GAP = 0.25, TX = (13.333 - (TW + GAP + BADGE)) / 2;
  T(s, [{ text: 'ПРОБЛЕМА ' }, { text: 'ВОДЫ', options: { color: RED } }], { x: TX, y: 1.0, w: TW, h: 1.2, valign: 'middle', fontSize: 64, head: true });
  // blue double-drop icon (Flaticon), centred where the old red badge was; no badge behind it
  s.addImage({ path: nodePath.join(__dirname, 'icons', 'drops-duo.png'), x: TX + TW + GAP - 0.05, y: 1.0, w: 1.2, h: 1.2, altText: '' });
}
[['72%', 'farm', 'пресной воды мира забирает сельское хозяйство', 'ФАО, AQUASTAT 2025'],
 ['до 50%', 'drop-half', 'воды в Казахстане теряется по дороге — в оросительных каналах', 'Astana Times, январь 2026'],
 ['−78%', 'grains', 'посевов риса в Туркестанской области: с 16 000 до 3 500 га', 'Dunyo.info, январь 2026']].forEach(([num, ic, txt, from], i) => {
  const x = 0.75 + i * 4.1;
  icon(s, ic, 'white', x, 2.75, 0.95);
  T(s, num, { x, y: 3.85, w: 3.6, h: 0.95, fontSize: 46, color: LIME, valign: 'middle', head: true });
  T(s, txt, { x, y: 4.85, w: 3.5, h: 1.2, fontSize: 17, bold: true });
  T(s, from, { x, y: 6.1, w: 3.5, h: 0.25, fontSize: 10, color: PALE });
  if (i < 2) vline(s, x + 3.8, 2.75, 6.3);
});
T(s, 'Осман Толобек · [школа, город] · Samsung Solve for Tomorrow', { x: 0.6, y: 6.55, w: 9, h: 0.28, fontSize: 12.5, color: PALE });
credit(s, 'Фото: «Graveyard of Ships (Aral sea)», Mirfayzbek Abdullayev, Wikimedia Commons, CC0 · Иконка капель: Flaticon', 6.86);
s._after();
s.addNotes('Здравствуйте! Меня зовут Осман Толобек, мой проект — Su-Tech. Это Аральское море: корабли стоят посреди пустыни. Сельское хозяйство забирает 72 процента пресной воды мира. В Казахстане до половины воды теряется ещё в каналах. В 2026 году ввели лимиты, посевы риса в Туркестанской области сокращают на 78 процентов.');

// 2. КАЖДЫЙ КУБОМЕТР НА СЧЕТУ
s = slide({ section: 'Проблема', glow: [7.6, -2.6, 7.5, -2.4, 3.4, 6.5] });
title(s, 'Каждый кубометр ', 'на счету');
T(s, '3,8 млрд м³', { x: 0.6, y: 2.2, w: 4.6, h: 0.8, fontSize: 36, color: LIME, valign: 'middle', head: true });
T(s, 'лимит воды на 2026 год для всей Туркестанской области', { x: 0.6, y: 3.05, w: 3.9, h: 0.9, fontSize: 15, bold: true });
T(s, 'Times of Central Asia, 2026', { x: 0.6, y: 4.0, w: 4, h: 0.25, fontSize: 10, color: PALE });
s.addImage({ path: 'c/donut-72.png', x: 7.0, y: 1.95, w: 2.65, h: 2.65, altText: 'Кольцевая диаграмма: 72% сельское хозяйство, 28% промышленность и быт' });
T(s, '72%', { x: 7.0, y: 2.95, w: 2.65, h: 0.65, align: 'center', valign: 'middle', fontSize: 24, color: LIME, head: true });
T(s, [{ text: 'сельское хозяйство', options: { breakLine: true } }, { text: '72%', options: { bold: true, fontSize: 18, color: LIME } }], { x: 4.5, y: 3.55, w: 2.35, h: 0.7, fontSize: 13, align: 'right' });
T(s, [{ text: 'промышленность и быт', options: { breakLine: true } }, { text: '28%', options: { bold: true, fontSize: 18 } }], { x: 9.85, y: 2.1, w: 2.9, h: 0.7, fontSize: 13 });
T(s, 'пресная вода мира · ФАО, 2025', { x: 9.85, y: 4.2, w: 2.9, h: 0.25, fontSize: 10, color: PALE });
hline(s, 4.7, 12.73, 4.75, '5E8072', 1.25);
vline(s, 8.9, 4.75, 6.85, '5E8072', 1.25);
s.addImage({ path: 'c/pie-50.png', x: 5.85, y: 4.95, w: 1.9, h: 1.9, altText: 'Круговая диаграмма: до 50% воды теряется в каналах' });
T(s, [{ text: 'теряется в каналах', options: { breakLine: true } }, { text: 'до 50%', options: { bold: true, fontSize: 18, color: 'FF8A80' } }], { x: 3.0, y: 5.2, w: 2.75, h: 0.7, fontSize: 13, align: 'right' });
T(s, [{ text: 'доходит до поля', options: { breakLine: true } }, { text: '50%', options: { bold: true, fontSize: 18 } }], { x: 3.0, y: 6.0, w: 2.75, h: 0.7, fontSize: 13, align: 'right' });
s.addShape(pres.shapes.OVAL, { x: 9.25, y: 5.15, w: 0.9, h: 0.9, fill: { color: LIME }, line: { color: LIME, width: 0 } });
s.addImage({ path: 'm/drop-white.png', x: 9.43, y: 5.33, w: 0.54, h: 0.54, altText: '' });
T(s, '3 940 м³', { x: 10.35, y: 5.05, w: 2.6, h: 0.7, fontSize: 26, valign: 'middle', head: true });
T(s, 'с гектара уходит глубже корней — даже при лучшем графике · модель FAO-56', { x: 10.35, y: 5.8, w: 2.4, h: 1.0, fontSize: 11, color: PALE });
s._after();
s.addNotes('Вопрос залу: сколько воды уходит в землю зря? График полива не знает погоды, его делают с запасом, и после дождя вода уходит глубже корней. Даже при лучшем графике это почти четыре тысячи кубометров с гектара за сезон. Каждый кубометр, дошедший до поля, нужно лить точно.');

// 3. SU-TECH
s = slide({ section: 'Решение', blank: true, photo: 'canal', glow: [-1.2, 0.6, 7.2, 7.5, -3.2, 8], logo: { x: 0.9, y: 1.85, d: 4.1 } });
T(s, 'SU-TECH', { x: 5.45, y: 1.45, w: 7.6, h: 1.5, valign: 'middle', fontSize: 84, color: LIME, head: true });
T(s, '— Telegram-бот, который каждый день по погоде поля считает, нужно ли поливать, сколько воды подать и сколько стоит работа насоса.',
  { x: 5.5, y: 3.1, w: 7.2, h: 1.95, fontSize: 22, bold: true, lineSpacingMultiple: 1.1 });
[['plant', 'Без датчиков', 5.5, 2.2], ['device-mobile', 'Нужен только телефон', 7.95, 3.1], ['translate', 'RU · ҚАЗ · EN', 11.15, 1.9]].forEach(([ic, t, x, w], i) => {
  icon(s, ic, 'lime', x, 5.45, 0.38);
  T(s, t, { x: x + 0.5, y: 5.45, w: w - 0.4, h: 0.38, valign: 'middle', fontSize: 14, bold: true });
  if (i) vline(s, x - 0.25, 5.4, 5.9);
});
credit(s, 'Фото: Benoît Prieur, Wikimedia Commons, CC0');
s._after();
s.addNotes('Su-Tech — агроном в кармане. Ничего не нужно покупать: открываешь бота в Telegram и отмечаешь поле. Бот отвечает на три вопроса: поливать ли сегодня, сколько воды и сколько это стоит.');

// 4. ИЗ ЧЕГО СОСТОИТ
s = slide({ section: 'Решение', glow: [3.2, 2.6, 7, -3, -2.5, 6.5] });
title(s, 'Из чего состоит ', 'Su-Tech');
[['Arduino Uno и реле', 'мозг стенда: включает насос'], ['Помпа и расходомер', 'подаёт и считает воду'],
 ['Весы HX711', 'вес горшка = сколько испарилось'], ['Telegram-бот', 'откройте по QR-коду']].forEach(([t, d], i) => {
  const x = 0.6 + i * 3.1;
  if (i < 3) dashed(s, x, 2.05, 2.8, 3.75, 'фото');
  else {
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.05, w: 2.8, h: 3.75, fill: { color: WHITE }, line: { color: WHITE, width: 0 } });
    s.addImage({ path: 'm/qr-demo.png', x: x + 0.2, y: 2.7, w: 2.4, h: 2.4, altText: 'QR-код: t.me/Su_Tech_bot, демо-режим' });
  }
  T(s, t, { x, y: 5.98, w: 2.85, h: 0.4, fontSize: 16, bold: true });
  T(s, d, { x, y: 6.4, w: 2.85, h: 0.4, fontSize: 11.5, color: PALE });
  if (i < 3) vline(s, x + 2.95, 2.05, 6.8);
});
s._after();
s.addNotes('Из чего состоит проект. Стенд на Arduino: реле и помпа, расходомер, весы под горшком. И сам бот — его можно открыть по QR-коду прямо сейчас.');

// 5. ВСЁ В ОДНОМ ЧАТЕ
s = slide({ section: 'Решение', photo: 'green', glow: [0.2, 1.6, 6.5, 7.2, 2.8, 7] });
title(s, 'Всё в одном ', 'чате');
s.addImage({ path: 'm/phone-bot.png', x: 0.85, y: 2.0, w: 2.3, h: 4.84, altText: 'Чат с ботом Su-Tech' });
s.addImage({ path: 'm/phone-mini.png', x: 3.45, y: 2.0, w: 2.3, h: 4.84, altText: 'Mini App Su-Tech' });
[['chat-circle-text', 'Совет приходит сообщением', 'каждый день, прямо в Telegram'], ['map-trifold', 'Поле на спутниковой карте', 'отмечается пальцем, площадь считается сама'],
 ['plant', 'Культура, почва, насос', 'хлопок, кукуруза, пшеница и другие'], ['translate', 'Три языка', 'русский, қазақша, English'],
 ['robot', 'ИИ-агроном', 'отвечает на вопросы и смотрит фото листьев']].forEach(([ic, t, d], i) => {
  const y = 2.0 + i * 0.97;
  icon(s, ic, 'lime', 6.5, y + 0.1, 0.55);
  T(s, t, { x: 7.3, y: y + 0.04, w: 5.4, h: 0.4, fontSize: 18, bold: true });
  T(s, d, { x: 7.3, y: y + 0.46, w: 5.4, h: 0.32, fontSize: 12.5, color: PALE });
  if (i < 4) hline(s, 6.5, 12.73, y + 0.9);
});
credit(s, 'Фото: Alabama Extension, Wikimedia Commons, CC0', 6.9);
s._after();
s.addNotes('Так это выглядит: слева сам бот, справа Mini App с полем на спутниковой карте. Три языка, ИИ-агроном. Демо для вас — по QR-коду.');

// 6. MINI APP КРУПНО — straight leader lines only
s = slide({ section: 'Решение', glow: [0.4, 1.2, 7.5, 8.4, 3.6, 6] });
title(s, 'Mini App ', 'крупно');
{
  const PX = 2.0, PY = 1.85, PW = 2.45, k = PW / 380;
  s.addImage({ path: 'm/phone-mini.png', x: PX, y: PY, w: PW, h: 800 * k, altText: 'Mini App Su-Tech крупно' });
  [['Три языка: RU · ҚАЗ · EN', 233, 187], ['Настроить поле за минуту', 120, 453], ['Вкладки: карта, параметры, расчёт', 187, 536],
   ['Поле на спутниковой карте', 133, 607], ['Город по поиску или GPS', 293, 724]].forEach(([t, cx, cy]) => {
    const px = PX + cx * k, py = PY + cy * k;
    hline(s, px, 6.95, py, LIME, 1.25);
    s.addShape(pres.shapes.OVAL, { x: px - 0.07, y: py - 0.07, w: 0.14, h: 0.14, fill: { color: LIME }, line: { color: WHITE, width: 1 } });
    T(s, t, { x: 7.1, y: py - 0.22, w: 5.7, h: 0.44, valign: 'middle', fontSize: 18, bold: true });
  });
}
s._after();
s.addNotes('Mini App внутри Telegram: три языка, поле настраивается за минуту, участок отмечается на спутниковой карте, город — поиском или по GPS.');

// 7. ПЕРВЫЙ ЭКСПЕРИМЕНТ
s = slide({ section: 'Доказательства', glow: [-2.8, 2.2, 6.5, 6.5, -2.8, 7.5] });
title(s, 'Первый ', 'эксперимент');
dashed(s, 0.6, 2.0, 3.75, 4.75, 'фото стенда');
[['Место', '[школа, кабинет]'], ['Срок', '[4–6 недель, даты]'], ['Горшки', '12 — 6 по Su-Tech, 6 по графику'], ['Измеряю', 'вес горшка каждый день'], ['Результат', '[__%] меньше воды']].forEach(([k, v], i) => {
  const y = 2.0 + i * 0.95;
  hline(s, 4.7, 12.73, y);
  T(s, k.toUpperCase(), { x: 4.7, y, w: 1.9, h: 0.95, valign: 'middle', fontSize: 11, bold: true, color: LIME });
  T(s, v, { x: 6.7, y, w: 6, h: 0.95, valign: 'middle', fontSize: 21, bold: true, color: i === 4 ? LIME : WHITE });
});
hline(s, 4.7, 12.73, 6.75);
s._after();
s.addNotes('Модель нужно проверить на настоящих растениях. Я собрал стенд на Arduino. Двенадцать горшков делятся по жребию на две группы. Каждый день весы показывают, сколько воды растение испарило на самом деле, и я сравниваю это с расчётом бота. [Здесь будет результат опыта.]');

// 8. РЕЗУЛЬТАТ МОДЕЛИ — bar chart from rectangles
s = slide({ section: 'Доказательства', photo: 'fields', glow: [-2.4, -1.2, 8, 7.8, 3.4, 6.5] });
title(s, 'Результат ', 'модели');
T(s, '−15–28%', { x: 0.6, y: 1.95, w: 6.0, h: 1.55, valign: 'middle', fontSize: 80, color: LIME, head: true });
T(s, 'воды при том же урожае', { x: 0.6, y: 3.55, w: 5.6, h: 0.5, fontSize: 22, bold: true });
['25 из 25 сезонов в пользу Su-Tech', 'худший сезон: 9–20%', '2 почвы × 3 даты посева: 14–42%'].forEach((t, i) => {
  const y = 4.3 + i * 0.62;
  icon(s, 'check-circle', 'lime', 0.6, y + 0.06, 0.34);
  T(s, t, { x: 1.1, y, w: 4.8, h: 0.46, valign: 'middle', fontSize: 15, bold: true });
});
T(s, 'Против лучшего возможного графика · модель FAO-56, погода NASA POWER, 5 регионов × 5 сезонов · не полевое измерение', { x: 0.6, y: 6.3, w: 5.5, h: 0.5, fontSize: 9.5, color: PALE });
T(s, 'ВОДА ЗА СЕЗОН, м³/га', { x: 6.75, y: 2.0, w: 5.8, h: 0.3, fontSize: 10.5, bold: true, color: PALE });
{
  s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 2.45, w: 0.22, h: 0.22, fill: { color: LIME }, line: { color: LIME, width: 0 } });
  T(s, 'Su-Tech', { x: 7.1, y: 2.4, w: 1.4, h: 0.32, valign: 'middle', fontSize: 11 });
  s.addShape(pres.shapes.RECTANGLE, { x: 8.6, y: 2.45, w: 0.22, h: 0.22, fill: { color: 'DCEBD3' }, line: { color: 'DCEBD3', width: 0 } });
  T(s, 'Лучший график', { x: 8.9, y: 2.4, w: 2.2, h: 0.32, valign: 'middle', fontSize: 11 });
  const data = [['Хлопок, капля', 11321, 15117], ['Хлопок, борозды', 19751, 27600], ['Кукуруза, капля', 9039, 10709], ['Кукуруза, борозды', 15781, 19525]];
  const base = 6.2, maxH = 3.0, max = 27600, gw = 1.5, bw = 0.5;
  const fmt = v => String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  data.forEach(([lab, a, b], i) => {
    const gx = 6.8 + i * gw;
    [[a, LIME, 0], [b, 'DCEBD3', bw + 0.05]].forEach(([v, col, off]) => {
      const h = maxH * v / max;
      s.addShape(pres.shapes.RECTANGLE, { x: gx + off, y: base - h, w: bw, h, fill: { color: col }, line: { color: col, width: 0 } });
      T(s, fmt(v), { x: gx + off - 0.2, y: base - h - 0.28, w: bw + 0.4, h: 0.25, align: 'center', fontSize: 9 });
    });
    T(s, lab, { x: gx - 0.1, y: base + 0.08, w: 1.25, h: 0.5, align: 'center', fontSize: 10 });
  });
  hline(s, 6.75, 12.8, base, '5E8072', 1);
}
credit(s, 'Фото: PSSP, «Irrigation canals of Faisalabad», CC BY 2.0, Wikimedia Commons', 6.88);
s._after();
s.addNotes('Главный результат. Su-Tech сравнивается не с плохим графиком, а с лучшим возможным: урожай не ниже 98 процентов. Даже против него Su-Tech тратит на 15–28 процентов меньше воды — в каждом из 25 сезонов. Честно: это компьютерная модель на реальной погоде, поэтому идёт эксперимент.');

// 9. ПОЛЬЗА
s = slide({ section: 'Доказательства', glow: [-2.6, -2.2, 7.5, 7.6, 3.0, 6.5] });
title(s, 'В чём ', 'польза');
[['drop', '−3 800 м³', 'воды с гектара за сезон при том же урожае', 'хлопок, капля: 11 321 вместо 15 117 м³/га'], ['coins', '≈35 000 ₸', 'за электричество насоса с гектара за сезон', 'пример: насос 22 кВт, 60 м³/ч, 25 ₸/кВт·ч'], ['chart-line-up', '100%', 'урожая вместо 84–90% у графика с той же водой', '0 дней стресса против 38–65']].forEach(([ic, num, txt, note], i) => {
  const x = 0.75 + i * 4.1;
  icon(s, ic, 'lime', x, 2.0, 0.6);
  T(s, num, { x, y: 2.7, w: 3.75, h: 0.9, valign: 'middle', fontSize: 40, color: LIME, head: true });
  T(s, txt, { x, y: 3.65, w: 3.5, h: 0.75, fontSize: 15, bold: true });
  T(s, note, { x, y: 4.45, w: 3.5, h: 0.45, fontSize: 10.5, color: PALE });
  if (i < 2) vline(s, x + 3.8, 2.0, 4.9);
});
hline(s, 0.6, 12.73, 5.2);
[['farm', 'Фермеру', 'меньше счёт за насос, урожай не страдает'], ['users-three', 'Акимату', 'проще уложиться в лимиты воды 2026 года'], ['plant', 'Природе', 'меньше воды из рек, меньше уходит в глубину']].forEach(([ic, h, d], i) => {
  const x = 0.75 + i * 4.1;
  icon(s, ic, 'white', x, 5.45, 0.42);
  T(s, [{ text: h, options: { bold: true, color: LIME, breakLine: true } }, { text: d }], { x: x + 0.6, y: 5.38, w: 3.25, h: 0.8, fontSize: 12.5 });
});
T(s, 'Модель FAO-56 на реальной погоде, а не измерение на поле · сравнение с лучшим графиком при одинаковом урожае', { x: 0.6, y: 6.55, w: 12.1, h: 0.25, fontSize: 9.5, color: PALE });
s._after();
s.addNotes('В чём польза. Первое: при том же урожае Su-Tech тратит меньше воды — для хлопка на капле это около 3 800 кубометров с гектара за сезон, и насосу не нужно их качать: при обычном насосе это примерно 35 тысяч тенге за электричество с гектара. Второе: если фермер поливает по средней норме, но не по погоде, Su-Tech даёт не экономию, а урожай — сто процентов вместо 84–90. Третье: при лимитах воды сэкономленные кубометры можно отдать другому полю. Всё это модель на реальной погоде, поэтому идёт опыт.');

// 9. СЛАБОЕ МЕСТО
s = slide({ section: 'Доказательства', blank: true, photo: 'split', glow: [6.0, 1.0, 4, 6.2, 1.2, 4] });
T(s, [{ text: 'СЛАБОЕ МЕСТО ' }, { text: 'И РЕШЕНИЕ', options: { color: LIME } }], { x: 0.6, y: 1.0, w: 12.13, h: 0.85, fontSize: 38, head: true });
icon(s, 'warning', 'white', 0.75, 2.2, 0.5);
T(s, 'Прогноз всё время занижает испарение на 20%', { x: 1.45, y: 2.2, w: 4.6, h: 0.5, valign: 'middle', fontSize: 14, bold: true, color: PALE });
T(s, '73', { x: 0.75, y: 2.9, w: 5.2, h: 2.3, valign: 'middle', fontSize: 150, head: true });
T(s, 'дня стресса растений за сезон', { x: 0.75, y: 5.3, w: 5.2, h: 0.5, fontSize: 20, bold: true });
s.addShape(pres.shapes.OVAL, { x: 6.29, y: 4.0, w: 0.75, h: 0.75, fill: { color: LIME }, line: { color: LIME, width: 0 } });
icon(s, 'arrow-right', 'deep', 6.465, 4.175, 0.4);
icon(s, 'check-circle', 'lime', 7.45, 2.2, 0.5);
T(s, 'То же + кнопка «сухо / нормально / влажно» раз в неделю', { x: 8.15, y: 2.2, w: 4.55, h: 0.5, valign: 'middle', fontSize: 14, bold: true, color: PALE });
T(s, '0', { x: 7.45, y: 2.9, w: 5.2, h: 2.3, valign: 'middle', fontSize: 150, color: LIME, head: true });
T(s, 'дней стресса · экономия 14–17%', { x: 7.45, y: 5.3, w: 5.25, h: 0.5, fontSize: 20, bold: true });
T(s, 'Случайные ошибки до ±30%, неучтённые дожди, неверная почва — 0 дней стресса · хлопок, модель', { x: 0.6, y: 6.55, w: 12.1, h: 0.25, fontSize: 9.5, color: PALE });
credit(s, 'Фото: Wilfredor и Alabama Extension, Wikimedia Commons, CC0', 6.86);
s._after();
s.addNotes('Я специально искал, где модель ломается. Случайные ошибки ей не страшны. А если прогноз всё время занижает испарение, ошибка копится — 73 дня стресса за сезон. Решение — одна кнопка: раз в неделю фермер отвечает, сухая ли почва. Стресс исчезает, экономия остаётся. Эта кнопка уже есть в боте.');

// 10. ФИНАНСЫ И РЫНОК
s = slide({ section: 'Бизнес', photo: 'steppe', glow: [-2.6, 2.6, 7, 7, -3.2, 7.5] });
title(s, 'Финансы ', 'и рынок');
vline(s, 6.67, 2.1, 6.6);
hline(s, 0.6, 12.73, 4.35);
[['Стоимость стенда (MVP)', '[__ ₸]', null, 'Arduino, помпа, расходомер, весы, датчики', LIME],
 ['Цена для фермера', '0 ₸', null, 'нужен только Telegram', LIME],
 ['Модель заработка', 'Freemium', 'handshake', 'расчёт полива — 0 ₸ · PRO $10/мес: ИИ-агроном по фото · комплект автоматики насоса — $100', WHITE],
 ['Рынок', '702 300 га', 'farm', 'уже на водосбережении (1 сен 2026) · цель — 1,3 млн га к 2030 · Astana Times', WHITE]].forEach(([k, v, ic, d, col], i) => {
  const x = i % 2 ? 7.05 : 0.8, y = i < 2 ? 2.2 : 4.6;
  T(s, k.toUpperCase(), { x, y, w: 5.4, h: 0.3, fontSize: 10.5, bold: true, color: PALE });
  T(s, v, { x, y: y + 0.38, w: 4.5, h: 1.0, valign: 'middle', fontSize: 46, color: col, head: true });
  if (ic) icon(s, ic, 'lime', x + 4.6, y + 0.5, 0.75);
  T(s, d, { x, y: y + 1.45, w: 5.4, h: 0.55, fontSize: 12, color: PALE });
});
credit(s, 'Фото: Wikideas1, Wikimedia Commons, CC0', 6.88);
s._after();
s.addNotes('Финансы. Стенд стоил [сумма]. Фермеру Su-Tech бесплатен — нужен только Telegram. Модель заработка — freemium: расчёт полива бесплатный, PRO за 10 долларов в месяц — ИИ-агроном по фото, и комплект автоматики насоса за 100 долларов. Рынок: 702 тысячи гектаров уже на водосберегающих технологиях, к 2030 году цель — 1,3 миллиона.');

// 11. VS КОНКУРЕНТЫ — table drawn from rectangles and text
s = slide({ section: 'Бизнес', glow: [7.4, 2.8, 7, -2.2, -2.8, 6.5] });
title(s, 'Su-Tech ', 'vs конкуренты');
{
  const X = 0.6, Y = 2.05, colW = [4.73, 1.85, 1.85, 1.85, 1.85], hdrH = 0.65, rowH = 0.78;
  const xs = colW.reduce((a, w, i) => a.concat(a[i] + w), [X]);
  const rows = [['Su-Tech', '+++-', true], ['НИИ земледелия: датчики и метеостанция', '--++', false],
    ['CropX: датчики в почве, подписка', '--++', false], ['CROPWAT ФАО: программа для агронома', '++--', false]];
  s.addShape(pres.shapes.RECTANGLE, { x: X, y: Y, w: 12.13, h: hdrH, fill: { color: LIME }, line: { color: LIME, width: 0 } });
  ['Решение', 'без датчиков', 'бесплатно для фермера', 'совет каждый день', 'проверено на поле'].forEach((h, i) =>
    T(s, h, { x: xs[i] + 0.14, y: Y, w: colW[i] - 0.28, h: hdrH, align: i ? 'center' : 'left', valign: 'middle', fontSize: 13, bold: true, color: DEEP }));
  rows.forEach(([name, marks, hl], r) => {
    const y = Y + hdrH + r * rowH;
    if (hl) s.addShape(pres.shapes.RECTANGLE, { x: X, y, w: 12.13, h: rowH, fill: { color: '0E5A3C' }, line: { color: '0E5A3C', width: 0 } });
    T(s, name, { x: X + 0.14, y, w: colW[0] - 0.28, h: rowH, valign: 'middle', fontSize: hl ? 18 : 14, bold: true, color: hl ? LIME : WHITE });
    [...marks].forEach((m, c) =>
      T(s, m === '+' ? '+' : '−', { x: xs[c + 1], y, w: colW[c + 1], h: rowH, align: 'center', valign: 'middle', fontSize: 28, color: m === '+' ? LIME : MUTED, head: true }));
    hline(s, X, X + 12.13, y + rowH, '3E7A62', 1);
  });
  xs.slice(1, -1).forEach(x => vline(s, x, Y + hdrH, Y + hdrH + rows.length * rowH, '3E7A62', 1));
}
T(s, [{ text: 'Честно: ', options: { bold: true, color: LIME } },
      { text: 'у НИИ земледелия есть поле — −32% воды на сахарной свёкле. У нас пока нет, поэтому идёт опыт и ищем пилот. Но их система дорогая, а Su-Tech работает на любом телефоне.' }],
  { x: 0.6, y: 6.3, w: 12.1, h: 0.6, fontSize: 12.5, color: PALE });
s._after();
s.addNotes('Главный конкурент в Казахстане — система НИИ земледелия: датчики, метеостанция, расходомеры. На сахарной свёкле она сэкономила 32 процента воды. У них есть поле, у нас пока нет — это честно. Но их система дорогая. Su-Tech работает на любом телефоне.');

// 12. SWOT
s = slide({ section: 'Бизнес', glow: [2.8, 1.4, 7.5, 8.6, -2.6, 6] });
title(s, 'SWOT', '-анализ');
vline(s, 6.67, 2.0, 6.85);
hline(s, 0.6, 12.73, 4.4);
[['Сильные стороны', LIME, [['device-mobile', 'Бесплатно — нужен только телефон'], ['calculator', 'Формулы проверены на 5 000 полях'], ['chart-line-up', 'В модели −15–28% воды']]],
 ['Слабые стороны', WHITE, [['farm', 'Пока нет данных с поля'], ['check-circle', 'Проверка почвы раз в неделю'], ['cloud-rain', 'Зависит от прогноза погоды']]],
 ['Возможности', LIME, [['drop', 'Лимиты воды с 2026 года'], ['chart-bar', 'Цель — 1,3 млн га к 2030'], ['cpu', 'Датчики и автоматика насосов']]],
 ['Угрозы', WHITE, [['warning', 'Систематическая ошибка прогноза'], ['users-three', 'Недоверие к новым приложениям'], ['wifi-slash', 'Нет интернета в поле']]]].forEach(([h, col, items], i) => {
  const x = i % 2 ? 7.0 : 0.8, y = i < 2 ? 2.05 : 4.55;
  T(s, h, { x, y, w: 5.6, h: 0.5, align: 'center', fontSize: 22, bold: true, color: col });
  items.forEach(([n, t], j) => {
    T(s, '•  ' + t, { x, y: y + 0.62 + j * 0.56, w: 4.8, h: 0.5, valign: 'middle', fontSize: 15, bold: true });
    icon(s, n, col === LIME ? 'lime' : 'white', x + 4.95, y + 0.64 + j * 0.56, 0.44);
  });
});
s._after();
s.addNotes('SWOT. Сильные стороны: бесплатно и проверенная математика. Слабая сторона: пока нет данных с поля — поэтому опыт и пилот. Угроза с ошибкой прогноза закрыта кнопкой проверки почвы.');

// 13. ДОРОЖНАЯ КАРТА
s = slide({ section: 'Команда', photo: 'steppe', glow: [-2.2, 1.2, 7, 6.8, 1.2, 7.5] });
title(s, 'Дорожная ', 'карта');
s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 4.1, w: 11.33, h: 0.05, fill: { color: '5E8072' }, line: { color: '5E8072', width: 0 } });
s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 4.1, w: 4.1, h: 0.05, fill: { color: LIME }, line: { color: LIME, width: 0 } });
[['сен 2026', 'Бот и Mini App', 1], ['окт 2026', 'ИИ-агроном, serverless', 1], ['ноя 2026', 'Проверка формул, исследование', 1],
 ['дек 2026', 'Опыт с горшками', 0], ['мар 2027', 'Junior Water Prize', 0], ['лето 2027', 'Пилот: 5 хозяйств', 0], ['осень 2027', 'PRO-подписка и рост', 0]].forEach(([d, t, done], i) => {
  const cx = 1.3 + i * 1.788, up = i % 2 === 0;
  if (done) {
    s.addShape(pres.shapes.OVAL, { x: cx - 0.24, y: 3.88, w: 0.48, h: 0.48, fill: { color: LIME }, line: { color: LIME, width: 0 } });
    icon(s, 'check', 'deep', cx - 0.14, 3.98, 0.28);
  } else s.addShape(pres.shapes.OVAL, { x: cx - 0.2, y: 3.92, w: 0.4, h: 0.4, fill: { color: '002A20' }, line: { color: LIME, width: 2.25 } });
  const y0 = up ? 2.5 : 4.65;
  T(s, d, { x: cx - 1.0, y: y0, w: 2.0, h: 0.4, align: 'center', fontSize: 18, bold: true, color: done ? LIME : WHITE });
  T(s, t, { x: cx - 1.0, y: y0 + 0.45, w: 2.0, h: 0.75, align: 'center', fontSize: 12.5, color: PALE });
});
credit(s, 'Фото: Wikideas1, Wikimedia Commons, CC0', 6.88);
s._after();
s.addNotes('Бот работает с сентября, в ноябре проверена математика. Дальше — опыт с горшками, конкурс в марте и пилот на поле летом 2027 года.');

// 14. КОМАНДА
s = slide({ section: 'Команда', glow: [3.0, 2.8, 7, -3.2, -2.2, 6.5] });
title(s, 'Наша ', 'команда');
[['Осман Толобек', 'автор: идея, стенд на Arduino, эксперимент'], ['[Наставник]', '[роль]'], ['[Участник команды]', '[роль]']].forEach(([n, r], i) => {
  const x = 0.6 + i * 4.1;
  dashed(s, x + 0.9, 2.1, 2.1, 2.1, 'фото', true);
  T(s, n, { x, y: 4.55, w: 3.9, h: 0.45, align: 'center', fontSize: 20, bold: true });
  T(s, r, { x: x + 0.1, y: 5.08, w: 3.7, h: 0.8, align: 'center', fontSize: 13, color: PALE });
  if (i < 2) vline(s, x + 4.0, 2.1, 5.9);
});
T(s, 'Код написан с помощью ИИ-ассистента; идея, проверка формул, стенд и эксперимент — автора', { x: 0.6, y: 6.4, w: 12.1, h: 0.3, fontSize: 11, color: MUTED });
s._after();
s.addNotes('[Представить себя, наставника и участника команды.] Код я писал с помощью ИИ-ассистента, а идея, проверка формул, стенд и эксперимент — мои.');

// 15. QR
s = slide({ section: 'Команда', blank: true, photo: 'fields2', glow: [5.6, -0.6, 8.5, -3, 3.2, 6.5], logo: { x: 0.75, y: 1.15, d: 1.25 } });
T(s, 'SU-TECH', { x: 2.2, y: 1.15, w: 5, h: 1.25, valign: 'middle', fontSize: 40, head: true });
T(s, [{ text: 'ПОПРОБУЙТЕ ', options: { breakLine: true } }, { text: 'ПРЯМО СЕЙЧАС', options: { color: LIME } }], { x: 0.75, y: 2.7, w: 7.4, h: 1.6, fontSize: 40, head: true });
T(s, 'Наведите камеру на QR-код — бот покажет расчёт полива по шагам.', { x: 0.75, y: 4.35, w: 6.9, h: 0.75, fontSize: 18, color: 'D7EEC4' });
s.addShape(pres.shapes.RECTANGLE, { x: 0.75, y: 5.25, w: 6.6, h: 0.72, fill: { color: LIME }, line: { color: LIME, width: 0 } });
T(s, 'Ищем первое хозяйство для пилота в 2027', { x: 0.75, y: 5.25, w: 6.6, h: 0.72, align: 'center', valign: 'middle', fontSize: 18, bold: true, color: DEEP });
T(s, 'Спасибо! · Осман Толобек · [контакт]', { x: 0.75, y: 6.2, w: 7, h: 0.35, fontSize: 14, color: PALE });
s.addShape(pres.shapes.RECTANGLE, { x: 8.5, y: 1.15, w: 4.23, h: 5.3, fill: { color: WHITE }, line: { color: WHITE, width: 0 } });
s.addImage({ path: 'm/qr-demo.png', x: 8.92, y: 1.57, w: 3.4, h: 3.4, altText: 'QR-код: бот Su-Tech в демо-режиме' });
T(s, 't.me/Su_Tech_bot → /demo', { x: 8.5, y: 5.25, w: 4.23, h: 0.5, align: 'center', fontSize: 16, bold: true, color: DEEP });
T(s, 'Фото (Wikimedia Commons): Mirfayzbek Abdullayev — Аральское море; Wilfredor — сухая земля; Benoît Prieur — канал (все CC0); Alabama Extension — хлопок (CC0); Wikideas1 — полив (CC0); PSSP — каналы Файсалабада (CC BY 2.0); иконка капель — Flaticon.', { x: 0.75, y: 6.78, w: 11.5, h: 0.25, fontSize: 8.5, color: MUTED });
s._after();
s.addNotes('Наведите камеру на QR-код — бот откроется в демо и покажет весь расчёт по шагам. Мы ищем первое хозяйство для пилота: если вы знаете фермера, который готов попробовать, подойдите ко мне после защиты. Спасибо!');

// 16. ЗАПАСНОЙ: ОГРАНИЧЕНИЯ (for jury questions; Canva has no hidden slides, keep it last)
s = slide({ section: 'Запасной слайд', appendix: true, glow: [6.4, 2.8, 7, -2.6, -2.6, 6.5] });
title(s, 'Ограничения ', 'исследования');
T(s, ['Модель против модели на реальной погоде, а не измерение на поле.',
  'Погода — NASA POWER для областных центров, не метеостанции хозяйств.',
  'Урожай оценён по формуле FAO-33, а не взвешен.',
  'Лучший график подобран со знанием всех сезонов — это выгодно графику.',
  'Глина и суглинок в параметрах проекта имеют одинаковый запас воды.',
  'Потери в каналах (до 50%) Su-Tech не уменьшает — он про воду, дошедшую до поля.'].map((t, i, a) => ({ text: '•  ' + t, options: { breakLine: i < a.length - 1, paraSpaceAfter: 10 } })),
  { x: 0.75, y: 2.2, w: 11.8, h: 4.4, fontSize: 18, bold: true });
s._after();
s.addNotes('Запасной слайд для ответов на вопросы жюри. Подробности: github.com/osmanri/sutech-core → research/README.md');

pres.writeFile({ fileName: OUT }).then(f => console.log('wrote', f));
