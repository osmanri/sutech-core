// Su-Tech pitch deck — mentor's structure and "big photo, then text" layouts, Su-Tech colours, native objects.
// Object names carry animation hints for animate.py:
//   "!!name"          Morph matches it across slides      "aN|kind|name"  entrance animation, stagger group N
const pptxgen = require('pptxgenjs');
const nodePath = require('path');
const { applyTheme } = require(process.argv[2] + '/scripts/apply_theme.js');
const OUT = process.env.OUT || 'Su-Tech.pptx';
const THEME = {
  name: 'Su-Tech', headFontFace: 'Manrope ExtraBold', bodyFontFace: 'Inter',
  colors: { dk1: '00382A', lt1: 'FFFFFF', dk2: '002A20', lt2: 'F3F8EE', accent1: '81CA2A', accent2: '3C9C24',
            accent3: '1E8A34', accent4: 'B9E07A', accent5: '005A32', accent6: '8FAE9F', hlink: '81CA2A', folHlink: 'B9E07A' },
};
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'Su-Tech — умный полив';
pres.author = 'Осман Толобек';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const WHITE = C.background1, DEEP = C.text1, LIME = C.accent1, PALE = C.accent4, MUTED = C.accent6;
const HEAD = '+mj-lt', RED = 'E53935';
const TOTAL = 16;
let uid = 0, shown = 0;
const an = (g, kind = 'rise') => `a${g}|${kind}|o${++uid}`;

pres.defineSlideMaster({ title: 'M', background: { path: 'm/base.jpg' }, objects: [
  { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 1.0, w: 12.13, h: 0.85, fontSize: 38, color: WHITE,
      margin: 0, valign: 'top', align: 'left' }, text: '' } },
  { rect: { x: 0.6, y: 7.12, w: 12.13, h: 0.03, fill: { color: WHITE, transparency: 86 } } },
] });
pres.defineSlideMaster({ title: 'B', background: { path: 'm/base.jpg' }, objects: [
  { rect: { x: 0.6, y: 7.12, w: 12.13, h: 0.03, fill: { color: WHITE, transparency: 86 } } },
] });

function T(s, text, o, g, kind) {
  s.addText(text, Object.assign({ margin: 0, valign: 'top', isTextBox: true, color: WHITE, fontSize: 14 }, g ? { objectName: an(g, kind) } : {}, o));
}
function icon(s, n, c, x, y, size, g, kind) {
  s.addImage(Object.assign({ path: `m/${n}-${c}.png`, x, y, w: size, h: size, altText: '' }, g ? { objectName: an(g, kind) } : {}));
}
function line(s, x1, y1, x2, y2, color, width, g, kind, tr) {
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipV: (x2 - x1) * (y2 - y1) < 0, line: { color, width, transparency: tr || 0 }, objectName: g ? an(g, kind || 'wipe') : `line-${++uid}` });
}
const sep = (s, x1, y1, x2, y2, g) => line(s, x1, y1, x2, y2, 'FFFFFF', 1, g, 'wipe', 72);   // thin divider
function dashed(s, x, y, w, h, label, g, round) {
  s.addShape(round ? pres.shapes.OVAL : pres.shapes.ROUNDED_RECTANGLE, Object.assign({ x, y, w, h, fill: { color: WHITE, transparency: 93 },
    line: { color: PALE, width: 1.25, dashType: 'dash', transparency: 30 }, objectName: g ? an(g) : `photo-${++uid}` }, round ? {} : { rectRadius: 0.1 }));
  T(s, label, { x, y: y + h / 2 - 0.18, w, h: 0.36, align: 'center', valign: 'middle', fontSize: 12, color: PALE }, g);
}
function slide(o) {
  const s = pres.addSlide({ masterName: o.blank ? 'B' : 'M', sectionTitle: o.section });
  if (o.photo) s.background = { path: `m/full-${o.photo}.jpg` };
  if (o.hidden) s.hidden = true; else shown++;
  const [ax, ay, aw, bx, by, bw] = o.glow;
  s.addImage({ path: 'm/glow-lime.png', x: ax, y: ay, w: aw, h: aw, altText: '', objectName: '!!glowA' });
  s.addImage({ path: 'm/glow-green.png', x: bx, y: by, w: bw, h: bw, altText: '', objectName: '!!glowB' });
  // corner details: faint big icon half off-slide, two small ones, and a dot grid
  {
    const sets = [['drop-half', 'thermometer', 'sun'], ['waves', 'leaf', 'drop'], ['sparkle', 'drop', 'leaf'], ['wind', 'cloud-rain', 'drop'],
      ['map-trifold', 'leaf', 'drop'], ['flask', 'drop', 'leaf'], ['chart-line-up', 'drop', 'leaf'], ['warning-circle', 'drop', 'leaf'],
      ['tractor', 'grains', 'drop'], ['scales', 'leaf', 'drop'], ['users-three', 'leaf', 'drop'], ['calendar-check', 'leaf', 'drop'], ['cpu', 'lightning', 'drop']];
    const [n1, n2, n3] = sets[(shown + uid) % sets.length];
    const put = (n, x, y, w, tr, k) => s.addImage({ path: `img/d-${n}-lime.png`, x, y, w, h: w, transparency: tr, altText: '', objectName: `decor-${n}-${k}` });
    if (!o.blank) {
      put(n1, 11.9, -0.45, 1.7, 80, 1); put(n2, 11.2, 0.95, 0.4, 68, 2); put(n3, 12.6, 1.3, 0.34, 68, 3);
      s.addImage({ path: 'm/dots.png', x: 0.6, y: 6.5, w: 1.45, h: 0.9, transparency: 62, altText: "", objectName: "decor-dots" });
    } else {
      put(n1, 11.9, 5.6, 1.7, 80, 1); put(n2, 11.1, 6.45, 0.4, 68, 2);
      s.addImage({ path: 'm/dots.png', x: 11.2, y: 0.95, w: 1.45, h: 0.9, transparency: 62, altText: "", objectName: "decor-dots" });
    }
  }
  s._after = () => {
    const L = o.logo || { x: 0.6, y: 0.36, d: 0.52 };
    s.addShape(pres.shapes.OVAL, { x: L.x, y: L.y, w: L.d, h: L.d, fill: { color: WHITE }, line: { type: 'none' }, objectName: '!!logodisc' });
    s.addImage({ path: 'm/logo.png', x: L.x + L.d * 0.14, y: L.y + L.d * 0.14, w: L.d * 0.72, h: L.d * 0.72, altText: 'Логотип Su-Tech', objectName: '!!logo' });
    if (!o.logo) T(s, 'Su-Tech', { x: 1.24, y: 0.36, w: 2, h: 0.52, valign: 'middle', fontSize: 15, bold: true, objectName: '!!wordmark' });
    T(s, `${String(shown).padStart(2, '0')} / ${TOTAL}  ·  ${o.section.toUpperCase()}`, { x: 7.7, y: 0.36, w: 5.03, h: 0.52, align: 'right', valign: 'middle',
      fontSize: 10.5, bold: true, color: PALE, charSpacing: 2 });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 7.105, w: Math.max(0.2, 12.13 * shown / TOTAL), h: 0.06, fill: { color: LIME }, line: { type: 'none' }, objectName: '!!progress' });
  };
  return s;
}
const title = (s, a, b) => s.addText([{ text: a.toUpperCase() }, { text: (b || '').toUpperCase(), options: { color: LIME } }], { placeholder: 'title' });
const credit = (s, t, y = 6.82) => T(s, t, { x: 0.6, y, w: 12, h: 0.22, fontSize: 8.5, color: MUTED });

// ===== 1. ПРОБЛЕМА ВОДЫ — the Aral Sea photo =====
pres.addSection({ title: 'Проблема' });
let s = slide({ section: 'Проблема', blank: true, photo: 'aral', glow: [-2.8, -3.0, 7, 9, 4.2, 6] });
{
  const TW = 7.84, BADGE = 1.1, GAP = 0.25, TX = (13.333 - (TW + GAP + BADGE)) / 2;
  T(s, [{ text: 'ПРОБЛЕМА ' }, { text: 'ВОДЫ', options: { color: RED } }],
    { x: TX, y: 1.0, w: TW + 0.4, h: 1.2, valign: 'middle', fontFace: HEAD, fontSize: 64, wrap: false, objectName: 'title-problem' });
  // blue double-drop icon (Flaticon), centred where the old red badge was; no badge behind it
  s.addImage({ path: nodePath.join(__dirname, 'icons', 'drops-duo.png'), x: TX + TW + GAP - 0.05, y: 1.0, w: 1.2, h: 1.2, altText: '', objectName: '!!dropicon' });
}
[['72%', 'farm', 'пресной воды мира забирает сельское хозяйство', 'ФАО, AQUASTAT 2025'],
 ['до 50%', 'drop-half', 'воды в Казахстане теряется по дороге — в оросительных каналах', 'Astana Times, октябрь 2026'],
 ['−78%', 'grains', 'предложено сократить посевы риса в Туркестанской области: с 16 000 до 3 500 га', 'Dunyo.info, 13 января 2026']].forEach(([num, ic, txt, from], i) => {
  const x = 0.75 + i * 4.1, g = i + 2;
  icon(s, ic, 'white', x, 2.75, 0.95, g);
  T(s, num, { x, y: 3.85, w: 3.6, h: 0.95, fontFace: HEAD, fontSize: 46, color: LIME, valign: 'middle', wrap: false }, g);
  T(s, txt, { x, y: 4.85, w: 3.5, h: 1.2, fontSize: 17, bold: true }, g);
  T(s, from, { x, y: 6.1, w: 3.5, h: 0.25, fontSize: 10, color: PALE }, g);
  if (i < 2) sep(s, x + 3.8, 2.75, x + 3.8, 6.3, g);
});
T(s, 'Осман Толобек · [школа, город]', { x: 0.6, y: 6.55, w: 9, h: 0.28, fontSize: 12.5, color: PALE }, 5, 'fade');
credit(s, 'Фото: «Graveyard of Ships (Aral sea)», Mirfayzbek Abdullayev, Wikimedia Commons, CC0 · Иконка капель: Flaticon', 6.86);
s._after();
s.addNotes('Здравствуйте! Меня зовут Осман Толобек, мой проект — Su-Tech. Это Аральское море: корабли стоят посреди пустыни. Сельское хозяйство забирает 72 процента пресной воды мира. В Казахстане до половины воды теряется ещё в каналах. В 2026 году ввели лимиты, посевы риса в Туркестанской области предложили сократить на 78 процентов.');

// ===== 2. ПРОБЛЕМА В ЦИФРАХ =====
s = slide({ section: 'Проблема', glow: [7.6, -2.6, 7.5, -2.4, 3.4, 6.5] });
title(s, 'Каждый кубометр ', 'на счету');
T(s, '3,8 млрд м³', { x: 0.6, y: 2.2, w: 4.3, h: 0.8, fontFace: HEAD, fontSize: 36, color: LIME, valign: 'middle', wrap: false }, 2, 'zoom');
T(s, 'лимит воды на 2026 год для всей Туркестанской области', { x: 0.6, y: 3.05, w: 3.9, h: 0.9, fontSize: 15, bold: true }, 2);
T(s, 'Times of Central Asia, 2026', { x: 0.6, y: 4.0, w: 4, h: 0.25, fontSize: 10, color: PALE }, 2);
s.addChart(pres.charts.DOUGHNUT, [{ name: 'Пресная вода мира', labels: ['Сельское хозяйство', 'Промышленность и сфера услуг'], values: [72, 28] }],
  { x: 7.0, y: 1.95, w: 2.65, h: 2.65, holeSize: 64, chartColors: ['81CA2A', '2E5F4B'], showLegend: false, showValue: false, showPercent: false, showTitle: false,
    dataBorder: { pt: 1, color: '002A20' }, objectName: an(3, 'fade') });
T(s, '72%', { x: 7.0, y: 2.95, w: 2.65, h: 0.65, align: 'center', valign: 'middle', fontFace: HEAD, fontSize: 24, color: LIME }, 3, 'zoom');
T(s, [{ text: 'сельское хозяйство', options: { breakLine: true } }, { text: '72%', options: { bold: true, fontSize: 18, color: LIME } }], { x: 4.7, y: 3.55, w: 2.15, h: 0.7, fontSize: 13, align: 'right' }, 3);
T(s, [{ text: 'промышленность и сфера услуг', options: { breakLine: true } }, { text: '28%', options: { bold: true, fontSize: 18 } }], { x: 9.85, y: 2.1, w: 2.9, h: 0.7, fontSize: 13 }, 3);
T(s, 'пресная вода мира · ФАО, 2025', { x: 9.85, y: 4.2, w: 2.9, h: 0.25, fontSize: 10, color: PALE }, 3);
line(s, 4.7, 4.75, 12.73, 4.75, 'FFFFFF', 1.25, 4, 'wipe', 55);
line(s, 8.9, 4.75, 8.9, 6.85, 'FFFFFF', 1.25, 4, 'wipe', 55);
s.addChart(pres.charts.PIE, [{ name: 'Вода в каналах', labels: ['Теряется', 'Доходит до поля'], values: [50, 50] }],
  { x: 5.85, y: 4.95, w: 1.9, h: 1.9, chartColors: ['E53935', '2E5F4B'], showLegend: false, showValue: false, showPercent: false, showTitle: false,
    dataBorder: { pt: 1, color: '002A20' }, objectName: an(5, 'fade') });
T(s, [{ text: 'теряется в каналах', options: { breakLine: true } }, { text: 'до 50%', options: { bold: true, fontSize: 18, color: 'FF8A80' } }], { x: 3.2, y: 5.2, w: 2.55, h: 0.7, fontSize: 13, align: 'right' }, 5);
T(s, [{ text: 'доходит до поля', options: { breakLine: true } }, { text: '50%', options: { bold: true, fontSize: 18 } }], { x: 3.2, y: 6.0, w: 2.55, h: 0.7, fontSize: 13, align: 'right' }, 5);
s.addShape(pres.shapes.OVAL, { x: 9.25, y: 5.15, w: 0.9, h: 0.9, fill: { color: LIME }, line: { type: 'none' }, objectName: '!!dropbg' });
s.addImage({ path: 'm/drop-white.png', x: 9.43, y: 5.33, w: 0.54, h: 0.54, altText: '', objectName: '!!dropicon' });
T(s, 'до 3 940 м³', { x: 10.35, y: 5.05, w: 2.4, h: 0.7, fontFace: HEAD, fontSize: 26, valign: 'middle', wrap: false }, 6, 'zoom');
T(s, 'с гектара уходит глубже корней — даже при лучшем графике · модель FAO-56', { x: 10.35, y: 5.8, w: 2.4, h: 1.0, fontSize: 11, color: PALE }, 6);
s._after();
s.addNotes('Вопрос залу: сколько воды уходит в землю зря? График полива не знает погоды, его делают с запасом, и после дождя вода уходит глубже корней. Даже при лучшем графике это до четырёх тысяч кубометров с гектара (хлопок, арык) за сезон. Каждый кубометр, дошедший до поля, нужно лить точно.');

// ===== 3. SU-TECH — canal photo =====
pres.addSection({ title: 'Решение' });
s = slide({ section: 'Решение', blank: true, photo: 'canal', glow: [-1.2, 0.6, 7.2, 7.5, -3.2, 8], logo: { x: 0.9, y: 1.85, d: 4.1 } });
T(s, 'SU-TECH', { x: 5.45, y: 1.45, w: 7.4, h: 1.5, valign: 'middle', fontFace: HEAD, fontSize: 84, color: LIME }, 2, 'zoom');
T(s, '— Telegram-бот, который каждый день по погоде поля считает, нужно ли поливать, сколько воды подать и сколько стоит работа насоса.',
  { x: 5.5, y: 3.1, w: 7.2, h: 1.95, fontSize: 22, bold: true, lineSpacingMultiple: 1.1 }, 3);
[['plant', 'Без датчиков', 5.5, 2.2], ['device-mobile', 'Нужен только телефон', 7.95, 3.1], ['translate', 'RU · ҚАЗ · EN', 11.15, 1.9]].forEach(([ic, t, x, w], i) => {
  const g = 4 + i;
  icon(s, ic, 'lime', x, 5.45, 0.38, g);
  T(s, t, { x: x + 0.5, y: 5.45, w: w - 0.5, h: 0.38, valign: 'middle', fontSize: 14, bold: true }, g);
  if (i) sep(s, x - 0.25, 5.4, x - 0.25, 5.9, g);
});
credit(s, 'Фото: Benoît Prieur, Wikimedia Commons, CC0');
s._after();
s.addNotes('Su-Tech — агроном в кармане. Ничего не нужно покупать: открываешь бота в Telegram и отмечаешь поле. Бот отвечает на три вопроса: поливать ли сегодня, сколько воды и сколько это стоит.');

// ===== 4. ИЗ ЧЕГО СОСТОИТ — four tall photos =====
s = slide({ section: 'Решение', glow: [3.2, 2.6, 7, -3, -2.5, 6.5] });
title(s, 'Из чего состоит ', 'Su-Tech');
[['Arduino Uno и реле', 'мозг стенда: включает насос'], ['Помпа и расходомер', 'подаёт и считает воду'],
 ['Весы HX711', 'вес горшка = сколько испарилось'], ['Telegram-бот', 'откройте по QR-коду']].forEach(([t, d], i) => {
  const x = 0.6 + i * 3.1, g = i + 2;
  if (i < 3) dashed(s, x, 2.05, 2.8, 3.75, 'фото', g);
  else {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.05, w: 2.8, h: 3.75, rectRadius: 0.1, fill: { color: WHITE }, line: { type: 'none' }, objectName: an(g) });
    s.addImage({ path: 'm/qr-demo.png', x: x + 0.2, y: 2.7, w: 2.4, h: 2.4, altText: 'QR-код: t.me/Su_Tech_bot, демо-режим', objectName: an(g) });
  }
  T(s, t, { x, y: 5.98, w: 2.8, h: 0.4, fontSize: 16, bold: true }, g);
  T(s, d, { x, y: 6.4, w: 2.8, h: 0.4, fontSize: 11.5, color: PALE }, g);
  if (i < 3) sep(s, x + 2.95, 2.05, x + 2.95, 6.8, g);
});
s._after();
s.addNotes('Из чего состоит проект. Стенд на Arduino: реле и помпа, расходомер, весы под горшком. И сам бот — его можно открыть по QR-коду прямо сейчас.');

// ===== 5. ПРИЛОЖЕНИЕ — phones over a field photo =====
s = slide({ section: 'Решение', photo: 'green', glow: [0.2, 1.6, 6.5, 7.2, 2.8, 7] });
title(s, 'Всё в одном ', 'чате');
s.addImage({ path: 'm/phone-bot.png', x: 0.85, y: 2.0, w: 2.3, h: 4.84, altText: 'Чат с ботом Su-Tech: меню «Открыть Su-Tech», «ИИ-агроном», «Мои поля», «История»', objectName: '!!phone-bot' });
s.addImage({ path: 'm/phone-mini.png', x: 3.45, y: 2.0, w: 2.3, h: 4.84, altText: 'Mini App Su-Tech: «Точный полив. Живое поле.» и карта поля', objectName: '!!phone-mini' });
[['chat-circle-text', 'Совет приходит сообщением', 'каждый день, прямо в Telegram'], ['map-trifold', 'Поле на спутниковой карте', 'отмечается пальцем, площадь считается сама'],
 ['plant', 'Культура, почва, насос', 'хлопок, кукуруза, пшеница и другие'], ['translate', 'Три языка', 'русский, қазақша, English'],
 ['robot', 'ИИ-агроном', 'отвечает на вопросы и смотрит фото листьев']].forEach(([ic, t, d], i) => {
  const y = 2.0 + i * 0.97, g = i + 2;
  icon(s, ic, 'lime', 6.5, y + 0.1, 0.55, g);
  T(s, t, { x: 7.3, y: y + 0.04, w: 5.4, h: 0.4, fontSize: 18, bold: true }, g);
  T(s, d, { x: 7.3, y: y + 0.46, w: 5.4, h: 0.32, fontSize: 12.5, color: PALE }, g);
  if (i < 4) sep(s, 6.5, y + 0.9, 12.73, y + 0.9, g);
});
credit(s, 'Фото: Alabama Extension, Wikimedia Commons, CC0', 6.9);
s._after();
s.addNotes('Так это выглядит: слева сам бот, справа Mini App с полем на спутниковой карте. Три языка, ИИ-агроном. Демо для вас — по QR-коду.');

// ===== 6. MINI APP =====
s = slide({ section: 'Решение', glow: [0.4, 1.2, 7.5, 8.4, 3.6, 6] });
title(s, 'Mini App ', 'крупно');
{
  const PX = 2.0, PY = 1.85, PW = 2.45, k = PW / 380;
  s.addImage({ path: 'm/phone-bot.png', x: -3.4, y: 2.6, w: 2.3, h: 4.84, altText: '', objectName: '!!phone-bot' });
  s.addImage({ path: 'm/phone-mini.png', x: PX, y: PY, w: PW, h: 800 * k, altText: 'Mini App Su-Tech крупно', objectName: '!!phone-mini' });
  [['Три языка: RU · ҚАЗ · EN', 233, 187], ['Настроить поле за минуту', 120, 453], ['Вкладки: карта, параметры, расчёт', 187, 536],
   ['Поле на спутниковой карте', 133, 607], ['Город по поиску или GPS', 293, 724]].forEach(([t, cx, cy], i) => {
    const px = PX + cx * k, py = PY + cy * k, ty = 2.05 + i * 0.92, g = i + 2;
    line(s, px, py, 7.0, ty + 0.3, '81CA2A', 1.25, g);
    s.addShape(pres.shapes.OVAL, { x: px - 0.07, y: py - 0.07, w: 0.14, h: 0.14, fill: { color: LIME }, line: { color: WHITE, width: 1 }, objectName: an(g, 'zoom') });
    T(s, t, { x: 7.15, y: ty, w: 5.6, h: 0.6, valign: 'middle', fontSize: 20, bold: true }, g);
  });
}
s._after();
s.addNotes('Mini App внутри Telegram: три языка, поле настраивается за минуту, участок отмечается на спутниковой карте, город — поиском или по GPS.');

// ===== 7. ПЕРВЫЙ ЭКСПЕРИМЕНТ — big photo left, lines right =====
pres.addSection({ title: 'Доказательства' });
s = slide({ section: 'Доказательства', glow: [-2.8, 2.2, 6.5, 6.5, -2.8, 7.5] });
title(s, 'Первый ', 'эксперимент');
dashed(s, 0.6, 2.0, 3.75, 4.75, 'фото стенда', 2);
const rows7 = [['Место', '[школа, кабинет]'], ['Срок', '[4–6 недель, даты]'], ['Горшки', '12 — 6 по Su-Tech, 6 по графику'], ['Измеряю', 'вес горшка каждый день'], ['Результат', '[__%] меньше воды']];
rows7.forEach(([k, v], i) => {
  const y = 2.0 + i * 0.95, g = i + 3, last = i === 4;
  sep(s, 4.7, y, 12.73, y, g);
  T(s, k.toUpperCase(), { x: 4.7, y, w: 1.9, h: 0.95, valign: 'middle', fontSize: 11, bold: true, color: LIME, charSpacing: 2 }, g);
  T(s, v, { x: 6.7, y, w: 6, h: 0.95, valign: 'middle', fontSize: 21, bold: true, color: last ? LIME : WHITE }, g);
});
sep(s, 4.7, 6.75, 12.73, 6.75, 8);
s._after();
s.addNotes('Модель нужно проверить на настоящих растениях. Я собрал стенд на Arduino. Двенадцать горшков делятся по жребию на две группы. Каждый день весы показывают, сколько воды растение испарило на самом деле, и я сравниваю это с расчётом бота. [Здесь будет результат опыта.]');

// ===== 8. РЕЗУЛЬТАТ МОДЕЛИ =====
s = slide({ section: 'Доказательства', photo: 'fields', glow: [-2.4, -1.2, 8, 7.8, 3.4, 6.5] });
title(s, 'Результат ', 'модели');
T(s, '−15–28%', { x: 0.6, y: 1.95, w: 5.8, h: 1.55, valign: 'middle', fontFace: HEAD, fontSize: 80, color: LIME, wrap: false }, 2, 'zoom');
T(s, 'воды при том же урожае', { x: 0.6, y: 3.55, w: 5.6, h: 0.5, fontSize: 22, bold: true }, 3);
['25 из 25 сезонов в пользу Su-Tech', 'худший сезон: 9–20%', '2 почвы × 3 даты посева: 14–42%'].forEach((t, i) => {
  const y = 4.3 + i * 0.62, g = i + 4;
  icon(s, 'check-circle', 'lime', 0.6, y + 0.06, 0.34, g);
  T(s, t, { x: 1.1, y, w: 4.8, h: 0.46, valign: 'middle', fontSize: 15, bold: true }, g);
});
T(s, 'Против лучшего возможного графика · модель FAO-56, погода NASA POWER, 5 регионов × 5 сезонов · не полевое измерение', { x: 0.6, y: 6.3, w: 5.5, h: 0.5, fontSize: 9.5, color: PALE }, 7, 'fade');
T(s, 'ВОДА ЗА СЕЗОН, м³/га', { x: 6.75, y: 2.0, w: 5.8, h: 0.3, fontSize: 10.5, bold: true, color: PALE, charSpacing: 2 }, 4);
s.addChart(pres.charts.BAR, [
  { name: 'Su-Tech', labels: ['Хлопок, капля', 'Хлопок, борозды', 'Кукуруза, капля', 'Кукуруза, борозды'], values: [11321, 19751, 9039, 15781] },
  { name: 'Лучший график', labels: ['Хлопок, капля', 'Хлопок, борозды', 'Кукуруза, капля', 'Кукуруза, борозды'], values: [15117, 27600, 10709, 19525] },
], { x: 6.6, y: 2.3, w: 6.2, h: 4.5, barDir: 'col', barGrouping: 'clustered', barGapWidthPct: 55,
     chartColors: ['81CA2A', 'DCEBD3'], showLegend: true, legendPos: 't', legendFontSize: 11, legendFontFace: '+mn-lt', legendColor: 'FFFFFF',
     showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 9, dataLabelColor: 'FFFFFF', dataLabelFontFace: '+mn-lt', dataLabelFormatCode: '# ##0',
     catAxisLabelColor: 'FFFFFF', catAxisLabelFontSize: 10, catAxisLabelFontFace: '+mn-lt', catAxisLineShow: false,
     valAxisHidden: true, valGridLine: { style: 'none' }, catGridLine: { style: 'none' }, objectName: an(5, 'wipeup') });
credit(s, 'Фото: PSSP, «Irrigation canals of Faisalabad», CC BY 2.0, Wikimedia Commons', 6.88);
s._after();
s.addNotes('Главный результат. Su-Tech сравнивается не с плохим графиком, а с лучшим возможным: урожай не ниже 98 процентов. Даже против него Su-Tech тратит на 15–28 процентов меньше воды — в каждом из 25 сезонов. Честно: это компьютерная модель на реальной погоде, поэтому идёт эксперимент.');

// ===== 9. ПОЛЬЗА — what the farmer, the akimat and nature gain =====
s = slide({ section: 'Доказательства', glow: [-2.6, -2.2, 7.5, 7.6, 3.0, 6.5] });
title(s, 'В чём ', 'польза');
[['drop', '−3 800 м³', 'воды с гектара за сезон при том же урожае', 'хлопок, капля: 11 321 вместо 15 117 м³/га'], ['coins', '≈35 000 ₸', 'за электричество насоса с гектара за сезон', 'пример: насос 22 кВт, 60 м³/ч, 25 ₸/кВт·ч'], ['chart-line-up', '100%', 'урожая вместо 84–90% у графика с обычной нормой воды', '0 дней стресса против 38–65']].forEach(([ic, num, txt, note], i) => {
  const x = 0.75 + i * 4.1, g = i + 2;
  icon(s, ic, 'lime', x, 2.0, 0.6, g);
  T(s, num, { x, y: 2.7, w: 3.7, h: 0.9, valign: 'middle', fontFace: HEAD, fontSize: 40, color: LIME, wrap: false }, g, 'zoom');
  T(s, txt, { x, y: 3.65, w: 3.5, h: 0.75, fontSize: 15, bold: true }, g);
  T(s, note, { x, y: 4.45, w: 3.5, h: 0.45, fontSize: 10.5, color: PALE }, g);
  if (i < 2) sep(s, x + 3.8, 2.0, x + 3.8, 4.9, g);
});
sep(s, 0.6, 5.2, 12.73, 5.2, 5);
[['farm', 'Фермеру', 'меньше счёт за насос, урожай не страдает'], ['users-three', 'Акимату', 'проще уложиться в лимиты воды 2026 года'], ['plant', 'Природе', 'меньше воды из рек, меньше уходит в глубину']].forEach(([ic, h, d], i) => {
  const x = 0.75 + i * 4.1, g = 6 + i;
  icon(s, ic, 'white', x, 5.45, 0.42, g);
  T(s, [{ text: h, options: { bold: true, color: LIME, breakLine: true } }, { text: d }], { x: x + 0.6, y: 5.38, w: 3.2, h: 0.8, fontSize: 12.5 }, g);
});
T(s, 'Модель FAO-56 на реальной погоде, а не измерение на поле · сравнение с лучшим графиком при одинаковом урожае', { x: 0.6, y: 6.55, w: 12.1, h: 0.25, fontSize: 9.5, color: PALE }, 9, 'fade');
s._after();
s.addNotes('В чём польза. Первое: при том же урожае Su-Tech тратит меньше воды — для хлопка на капле это около 3 800 кубометров с гектара за сезон, и насосу не нужно их качать: при обычном насосе это примерно 35 тысяч тенге за электричество с гектара. Второе: если фермер поливает по средней норме, но не по погоде, Su-Tech даёт не экономию, а урожай — сто процентов вместо 84–90. Третье: при лимитах воды сэкономленные кубометры можно отдать другому полю. Всё это модель на реальной погоде, поэтому идёт опыт.');

// ===== 9. СЛАБОЕ МЕСТО — two photos side by side =====
s = slide({ section: 'Доказательства', blank: true, photo: 'split', glow: [6.0, 1.0, 4, 6.2, 1.2, 4] });
s.addText([{ text: 'СЛАБОЕ МЕСТО ' }, { text: 'И РЕШЕНИЕ', options: { color: LIME } }], { x: 0.6, y: 1.0, w: 12.13, h: 0.85, fontFace: HEAD, fontSize: 38, color: WHITE, margin: 0, valign: 'top' });
icon(s, 'warning', 'white', 0.75, 2.2, 0.5, 2);
T(s, 'Прогноз всё время занижает испарение на 20%', { x: 1.45, y: 2.2, w: 4.6, h: 0.5, valign: 'middle', fontSize: 14, bold: true, color: PALE }, 2);
T(s, '73', { x: 0.75, y: 2.9, w: 5.2, h: 2.3, valign: 'middle', fontFace: HEAD, fontSize: 150, wrap: false }, 2, 'zoom');
T(s, 'дня стресса растений за сезон', { x: 0.75, y: 5.3, w: 5.2, h: 0.5, fontSize: 20, bold: true }, 2);
s.addShape(pres.shapes.OVAL, { x: 6.29, y: 4.0, w: 0.75, h: 0.75, fill: { color: LIME }, line: { type: 'none' }, objectName: an(3, 'zoom') });
icon(s, 'arrow-right', 'deep', 6.465, 4.175, 0.4, 3, 'zoom');
icon(s, 'check-circle', 'lime', 7.45, 2.2, 0.5, 4);
T(s, 'То же + кнопка «сухо / нормально / влажно» раз в неделю', { x: 8.15, y: 2.2, w: 4.55, h: 0.5, valign: 'middle', fontSize: 14, bold: true, color: PALE }, 4);
T(s, '0', { x: 7.45, y: 2.9, w: 5.2, h: 2.3, valign: 'middle', fontFace: HEAD, fontSize: 150, color: LIME, wrap: false }, 4, 'zoom');
T(s, 'дней стресса · экономия 14–17%', { x: 7.45, y: 5.3, w: 5.25, h: 0.5, fontSize: 20, bold: true }, 4);
T(s, 'Случайные ошибки до ±30%, неучтённые дожди, неверная почва — 0 дней стресса · хлопок, модель', { x: 0.6, y: 6.55, w: 12.1, h: 0.25, fontSize: 9.5, color: PALE }, 5, 'fade');
credit(s, 'Фото: Wilfredor и Alabama Extension, Wikimedia Commons, CC0', 6.86);
s._after();
s.addNotes('Я специально искал, где модель ломается. Случайные ошибки ей не страшны. А если прогноз всё время занижает испарение, ошибка копится — 73 дня стресса за сезон. Решение — одна кнопка: раз в неделю фермер отвечает, сухая ли почва. Стресс исчезает, экономия остаётся. Эта кнопка уже есть в боте.');

// ===== 10. ФИНАНСЫ — four big numbers over a field photo =====
pres.addSection({ title: 'Бизнес' });
s = slide({ section: 'Бизнес', photo: 'steppe', glow: [-2.6, 2.6, 7, 7, -3.2, 7.5] });
title(s, 'Финансы ', 'и рынок');
sep(s, 6.67, 2.1, 6.67, 6.6, 2);
sep(s, 0.6, 4.35, 12.73, 4.35, 2);
[['Стоимость стенда (MVP)', '[__ ₸]', null, 'Arduino, помпа, расходомер, весы, датчики', LIME],
 ['Цена для фермера', '0 ₸', null, 'нужен только Telegram', LIME],
 ['Модель заработка', 'Freemium', 'handshake', 'расчёт полива — 0 ₸ · PRO $10/мес: ИИ-агроном по фото · комплект автоматики насоса — $100', WHITE],
 ['Рынок', '702 300 га', 'farm', 'уже на водосбережении (1 сен 2026) · цель — 1,3 млн га к 2030 · Astana Times', WHITE]].forEach(([k, v, ic, d, col], i) => {
  const x = i % 2 ? 7.05 : 0.8, y = i < 2 ? 2.2 : 4.6, g = i + 3;
  T(s, k.toUpperCase(), { x, y, w: 5.4, h: 0.3, fontSize: 10.5, bold: true, color: PALE, charSpacing: 2 }, g);
  T(s, v, { x, y: y + 0.38, w: 4.4, h: 1.0, valign: 'middle', fontFace: HEAD, fontSize: 46, color: col, wrap: false }, g, 'zoom');
  if (ic) icon(s, ic, 'lime', x + 4.6, y + 0.5, 0.75, g);
  T(s, d, { x, y: y + 1.45, w: 5.4, h: 0.55, fontSize: 12, color: PALE }, g);
});
credit(s, 'Фото: Wikideas1, Wikimedia Commons, CC0', 6.88);
s._after();
s.addNotes('Финансы. Стенд стоил [сумма]. Фермеру Su-Tech бесплатен — нужен только Telegram. Модель заработка — freemium: расчёт полива бесплатный, PRO за 10 долларов в месяц — ИИ-агроном по фото, и комплект автоматики насоса за 100 долларов. Рынок: 702 тысячи гектаров уже на водосберегающих технологиях, к 2030 году цель — 1,3 миллиона.');

// ===== 11. VS КОНКУРЕНТЫ =====
s = slide({ section: 'Бизнес', glow: [7.4, 2.8, 7, -2.2, -2.8, 6.5] });
title(s, 'Su-Tech ', 'vs конкуренты');
{
  // same four columns as the mentor's comparison slide; every mark follows the sources (Qazinform 28.09.2026, cropx.com and store.cropx.com, FAO software page, FAO/IAEA study)
  const P = { text: '+', options: { color: '81CA2A', fontFace: 'Manrope ExtraBold', fontSize: 28, align: 'center', valign: 'middle' } };
  const M = { text: '−', options: { color: '8FAE9F', fontFace: 'Manrope ExtraBold', fontSize: 28, align: 'center', valign: 'middle' } };
  const Q = { text: '?', options: M.options };   // the price of the NII system is not published
  const hd = (t, al) => ({ text: t, options: { bold: true, color: '00382A', fill: { color: '81CA2A' }, fontSize: 13, align: al || 'center', valign: 'middle' } });
  const rw = (name, vals, hl) => [{ text: name, options: { bold: true, fontSize: hl ? 18 : 14, color: hl ? '81CA2A' : 'FFFFFF', valign: 'middle', fill: hl ? { color: '0E5A3C' } : undefined } }]
    .concat(vals.map(v => ({ text: v.text, options: Object.assign({}, v.options, hl ? { fill: { color: '0E5A3C' } } : {}) })));
  s.addTable([
    [hd('Название', 'left'), hd('автоматизация'), hd('финансовая доступность'), hd('полная оптимизация'), hd('отечественный продукт')],
    rw('Su-Tech', [P, P, P, P], true),
    rw('НИИ земледелия: датчики и метеостанция', [P, Q, P, P]),
    rw('CropX: зарубежная система с датчиками', [P, M, P, M]),
    rw('CROPWAT ФАО: программа для компьютера', [M, P, P, M]),
  ], { x: 0.6, y: 2.05, w: 12.13, colW: [4.73, 1.85, 1.85, 1.85, 1.85], rowH: [0.65, 0.78, 0.78, 0.78, 0.78],
       border: { type: 'solid', color: '3E7A62', pt: 1 }, margin: 0.14, objectName: an(3, 'fade') });
}
T(s, [{ text: 'Пояснения: ', options: { bold: true, color: LIME } },
      { text: 'автоматизация — расчёт без ежедневного ввода данных (насос включает человек, автоматика насоса пока прототип); оптимизация — по погоде, культуре и почве, в модели, данных с поля у нас пока нет. CropX: датчик $500–695 + подписка $300 (магазин CropX); CROPWAT бесплатен (ФАО); цена системы НИИ не опубликована («?»).' }],
  { x: 0.6, y: 6.3, w: 12.1, h: 0.6, fontSize: 12.5, color: PALE }, 4);
s._after();
s.addNotes('Сравнение как у ментора: четыре признака. Автоматизация — расчёт без ежедневного ввода данных: Su-Tech берёт погоду сам, CropX и комплекс НИИ работают по датчикам, в CROPWAT данные вводит человек. Финансовая доступность: Su-Tech бесплатен; CropX — датчик от 500 долларов и подписка 300 долларов; CROPWAT бесплатен; цена системы НИИ не опубликована. Оптимизация — учёт погоды, культуры и почвы; у нас пока в модели. Отечественный продукт: Su-Tech и комплекс НИИ — казахстанские, CropX и CROPWAT — нет. Данных с поля у нас пока нет — это честно, поэтому идёт опыт.');

// ===== 12. SWOT =====
s = slide({ section: 'Бизнес', glow: [2.8, 1.4, 7.5, 8.6, -2.6, 6] });
title(s, 'SWOT', '-анализ');
sep(s, 6.67, 2.0, 6.67, 6.85, 2);
sep(s, 0.6, 4.4, 12.73, 4.4, 2);
[['Сильные стороны', LIME, [['device-mobile', 'Бесплатно — нужен только телефон'], ['calculator', 'Формулы проверены на 5 000 случайных смоделированных полях'], ['chart-line-up', 'В модели −15–28% воды']]],
 ['Слабые стороны', WHITE, [['farm', 'Пока нет данных с поля'], ['check-circle', 'Проверка почвы раз в неделю'], ['cloud-rain', 'Зависит от прогноза погоды']]],
 ['Возможности', LIME, [['drop', 'Лимиты воды с 2026 года'], ['chart-bar', 'Цель — 1,3 млн га к 2030'], ['cpu', 'Датчики и автоматика насосов']]],
 ['Угрозы', WHITE, [['warning', 'Систематическая ошибка прогноза'], ['users-three', 'Недоверие к новым приложениям'], ['wifi-slash', 'Нет интернета в поле']]]].forEach(([h, col, items], i) => {
  const x = i % 2 ? 7.0 : 0.8, y = i < 2 ? 2.05 : 4.55, g = i + 3;
  T(s, h, { x, y, w: 5.6, h: 0.5, align: 'center', fontSize: 22, bold: true, color: col }, g);
  items.forEach(([n, t], j) => {
    T(s, '•  ' + t, { x, y: y + 0.62 + j * 0.56, w: 4.7, h: 0.5, valign: 'middle', fontSize: 15, bold: true }, g);
    icon(s, n, col === LIME ? 'lime' : 'white', x + 4.95, y + 0.64 + j * 0.56, 0.44, g);
  });
});
s._after();
s.addNotes('SWOT. Сильные стороны: бесплатно и проверенная математика. Слабая сторона: пока нет данных с поля — поэтому опыт и пилот. Угроза с ошибкой прогноза закрыта кнопкой проверки почвы.');

// ===== 13. ОТЗЫВЫ (hidden until real ones exist) =====
pres.addSection({ title: 'Команда' });
s = slide({ section: 'Команда', blank: true, photo: 'dry', hidden: true, glow: [-2.6, 2.4, 7, 7.6, -3, 7] });
[['[Отзыв фермера или хозяйства, которое попробовало бота.]', '[Имя Фамилия]', '[хозяйство, район]'],
 ['[Отзыв специалиста: агронома, акимата или водного хозяйства.]', '[Имя Фамилия]', '[должность, организация]']].forEach(([q, n, r], i) => {
  const y = 1.3 + i * 2.9, g = i + 2;
  T(s, `"${q}"`, { x: 0.75, y, w: 11.8, h: 1.4, fontSize: 22, bold: true }, g);
  dashed(s, 6.9, y + 1.5, 0.95, 0.95, 'фото', g, true);
  T(s, [{ text: n, options: { bold: true, breakLine: true } }, { text: r, options: { color: PALE } }], { x: 8.0, y: y + 1.62, w: 4.7, h: 0.75, fontSize: 14 }, g);
});
s._after();
s.addNotes('Слайд скрыт. Вставить только настоящие отзывы с разрешения автора и показать слайд (правой кнопкой → Показать слайд).');

// ===== 14. ДОРОЖНАЯ КАРТА =====
s = slide({ section: 'Команда', photo: 'steppe', glow: [-2.2, 1.2, 7, 6.8, 1.2, 7.5] });
title(s, 'Дорожная ', 'карта');
s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 4.1, w: 11.33, h: 0.05, fill: { color: WHITE, transparency: 75 }, line: { type: 'none' }, objectName: 'road-track' });
s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 4.1, w: 4.1, h: 0.05, fill: { color: LIME }, line: { type: 'none' }, objectName: an(2, 'wipe') });
[['сен 2026', 'Бот и Mini App', 1], ['окт 2026', 'ИИ-агроном, serverless', 1], ['ноя 2026', 'Проверка формул, исследование', 1],
 ['дек 2026', 'Опыт с горшками', 0], ['мар 2027', 'Защита проекта', 0], ['лето 2027', 'Пилот: 5 хозяйств', 0], ['осень 2027', 'PRO-подписка и рост', 0]].forEach(([d, t, done], i) => {
  const cx = 1.3 + i * 1.788, g = i + 3, up = i % 2 === 0;
  if (done) {
    s.addShape(pres.shapes.OVAL, { x: cx - 0.24, y: 3.88, w: 0.48, h: 0.48, fill: { color: LIME }, line: { type: 'none' }, objectName: an(g, 'zoom') });
    icon(s, 'check', 'deep', cx - 0.14, 3.98, 0.28, g, 'zoom');
  } else s.addShape(pres.shapes.OVAL, { x: cx - 0.2, y: 3.92, w: 0.4, h: 0.4, fill: { color: '002A20' }, line: { color: LIME, width: 2.25 }, objectName: an(g, 'zoom') });
  const y0 = up ? 2.5 : 4.65;
  T(s, d, { x: cx - 1.0, y: y0, w: 2.0, h: 0.4, align: 'center', fontSize: 18, bold: true, color: done ? LIME : WHITE }, g);
  T(s, t, { x: cx - 1.0, y: y0 + 0.45, w: 2.0, h: 0.75, align: 'center', fontSize: 12.5, color: PALE }, g);
});
credit(s, 'Фото: Wikideas1, Wikimedia Commons, CC0', 6.88);
s._after();
s.addNotes('Бот работает с сентября, в ноябре проверена математика. Дальше — опыт с горшками, защита проекта в марте и пилот на поле летом 2027 года.');

// ===== 15. КОМАНДА =====
s = slide({ section: 'Команда', glow: [3.0, 2.8, 7, -3.2, -2.2, 6.5] });
title(s, 'Наша ', 'команда');
[['Осман Толобек', 'автор: идея, стенд на Arduino, эксперимент'], ['[Наставник]', '[роль]'], ['[Участник команды]', '[роль]']].forEach(([n, r], i) => {
  const x = 0.6 + i * 4.1, g = i + 2;
  dashed(s, x + 0.9, 2.1, 2.1, 2.1, 'фото', g, true);
  T(s, n, { x, y: 4.55, w: 3.9, h: 0.45, align: 'center', fontSize: 20, bold: true }, g);
  T(s, r, { x: x + 0.1, y: 5.08, w: 3.7, h: 0.8, align: 'center', fontSize: 13, color: PALE }, g);
  if (i < 2) sep(s, x + 4.0, 2.1, x + 4.0, 5.9, g);
});
T(s, 'Код написан с помощью ИИ-ассистента; идея, проверка формул, стенд и эксперимент — автора', { x: 0.6, y: 6.4, w: 12.1, h: 0.3, fontSize: 11, color: MUTED }, 5, 'fade');
s._after();
s.addNotes('[Представить себя, наставника и участника команды.] Код я писал с помощью ИИ-ассистента, а идея, проверка формул, стенд и эксперимент — мои.');

// ===== 16. QR =====
s = slide({ section: 'Команда', blank: true, photo: 'fields2', glow: [5.6, -0.6, 8.5, -3, 3.2, 6.5], logo: { x: 0.75, y: 1.15, d: 1.25 } });
T(s, 'SU-TECH', { x: 2.2, y: 1.15, w: 5, h: 1.25, valign: 'middle', fontFace: HEAD, fontSize: 40 }, 2);
T(s, [{ text: 'ПОПРОБУЙТЕ ' }, { text: 'ПРЯМО СЕЙЧАС', options: { color: LIME } }], { x: 0.75, y: 2.7, w: 7.4, h: 1.6, fontFace: HEAD, fontSize: 40 }, 3);
T(s, 'Наведите камеру на QR-код — бот покажет расчёт полива по шагам.', { x: 0.75, y: 4.35, w: 6.9, h: 0.75, fontSize: 18, color: 'D7EEC4' }, 4);
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.75, y: 5.25, w: 6.6, h: 0.72, rectRadius: 0.36, fill: { color: LIME }, line: { type: 'none' }, objectName: an(5) });
T(s, 'Ищем первое хозяйство для пилота в 2027', { x: 0.75, y: 5.25, w: 6.6, h: 0.72, align: 'center', valign: 'middle', fontSize: 18, bold: true, color: DEEP }, 5);
T(s, 'Спасибо! · Осман Толобек · [контакт]', { x: 0.75, y: 6.2, w: 7, h: 0.35, fontSize: 14, color: PALE }, 6, 'fade');
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.5, y: 1.15, w: 4.23, h: 5.3, rectRadius: 0.3, fill: { color: WHITE }, line: { type: 'none' }, objectName: an(3) });
s.addImage({ path: 'm/qr-demo.png', x: 8.92, y: 1.57, w: 3.4, h: 3.4, altText: 'QR-код: бот Su-Tech в демо-режиме', objectName: an(3) });
T(s, 't.me/Su_Tech_bot → /demo', { x: 8.5, y: 5.25, w: 4.23, h: 0.5, align: 'center', fontSize: 16, bold: true, color: DEEP }, 3);
T(s, 'Фото (Wikimedia Commons): Mirfayzbek Abdullayev — Аральское море; Wilfredor — сухая земля; Benoît Prieur — канал (все CC0); Alabama Extension — хлопок (CC0); Wikideas1 — полив (CC0); PSSP — каналы Файсалабада (CC BY 2.0); иконка капель — Flaticon.', { x: 0.75, y: 6.78, w: 11.5, h: 0.25, fontSize: 8.5, color: MUTED });
s._after();
s.addNotes('Наведите камеру на QR-код — бот откроется в демо и покажет весь расчёт по шагам. Мы ищем первое хозяйство для пилота: если вы знаете фермера, который готов попробовать, подойдите ко мне после защиты. Спасибо!');

// ===== 17. ОГРАНИЧЕНИЯ (hidden) =====
s = slide({ section: 'Команда', hidden: true, glow: [6.4, 2.8, 7, -2.6, -2.6, 6.5] });
title(s, 'Ограничения ', 'исследования');
T(s, ['Модель против модели на реальной погоде, а не измерение на поле.',
  'Погода — NASA POWER для областных центров, не метеостанции хозяйств.',
  'Урожай оценён по формуле FAO-33, а не взвешен.',
  'Лучший график подобран со знанием всех сезонов — это выгодно графику.',
  'Глина и суглинок в параметрах проекта имеют одинаковый запас воды.',
  'Потери в каналах (до 50%) Su-Tech не уменьшает — он про воду, дошедшую до поля.'].map((t, i, a) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: i < a.length - 1, paraSpaceAfter: 10 } })),
  { x: 0.75, y: 2.2, w: 11.8, h: 4.4, fontSize: 18, bold: true }, 2);
s._after();
s.addNotes('Скрытый слайд для ответов на вопросы жюри. Подробности: github.com/osmanri/sutech-core → research/README.md');

pres.writeFile({ fileName: OUT }).then(async f => { await applyTheme(f, THEME); console.log('wrote', f); });
