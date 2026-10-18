import {tr} from './i18n.js';

// Only whole, short social/capability messages are handled locally. A greeting
// followed by symptoms or another task must still go through the domain guard.
const greeting='(?:привет(?:ик)?|здравствуй(?:те)?|доброе утро|добрый (?:день|вечер)|салем(?:етсиз бе)?|сәлем(?:етсіз бе)?|қайырлы (?:таң|күн|кеш)|hello|hi|hey|good (?:morning|afternoon|evening))';
const greetingOnly=new RegExp(`^${greeting}(?: (?:бот|бро|друг|агроном|su tech))?$`,'u');
const greetingPrefix=new RegExp(`^${greeting}(?: (?:бот|бро|друг|агроном|su tech))? `,'u');
const ability=[
 /^(?:ты )?(?:что (?:ты )?умеешь|чем (?:ты )?(?:можешь помочь|поможешь)|как (?:ты )?(?:можешь помочь|работаешь))$/u,
 /^(?:(?:ты )?(?:можешь|сможешь|умеешь)(?: ли)?(?: ты)?|можно)(?: мне)?(?: сделать| делать| провести| проводить| помочь с)? (?:анализ|разбор|диагностику|анализировать|разобрать|проанализировать|помочь)(?: (?:растения|растений|растение))?(?: (?:по фото|фото|фотографии|без фото|без фотографии))?$/u,
 /^(?:сделай|сделать|проведи|провести|нужен|нужна|хочу|хочу сделать|хочу провести|можно) (?:анализ|разбор|диагностику)(?: (?:растения|растений|по фото|фото|без фото|без фотографии))?$/u,
 /^(?:анализ|разбор|диагностика)(?: (?:растений|растения|по фото|фото|без фото|без фотографии))?$/u,
 /^(?:фотосыз |фотомен |фото бойынша )?(?:талдау|анализ|диагностика)(?: (?:жасай аласың ба|жасай аласыз ба|жасайсың ба|жасайсыз ба|жасап бер(?:ші)?|керек))?$/u,
 /^(?:не істей аласың|не істей аласыз|қалай көмектесе аласың|қалай көмектесе аласыз)$/u,
 /^(?:what can you do|how can you help(?: me)?|can you help(?: me)?)$/u,
 /^(?:(?:can|could) you |please )?(?:analy[sz]e|do (?:(?:an|the) )?analysis|make (?:(?:an|the) )?analysis|assess|diagnose)(?: (?:a plant|plants|a photo|a picture|this))?(?: (?:without (?:a |the )?(?:photo|picture)|from (?:a |the )?(?:photo|picture)))?$/u,
 /^(?:без фото|нет фото|фото нет|фото жоқ|фотосыз|no photo|without a photo)$/u
];

export function quickReply(text,lang) {
 const normalized=String(text).normalize('NFKC').toLowerCase().replaceAll('ё','е').replace(/[^\p{L}\p{N}\s]/gu,' ').replace(/\s+/g,' ').trim();
 if(!normalized||normalized.length>160)return null;
 if(greetingOnly.test(normalized))return tr(lang,
  'Привет! 👋 Помогу с растениями, поливом и почвой. Пришли фото или расскажи, что случилось 🌱',
  'Сәлем! 👋 Өсімдік, суару және топырақ туралы көмектесемін. Фото жібер немесе не болғанын жаз 🌱',
  'Hi! 👋 I can help with plants, watering and soil. Send a photo or tell me what is happening 🌱');
 const request=normalized.replace(greetingPrefix,'').replace(/^(?:пожалуйста|өтінемін) /u,'');
 if(/^(?:спасибо(?: большое| тебе| вам)?|большое спасибо|благодарю|рахмет(?: көп| саған| сізге)?|көп рахмет|thanks(?: a lot)?|thank you(?: very much)?)$/u.test(request))return tr(lang,
  'Пожалуйста! 😊 Если появятся вопросы о растениях или поливе — пиши.',
  'Оқасы жоқ! 😊 Өсімдік немесе суару туралы сұрағың болса, жаза бер.',
  'You’re welcome! 😊 Feel free to ask about your plants or watering.');
 if(/^(?:как дела|как ты|қалайсың|қалың қалай|қалайсыз|how are you|how s it going)$/u.test(request))return tr(lang,
  'Я на связи и готов помочь 😊 Как твои растения — всё в порядке?',
  'Көмектесуге дайынмын 😊 Өсімдіктерің қалай, бәрі жақсы ма?',
  'I’m here and ready to help 😊 How are your plants doing?');
 if(ability.some(pattern=>pattern.test(request)))return tr(lang,
  'Да, могу помочь 😊 По фото разберу видимые симптомы, а без фото — по твоему описанию. Подскажу, что проверить и как ухаживать 🌱\n\nКакое растение и что с ним происходит?',
  'Иә, көмектесемін 😊 Фотодан көрінетін белгілерді, ал фотосыз — сипаттамаңды талдаймын. Нені тексеру және қалай күту керегін айтамын 🌱\n\nҚандай өсімдік және не болып жатыр?',
  'Yes, I can help 😊 I can assess visible symptoms in a photo or work from your description without one. I’ll suggest what to check and how to care for the plant 🌱\n\nWhat plant is it, and what is happening?');
 return null;
}

export const aiIntro=lang=>tr(lang,
 'Привет! 👋 Я ИИ-агроном Su-Tech. Помогу разобраться с растениями, поливом и почвой 🌱\n\nПришли фото или просто опиши, что случилось — можно и без фотографии.\n\nФото и вопросы обрабатывает Google Gemini. Оценка по фото предварительная. Ответы сохраняются в истории, фото — нет.',
 'Сәлем! 👋 Мен Su-Tech ЖИ-агрономымын. Өсімдік, суару және топырақ туралы көмектесемін 🌱\n\nФото жібер немесе не болғанын жаз — фотосыз да болады.\n\nФото мен сұрақты Google Gemini өңдейді. Фото бойынша бағалау алдын ала жасалады. Жауаптар тарихта сақталады, фотолар сақталмайды.',
 'Hi! 👋 I’m Su-Tech’s AI agronomist. I can help with plants, watering and soil 🌱\n\nSend a photo or tell me what is happening — a photo is optional.\n\nGoogle Gemini processes photos and questions. Photo assessments are preliminary. Answers are saved in history; photos are not stored.');

export const CONVERSATION_STYLE=`
Use a warm, natural, conversational tone, like a helpful agronomist in a chat.
Match the user's level of formality. Avoid bureaucratic wording, lectures and
repeating your role or restrictions in every reply. Use 1-3 relevant emoji such
as 🌱, 💧, 🔎, 😊 or 📸 when they fit; vary them and do not decorate every line.
Greet back briefly when greeted; acknowledge thanks naturally. If asked whether
you can analyze a plant without a photo, say yes: you can help from a description,
then ask which plant and what symptoms. Do not demand a photo for every question.
Do not claim to see an image when none is attached. For ordinary questions,
answer naturally instead of forcing a diagnostic template. For actual plant
photos, keep the useful assessment structure and express uncertainty briefly.
Friendly wording does not change the agronomy scope or factual boundaries.
`;
