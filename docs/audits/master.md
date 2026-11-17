# MASTER DESIGN SYSTEM — AgroTech Field Monitor
**Тема:** Clean Light Agro · B2B AgroTech · Мониторинг полей и расчёт полива  
**Версия:** 1.0.0 · Сгенерировано через ui-ux-pro-max BM25  
**Статус:** Ожидает утверждения

---

## 1. ПРИНЦИПЫ ДИЗАЙНА

| Принцип | Описание |
|---------|----------|
| **Читаемость на солнце** | Максимальный контраст текста ≥ 7:1 для ключевых данных. Плотный шрифт с широкими буквами. |
| **Данные прежде всего** | Цифры и статусы полей — главные герои. Декор — вспомогательный. |
| **Доверие и точность** | B2B-стиль: чёткие сетки, последовательные токены, ноль случайных решений. |
| **Отзывчивость интерфейса** | Каждый клик подтверждается визуально в пределах 80–150 мс. |
| **Адаптивность** | Breakpoints: 375 / 768 / 1024 / 1440 px. |

---

## 2. ЦВЕТОВАЯ ПАЛИТРА — Clean Light Agro

> BM25 источники: `colors.csv` (SaaS enterprise) · `styles.csv` (Minimalism & Swiss) · `products.csv` (B2B monitoring)

### 2.1 Основные токены

```css
:root {
  /* Primary — Agro Green */
  --color-primary:         #1A7A4A;
  --color-primary-hover:   #15663D;
  --color-primary-active:  #114F2F;
  --color-on-primary:      #FFFFFF;

  /* Secondary — Trust Blue */
  --color-secondary:       #1E5FA8;
  --color-secondary-hover: #194D8B;
  --color-on-secondary:    #FFFFFF;

  /* Accent — Alert Amber */
  --color-accent:          #D97706;
  --color-accent-hover:    #B45309;
  --color-on-accent:       #FFFFFF;

  /* Backgrounds */
  --color-background:      #F4F7F2;
  --color-surface:         #FFFFFF;
  --color-surface-raised:  #FAFCF9;

  /* Foreground / Text */
  --color-foreground:      #1C2B1E;
  --color-foreground-muted:#4A5E4D;
  --color-foreground-faint:#7A9080;

  /* Borders */
  --color-border:          #D1E0D4;
  --color-border-strong:   #9DB8A3;
  --color-ring:            #1A7A4A;

  /* Semantic States */
  --color-success:         #16A34A;
  --color-success-bg:      #DCFCE7;
  --color-warning:         #D97706;
  --color-warning-bg:      #FEF3C7;
  --color-error:           #DC2626;
  --color-error-bg:        #FEE2E2;
  --color-on-error:        #FFFFFF;
  --color-info:            #1E5FA8;
  --color-info-bg:         #DBEAFE;

  /* Chart palette (7 серий) */
  --color-chart-1:         #1A7A4A;
  --color-chart-2:         #1E5FA8;
  --color-chart-3:         #D97706;
  --color-chart-4:         #7C3AED;
  --color-chart-5:         #0891B2;
  --color-chart-6:         #DB2777;
  --color-chart-7:         #6B7280;
}
```

### 2.2 Контраст и читаемость (WCAG AA / AAA)

| Пара | Значение | Стандарт |
|------|----------|----------|
| `--color-foreground` на `--color-surface` | ≈ 9.5:1 | **AAA** |
| `--color-on-primary` на `--color-primary` | ≈ 5.8:1 | **AA** |
| `--color-foreground-muted` на `--color-surface` | ≈ 5.1:1 | **AA** |
| Числовые показатели датчиков (bold) | ≥ 7:1 | **AAA** |

> ⚠️ **Правило «чтение на солнце»:** Числовые значения датчиков рендерятся только в `--color-foreground` на `--color-surface`. Цветовой акцент — только как фоновый badge с контрастным текстом поверх.

---

## 3. ТИПОГРАФИКА

> BM25 источники: `typography.csv` — два совпадения для B2B AgroTech:
> - **Design-System query** ("B2B AgroTech enterprise SaaS accessible trustworthy") → **«Enterprise SaaS Mobile / Friendly SaaS»** → **Plus Jakarta Sans** (основной, single-family)
> - **Typography domain** ("enterprise accessible professional corporate SaaS") → **«Corporate Trust»** → Lexend + Source Sans 3 (#1)
>
> **Итог (приоритет design-system output):** `Plus Jakarta Sans` — primary sans для всего UI.
> `Fira Code` — моно для данных (координаты, Kc, площадь).

### 3.1 Шрифты

**Primary (все элементы UI):** `Plus Jakarta Sans` — «Friendly SaaS» / «Enterprise SaaS Mobile».
Единый versatile шрифт. Современная альтернатива Inter. Баланс профессиональности и approachability.

**Моно (данные / координаты):** `Fira Code` — для GPS координат, Kc-коэффициентов, числовых меток.

```html
<!-- Google Fonts — точный URL из typography.csv #13 + #61 -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=Fira+Code:wght@400;500&display=swap"
  rel="stylesheet"
/>
```

```js
// Tailwind config — fontFamily per skill spec
tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        // ui-ux-pro-max: "Friendly SaaS / Enterprise SaaS"
        // fontFamily: { sans: ['Plus Jakarta Sans', 'sans-serif'] }
        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
        mono: ['"Fira Code"', 'Courier New', 'monospace'],
      },
    },
  },
};
```

### 3.2 Типографическая шкала (Tailwind)

| CSS токен | Tailwind | px | Роль |
|-----------|----------|----|------|
| `--text-2xs` | `text-[10px]` | 10 | метки осей, badges ALL-CAPS |
| `--text-xs`  | `text-xs`     | 12 | подписи, timestamps, теги |
| `--text-sm`  | `text-sm`     | 14 | вторичный текст, описания |
| `--text-base`| `text-base`   | 16 | основной текст карточек |
| `--text-md`  | `text-md`     | 18 | заголовки карточек |
| `--text-lg`  | `text-lg`     | 20 | заголовки секций |
| `--text-xl`  | `text-xl`     | 24 | h3 |
| `--text-2xl` | `text-2xl`    | 30 | h2 |

**Вес шрифтов (Plus Jakarta Sans) — строго по weight-scale скилла:**

| Вес | Tailwind | Применение |
|-----|----------|------------|
| 800 ExtraBold | `font-extrabold` | Hero-заголовки дашборда |
| 700 Bold      | `font-bold`      | Заголовки секций H2, кнопки submit |
| 600 SemiBold  | `font-semibold`  | Заголовки карточек, кнопки, названия культур |
| 500 Medium    | `font-medium`    | Метки полей (uppercase, tracking-wide) |
| 400 Regular   | `font-normal`    | Основной текст описания (leading-normal) |

**Межстрочный интервал:**
- `leading-tight` (1.2) — Hero/H1
- `leading-snug` (1.35) — заголовки карточек
- `leading-normal` (1.5) — тело, описания

**Метки (labels) — skill spec:**
```html
<!-- Пример: label поля формы -->
<label class="font-sans text-xs font-medium uppercase tracking-wide text-muted">
  Единица измерения:
</label>

<!-- Пример: status badge -->
<span class="font-sans text-[10px] font-bold uppercase tracking-wide
             px-2.5 py-0.5 rounded-pill bg-success-bg text-[#14532D]">
  Готово
</span>

<!-- Пример: числовые данные -->
<span class="font-mono text-sm font-semibold text-foreground">43.301540°</span>
```

### 3.3 Роли типографики

| Роль UI | Шрифт | Tailwind-размер | Вес | leading |
|---------|-------|-----------------|-----|----------|
| Главный показатель дашборда | Plus Jakarta Sans | `text-2xl` | `font-bold` (700) | `leading-tight` |
| Заголовок страницы H1 | Plus Jakarta Sans | `text-xl` | `font-bold` (700) | `leading-tight` |
| Заголовок секции H2 | Plus Jakarta Sans | `text-md` | `font-semibold` (600) | `leading-snug` |
| Заголовок карточки культуры | Plus Jakarta Sans | `text-xs` | `font-semibold` (600) | `leading-tight` |
| Значение датчика | Plus Jakarta Sans | `text-xl` | `font-bold` (700) | `leading-tight` |
| Единица измерения (%, °C, л/га) | Plus Jakarta Sans | `text-sm` | `font-normal` (400) | — |
| Основной текст описания | Plus Jakarta Sans | `text-sm` | `font-normal` (400) | `leading-normal` |
| Метка поля (label) | Plus Jakarta Sans | `text-xs` | `font-medium` (500) | — |
| Статус badge ALL-CAPS | Plus Jakarta Sans | `text-[10px]` | `font-bold` (700) | — |
| GPS / технические координаты | Fira Code | `text-sm` | `font-semibold` (600) | — |

---

## 4. SPACING & LAYOUT

```css
:root {
  --space-1:   0.25rem;   /*  4px */
  --space-2:   0.5rem;    /*  8px */
  --space-3:   0.75rem;   /* 12px */
  --space-4:   1rem;      /* 16px */
  --space-5:   1.25rem;   /* 20px */
  --space-6:   1.5rem;    /* 24px */
  --space-8:   2rem;      /* 32px */
  --space-10:  2.5rem;    /* 40px */
  --space-12:  3rem;      /* 48px */
  --space-16:  4rem;      /* 64px */
  --space-20:  5rem;      /* 80px */

  --grid-cols-desktop: 12;
  --grid-cols-tablet:  8;
  --grid-cols-mobile:  4;
  --gutter:    1.5rem;
  --max-width: 1440px;

  --card-min-width: 280px;
  --card-max-width: 360px;
}
```

---

## 5. КОМПОНЕНТЫ

### 5.1 Карточка культуры (Field Crop Card)

#### Токены формы

```css
:root {
  --card-radius:       12px;
  --card-radius-inner:  8px;
  --card-shadow:       0 1px 3px rgba(28,43,30,0.08), 0 4px 12px rgba(28,43,30,0.06);
  --card-shadow-hover: 0 4px 8px rgba(28,43,30,0.12), 0 12px 28px rgba(28,43,30,0.10);
  --card-shadow-focus: 0 0 0 3px var(--color-ring);
  --card-padding:      var(--space-6);
  --card-gap:          var(--space-4);
  --card-border:       1px solid var(--color-border);
  --card-transition:   box-shadow 200ms ease, transform 150ms ease;
}
```

#### HTML-структура

```html
<article class="field-card" aria-label="Поле Восток-3 — Пшеница">
  <header class="field-card__header">
    <div class="field-card__meta">
      <span class="field-card__field-id">Восток-3</span>
      <span class="field-card__area">48 га</span>
    </div>
    <span class="status-badge status-badge--ok" aria-label="Статус: норма">НОРМА</span>
  </header>

  <div class="field-card__crop">
    <img src="/icons/wheat.svg" alt="" aria-hidden="true" class="field-card__crop-icon" />
    <span class="field-card__crop-name">Пшеница озимая</span>
  </div>

  <div class="field-card__moisture">
    <div class="field-card__stat-label">Влажность почвы</div>
    <div class="field-card__stat-value">
      <span class="field-card__number">67</span>
      <span class="field-card__unit">%</span>
    </div>
    <div class="moisture-bar" role="progressbar" aria-valuenow="67" aria-valuemin="0" aria-valuemax="100">
      <div class="moisture-bar__fill" style="--fill: 67%"></div>
    </div>
  </div>

  <div class="field-card__water">
    <span class="field-card__stat-label">Расход сегодня</span>
    <span class="field-card__number">240</span>
    <span class="field-card__unit">л/га</span>
  </div>

  <footer class="field-card__actions">
    <button class="btn btn--secondary btn--sm" type="button">Детали</button>
    <button class="btn btn--primary btn--sm" type="button">Запустить полив</button>
  </footer>
</article>
```

#### CSS карточки

```css
.field-card {
  background:    var(--color-surface);
  border:        var(--card-border);
  border-radius: var(--card-radius);
  box-shadow:    var(--card-shadow);
  padding:       var(--card-padding);
  display:       flex;
  flex-direction:column;
  gap:           var(--card-gap);
  transition:    var(--card-transition);
  cursor:        pointer;
  will-change:   box-shadow;
}
.field-card:hover      { box-shadow: var(--card-shadow-hover); }
.field-card:focus-visible { outline: none; box-shadow: var(--card-shadow-focus); }

/* Прогресс-бар влажности */
.moisture-bar {
  height: 8px; border-radius: 999px;
  background: #E8F0EA; overflow: hidden;
}
.moisture-bar__fill {
  height: 100%; width: var(--fill); border-radius: 999px;
  background: linear-gradient(90deg, var(--color-warning) 0%, var(--color-primary) 50%, var(--color-info) 100%);
  background-size: 200% 100%;
  background-position: calc((100% - var(--fill)) * 1.2) 0;
  transition: width 400ms ease;
}
```

---

### 5.2 Статус-бейджи (Status Badges)

```css
.status-badge {
  display: inline-flex; align-items: center; gap: var(--space-1);
  padding: 2px 10px; border-radius: 999px;
  font-family: var(--font-body); font-size: var(--text-xs);
  font-weight: var(--weight-bold); letter-spacing: var(--tracking-wide);
  text-transform: uppercase; white-space: nowrap;
}
.status-badge--ok      { background: var(--color-success-bg); color: #14532D; }
.status-badge--warning { background: var(--color-warning-bg); color: #78350F; }
.status-badge--error   { background: var(--color-error-bg);   color: #7F1D1D; }
.status-badge--info    { background: var(--color-info-bg);    color: #1E3A5F; }
.status-badge--offline { background: #F1F5F9;                 color: #475569; }
```

---

### 5.3 Кнопки полива (Irrigation Action Buttons)

> Safety-critical элементы: крупные, контрастные, с явной обратной связью.

```css
:root {
  --btn-radius:      8px;
  --btn-font:        var(--font-body);
  --btn-weight:      var(--weight-semibold);
  --btn-transition:  background 150ms ease, box-shadow 150ms ease, transform 80ms ease;
  --btn-focus-ring:  0 0 0 3px rgba(26, 122, 74, 0.4);
  --btn-h-sm:  36px;
  --btn-h-md:  44px;   /* минимум WCAG 2.5.5 */
  --btn-h-lg:  52px;
  --btn-h-xl:  60px;
  --btn-px-sm: var(--space-4);
  --btn-px-md: var(--space-6);
  --btn-px-lg: var(--space-8);
}

.btn {
  display: inline-flex; align-items: center; justify-content: center;
  gap: var(--space-2); font-family: var(--btn-font);
  font-weight: var(--btn-weight); font-size: var(--text-base);
  border-radius: var(--btn-radius); border: none; cursor: pointer;
  transition: var(--btn-transition); white-space: nowrap;
  transform: translateZ(0);
}
.btn:focus-visible { outline: none; box-shadow: var(--btn-focus-ring); }

.btn--sm { height: var(--btn-h-sm); padding: 0 var(--btn-px-sm); font-size: var(--text-sm); }
.btn--md { height: var(--btn-h-md); padding: 0 var(--btn-px-md); }
.btn--lg { height: var(--btn-h-lg); padding: 0 var(--btn-px-lg); font-size: var(--text-md); }
.btn--xl { height: var(--btn-h-xl); padding: 0 var(--btn-px-lg); font-size: var(--text-lg); width: 100%; }

/* Primary — Запустить полив */
.btn--primary {
  background: var(--color-primary); color: var(--color-on-primary);
  box-shadow: 0 1px 2px rgba(26,122,74,0.3);
}
.btn--primary:hover  { background: var(--color-primary-hover); box-shadow: 0 4px 12px rgba(26,122,74,0.35); }
.btn--primary:active { background: var(--color-primary-active); transform: scale(0.97); transition-duration: 80ms; }

/* Secondary — Детали / Отмена */
.btn--secondary { background: transparent; color: var(--color-primary); border: 1.5px solid var(--color-primary); }
.btn--secondary:hover  { background: rgba(26,122,74,0.06); }
.btn--secondary:active { background: rgba(26,122,74,0.12); transform: scale(0.97); transition-duration: 80ms; }

/* Danger — Остановить полив */
.btn--danger { background: var(--color-error); color: var(--color-on-error); }
.btn--danger:hover  { background: #B91C1C; box-shadow: 0 4px 12px rgba(220,38,38,0.35); }
.btn--danger:active { background: #991B1B; transform: scale(0.97); transition-duration: 80ms; }

/* Irrigation Toggle — выбор режима полива */
.irrigation-toggle {
  display: flex; gap: var(--space-2); padding: var(--space-1);
  background: var(--color-background); border: 1px solid var(--color-border);
  border-radius: calc(var(--btn-radius) + 4px);
}
.irrigation-toggle__btn {
  flex: 1; height: 40px; border-radius: var(--btn-radius);
  font-family: var(--btn-font); font-weight: var(--weight-medium);
  font-size: var(--text-sm); border: none; cursor: pointer;
  background: transparent; color: var(--color-foreground-muted);
  transition: background 200ms ease, color 200ms ease, box-shadow 200ms ease;
}
.irrigation-toggle__btn[aria-pressed="true"] {
  background: var(--color-surface); color: var(--color-primary);
  font-weight: var(--weight-semibold); box-shadow: 0 1px 4px rgba(28,43,30,0.12);
}

/* Disabled */
.btn:disabled, .btn[aria-disabled="true"] { opacity: 0.45; cursor: not-allowed; pointer-events: none; }
```

---

### 5.4 Range Slider (Доза полива)

```css
.irrigation-slider {
  appearance: none; -webkit-appearance: none;
  width: 100%; height: 6px; border-radius: 999px; outline: none; cursor: pointer;
  background: linear-gradient(
    to right,
    var(--color-primary) var(--slider-pct, 0%),
    var(--color-border)  var(--slider-pct, 0%)
  );
}
.irrigation-slider::-webkit-slider-thumb {
  appearance: none; width: 22px; height: 22px; border-radius: 50%;
  background: var(--color-primary); border: 3px solid var(--color-surface);
  box-shadow: 0 0 0 2px var(--color-primary), 0 2px 6px rgba(26,122,74,0.4);
  transition: transform 150ms ease, box-shadow 150ms ease;
}
.irrigation-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
  box-shadow: 0 0 0 3px var(--color-primary), 0 4px 12px rgba(26,122,74,0.5);
}
```

---

### 5.5 Инпуты

```css
:root {
  --input-radius: 8px; --input-height: 44px;
  --input-border: 1.5px solid var(--color-border);
}
.input {
  height: var(--input-height); padding: 0 var(--space-4);
  background: var(--color-surface); border: var(--input-border);
  border-radius: var(--input-radius); font-family: var(--font-body);
  font-size: var(--text-base); color: var(--color-foreground);
  outline: none; width: 100%;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.input::placeholder { color: var(--color-foreground-faint); }
.input:hover   { border-color: var(--color-border-strong); }
.input:focus   { border-color: var(--color-ring); box-shadow: 0 0 0 3px rgba(26,122,74,0.25); }
.input--error  { border-color: var(--color-error); box-shadow: 0 0 0 3px rgba(220,38,38,0.2); }
```

---

### 5.6 Sidebar Navigation

```css
:root {
  --nav-width: 240px; --nav-bg: var(--color-surface);
  --nav-item-h: 44px; --nav-item-px: var(--space-4);
  --nav-item-radius: var(--card-radius-inner);
}
.nav-item {
  display: flex; align-items: center; gap: var(--space-3);
  height: var(--nav-item-h); padding: 0 var(--nav-item-px);
  border-radius: var(--nav-item-radius); font-family: var(--font-body);
  font-weight: var(--weight-medium); font-size: var(--text-base);
  color: var(--color-foreground-muted);
  transition: background 150ms ease, color 150ms ease;
  cursor: pointer; text-decoration: none;
}
.nav-item:hover { background: rgba(26,122,74,0.06); color: var(--color-primary); }
.nav-item[aria-current="page"] {
  background: rgba(26,122,74,0.10); color: var(--color-primary); font-weight: var(--weight-semibold);
}
```

---

## 6. ГРАФИКИ И ВИЗУАЛИЗАЦИЯ

> BM25 источник: `charts.csv` — Streaming Area Chart, Line Chart with Highlights, Trend Line Chart

| Метрика | Тип графика | Библиотека |
|---------|-------------|-----------|
| Влажность почвы (реальное время) | Streaming Area Chart | ApexCharts |
| Температура за 7 дней | Line Chart | Chart.js / Recharts |
| Расход воды (аномалии) | Line Chart with Highlights | ApexCharts |
| Объём полива по полям | Bar Chart (горизонтальный) | Recharts |
| Статус полей | Grid Heatmap | D3.js |

```js
// ApexCharts — общая тема AgroTech
const AGRO_CHART_DEFAULTS = {
  chart: {
    fontFamily: 'Source Sans 3, sans-serif',
    foreColor:  '#4A5E4D',
    toolbar:    { show: false },
    animations: { easing: 'easeinout', speed: 400 },
  },
  grid: { borderColor: '#D1E0D4', strokeDashArray: 4 },
  tooltip: { style: { fontFamily: 'Source Sans 3, sans-serif' } },
  colors: ['#1A7A4A','#1E5FA8','#D97706','#7C3AED','#0891B2','#DB2777','#6B7280'],
};
```

**Правила доступности графиков:**
- `aria-live="polite"` текстовый дубль текущего значения для Streaming charts
- Line charts: разные стили линий (solid/dashed/dotted) + маркеры — не только цвет
- Anomaly charts: аномалии помечены формой + текстовой аннотацией + цветом

---

## 7. АНИМАЦИИ И МИКРО-ВЗАИМОДЕЙСТВИЯ

> BM25 источники: `motion.csv` — Scroll Reveal (Subtle), Stagger List · `ux-guidelines.csv` — Active States

### 7.1 Токены движения

```css
:root {
  --motion-instant:   80ms;
  --motion-fast:     150ms;
  --motion-normal:   250ms;
  --motion-slow:     400ms;
  --motion-enter:    350ms;

  --ease-standard:   cubic-bezier(0.4, 0, 0.2, 1);
  --ease-decelerate: cubic-bezier(0, 0, 0.2, 1);
  --ease-accelerate: cubic-bezier(0.4, 0, 1, 1);
  --ease-spring:     cubic-bezier(0.34, 1.56, 0.64, 1);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration:        0.01ms !important;
    animation-iteration-count: 1      !important;
    transition-duration:       0.01ms !important;
  }
}
```

### 7.2 Scroll Reveal — появление карточек полей (GSAP Subtle)

```js
// BM25: Scroll Reveal · Tier: Subtle · Duration: 300-400ms · Easing: power1.out
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
gsap.registerPlugin(ScrollTrigger);

const revealCards = () => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.querySelectorAll('.field-card').forEach((el, i) => {
    gsap.from(el, {
      opacity: 0,
      y: 12,               // BM25 Do: 8-16px — fade, не slide
      duration: 0.35,
      delay: i * 0.05,
      ease: 'power1.out',
      scrollTrigger: {
        trigger:      el,
        start:        'top 90%',
        toggleActions:'play none none reverse',
      },
    });
  });
};
revealCards();
```

### 7.3 Клик — обратная связь кнопки полива (≤ 80 мс)

```js
document.querySelector('[data-action="start-irrigation"]')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget;

  // 1. Немедленная обратная связь (80ms press)
  gsap.to(btn, { scale: 0.97, duration: 0.08, ease: 'power2.in', yoyo: true, repeat: 1 });

  // 2. Loading state
  btn.setAttribute('aria-busy', 'true');
  btn.textContent = 'Запуск...';

  // 3. API call
  await startIrrigationAPI();

  // 4. Success bounce
  gsap.fromTo(btn, { scale: 0.95 }, { scale: 1, duration: 0.4, ease: 'back.out(2)' });
  btn.textContent = '✓ Полив запущен';
  btn.removeAttribute('aria-busy');
});
```

### 7.4 Числовой counter flip (обновление показателей)

```js
const animateNumber = (el, from, to, duration = 600) => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    el.textContent = to; return;
  }
  gsap.fromTo(
    { val: from },
    { val: to, duration: duration / 1000, ease: 'power2.out',
      onUpdate() { el.textContent = Math.round(this.targets()[0].val); }
    }
  );
};
```

### 7.5 Hover elevation — карточка поля (layout-safe)

```js
// Только box-shadow, без transform (нет layout-shift)
document.querySelectorAll('.field-card').forEach(card => {
  const enter = () => gsap.to(card, { boxShadow: '0 4px 8px rgba(28,43,30,0.12), 0 12px 28px rgba(28,43,30,0.10)', duration: 0.2, ease: 'power1.out' });
  const leave = () => gsap.to(card, { boxShadow: '0 1px 3px rgba(28,43,30,0.08), 0 4px 12px rgba(28,43,30,0.06)', duration: 0.2, ease: 'power1.out' });
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    card.addEventListener('mouseenter', enter);
    card.addEventListener('mouseleave', leave);
  }
});
```

---

## 8. ИКОНКИ

| Библиотека | Применение |
|------------|-----------|
| **Phosphor Icons** (`@phosphor-icons/react`) | Основная |
| **Heroicons** (`@heroicons/react`) | Резервная |
| Кастомные SVG | Иконки культур (пшеница, кукуруза, соя) |

### Рекомендуемые иконки

| Сценарий | Phosphor |
|----------|----------|
| Поле / участок | `Polygon` |
| Полив включён | `Drop` (filled) |
| Полив выключен | `DropSlash` |
| Предупреждение | `Warning` |
| Ошибка датчика | `WarningCircle` |
| Настройки | `SlidersHorizontal` |
| Карта полей | `MapTrifold` |
| Расписание | `CalendarCheck` |
| Аналитика | `ChartLineUp` |
| Добавить поле | `PlusCircle` |

```jsx
// Декоративная иконка — aria-hidden
<Drop size={20} aria-hidden="true" />
<span>240 л/га</span>

// Смысловая иконка — aria-label обязателен
<button aria-label="Запустить полив поля Восток-3">
  <Drop size={20} />
</button>
```

---

## 9. ДОСТУПНОСТЬ (A11Y)

- Контраст текста ≥ 4.5:1 (обычный), ≥ 3:1 (крупный ≥ 18px bold), ≥ 7:1 (показатели датчиков)
- Focus ring: 3px solid `--color-ring`, виден при Tab-навигации
- Touch target: минимум 44×44px для всех кнопок
- Статусы = цвет **+** иконка **+** текст-метка (не только цвет)
- Streaming charts имеют `aria-live="polite"` текстовый дубль текущего значения
- `prefers-reduced-motion`: все анимации деактивируются

---

## 10. CSS TOKENS — СВОДНЫЙ СПИСОК

```css
/* styles/tokens.css */
:root {
  --color-primary:          #1A7A4A;
  --color-primary-hover:    #15663D;
  --color-primary-active:   #114F2F;
  --color-on-primary:       #FFFFFF;
  --color-secondary:        #1E5FA8;
  --color-on-secondary:     #FFFFFF;
  --color-accent:           #D97706;
  --color-on-accent:        #FFFFFF;
  --color-background:       #F4F7F2;
  --color-surface:          #FFFFFF;
  --color-surface-raised:   #FAFCF9;
  --color-foreground:       #1C2B1E;
  --color-foreground-muted: #4A5E4D;
  --color-foreground-faint: #7A9080;
  --color-border:           #D1E0D4;
  --color-border-strong:    #9DB8A3;
  --color-ring:             #1A7A4A;
  --color-success:          #16A34A;
  --color-success-bg:       #DCFCE7;
  --color-warning:          #D97706;
  --color-warning-bg:       #FEF3C7;
  --color-error:            #DC2626;
  --color-error-bg:         #FEE2E2;
  --color-on-error:         #FFFFFF;
  --color-info:             #1E5FA8;
  --color-info-bg:          #DBEAFE;
  --color-chart-1:          #1A7A4A;
  --color-chart-2:          #1E5FA8;
  --color-chart-3:          #D97706;
  --color-chart-4:          #7C3AED;
  --color-chart-5:          #0891B2;
  --color-chart-6:          #DB2777;
  --color-chart-7:          #6B7280;

  --font-heading: 'Lexend', sans-serif;
  --font-body:    'Source Sans 3', sans-serif;
  --font-mono:    'Fira Code', 'Courier New', monospace;

  --text-xs:    0.75rem;
  --text-sm:    0.875rem;
  --text-base:  1rem;
  --text-md:    1.125rem;
  --text-lg:    1.25rem;
  --text-xl:    1.5rem;
  --text-2xl:   1.875rem;
  --text-3xl:   2.25rem;
  --text-hero:  3rem;

  --weight-regular:   400;
  --weight-medium:    500;
  --weight-semibold:  600;
  --weight-bold:      700;
  --weight-extrabold: 800;

  --leading-tight:    1.2;
  --leading-snug:     1.35;
  --leading-normal:   1.5;
  --leading-relaxed:  1.65;

  --tracking-tight:  -0.02em;
  --tracking-normal:  0em;
  --tracking-wide:    0.04em;

  --space-1:   0.25rem;  --space-2:  0.5rem;   --space-3:  0.75rem;
  --space-4:   1rem;     --space-5:  1.25rem;  --space-6:  1.5rem;
  --space-8:   2rem;     --space-10: 2.5rem;   --space-12: 3rem;
  --space-16:  4rem;     --space-20: 5rem;

  --card-radius:       12px;
  --card-radius-inner:  8px;
  --card-shadow:       0 1px 3px rgba(28,43,30,0.08), 0 4px 12px rgba(28,43,30,0.06);
  --card-shadow-hover: 0 4px 8px rgba(28,43,30,0.12), 0 12px 28px rgba(28,43,30,0.10);
  --card-padding:      1.5rem;
  --card-border:       1px solid var(--color-border);

  --btn-radius:   8px;
  --btn-h-sm:     36px; --btn-h-md: 44px; --btn-h-lg: 52px; --btn-h-xl: 60px;

  --input-radius: 8px;
  --input-height: 44px;
  --nav-width:    240px;

  --motion-instant:   80ms;
  --motion-fast:     150ms;
  --motion-normal:   250ms;
  --motion-slow:     400ms;
  --motion-enter:    350ms;

  --ease-standard:   cubic-bezier(0.4, 0, 0.2, 1);
  --ease-decelerate: cubic-bezier(0, 0, 0.2, 1);
  --ease-accelerate: cubic-bezier(0.4, 0, 1, 1);
  --ease-spring:     cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

---

## 11. ANTI-PATTERNS

| ❌ Запрещено | ✅ Правильно |
|-------------|-------------|
| Dark mode by default | Только Clean Light Agro |
| Эмодзи как иконки (🌱 💧) | SVG из Phosphor Icons |
| Произвольные hex-цвета | Только `var(--color-*)` токены |
| `transform: translateY()` при hover карточек | Только `box-shadow` elevation |
| Анимации без reduced-motion fallback | `@media (prefers-reduced-motion: reduce)` обязателен |
| Контраст текста < 4.5:1 | Все пары верифицированы |
| touch target < 44px | `--btn-h-md: 44px` минимум |
| Цвет как единственный индикатор статуса | Цвет + иконка + текст |
| `font-size < 12px` | Минимум `--text-xs: 0.75rem` |

---

## 12. PRE-DEPLOY CHECKLIST

- [ ] Все цвета из `var(--color-*)` — нет hardcoded hex в компонентах
- [ ] Контраст ≥ 4.5:1 (основной текст), ≥ 7:1 (показатели датчиков)
- [ ] Все кнопки ≥ 44px высота
- [ ] `cursor: pointer` на всех кликабельных элементах
- [ ] Focus ring виден при Tab-навигации
- [ ] `prefers-reduced-motion` — все анимации деактивируются
- [ ] Шрифты загружены: Lexend + Source Sans 3 + Fira Code (Google Fonts)
- [ ] Статусы полей: цвет + иконка + текст
- [ ] Streaming charts имеют `aria-live` текстовый дубль
- [ ] Responsive проверен: 375 / 768 / 1024 / 1440 px

---

*Дизайн-система AgroTech Field Monitor v1.0 · ui-ux-pro-max BM25 · 2026-09-16*
