# Заготовка раздела «Author contribution» — ТОЛЬКО ПОСЛЕ эксперимента

Как пользоваться: вставляй этот текст в статью **после** того, как эксперимент проведён, и заменяй каждое `[X]` реальным числом из `experiment/results/`. Пока хотя бы одно `[X]` осталось или утверждение не стало правдой, абзац в статью не идёт. Жюри на интервью спросит про каждое слово.

## English (for the paper)

**Author contribution.** I designed the study, built the physical test stand and ran the experiment. The stand is an Arduino Uno with a relay and pump, soil-moisture, water-level and temperature sensors, and a load-cell scale that weighs each pot. Over [X] weeks I weighed [X] pots every day and recorded [X] measurements; the raw data are published with the code. The weighed measurements show that the model's daily evaporation estimate has an RMSE of [X] mm/day, and that the Su-Tech group used [X]% [less/more] water than the fixed-schedule group with [no significant difference / a difference of X g] in dry mass (Welch test, p = [X], n = [X] per group).

I work as an AI-assisted engineer: I used AI tools for coding, and I selected the methods, set the assumptions, designed and carried out the experiment, and checked the calculations by hand. I can derive every formula in the model and explain every step of the code. Where an AI tool contributed to the code or text, it was reviewed and tested by me.

## По-русски (для себя)

**Мой вклад.** Я сам придумал исследование, собрал стенд и провёл опыт. Стенд: Arduino Uno с реле и помпой, датчики влажности, уровня воды и температуры и весы, которые взвешивают каждый горшок. За [X] недель я ежедневно взвешивал [X] горшков и записал [X] измерений; сырые данные лежат в репозитории вместе с кодом. Взвешивание показало, что модель оценивает суточное испарение с ошибкой RMSE [X] мм/сут, а группа Su-Tech потратила на [X]% [меньше/больше] воды, чем группа по расписанию, при [отсутствии значимой разницы / разнице в X г] сухой массы (тест Уэлча, p = [X], n = [X] в группе).

Я работаю как инженер с использованием ИИ: ИИ помогал писать код, а методы, допущения, план опыта, сам опыт и проверку расчётов вёл я. Я могу вывести каждую формулу модели и объяснить каждый шаг кода.

## Чек-лист перед вставкой (всё должно быть «да»)

- [ ] Опыт проведён, данные лежат в `data/log.csv` и `data/outcomes.csv`
- [ ] `python experiment/analyze.py ...` отработал и дал все числа для `[X]`
- [ ] Я могу вслух объяснить шаги из демо-режима бота (TAW → RAW → ETc → дефицит → объём → насос)
- [ ] Я могу объяснить, почему экономия считается при равном урожае, а не против любого графика
- [ ] Я могу объяснить, чем моя модель отличается от CROPWAT и где её ограничения
- [ ] Использование ИИ раскрыто (в тексте выше или отдельной строкой в статье)
