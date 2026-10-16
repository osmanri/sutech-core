import {DOMAIN_ROOTS} from './copy.js';
const normalize=s=>String(s).normalize('NFKC').toLowerCase().replaceAll('ё','е');
export function hasDomain(text) {
  text=normalize(text);const words=text.match(/[\p{L}\p{N}_-]+/gu)??[];
  return /su[\s-]+tech|су[\s-]+тех|о проекте|об этом проекте|наш проект|наш сервис|нашего проекта|что (ты )?умеешь|какие функции|бизнес модель|жоба туралы|жобаның|не істей аласың|about (this |the )?project|business model|what can you do|project features/u.test(text)||words.some(w=>DOMAIN_ROOTS.some(r=>w.startsWith(r)));
}
export function inScope(text,history=[],hasImage=false) {
  text=normalize(text).trim();
  if(/(?:^|[^\p{L}])(?:столиц|президент|политик|биткоин|криптовалют|футбол|фильм|анекдот|гороскоп|сочинени|стих|capital|president|politics|bitcoin|crypto|football|movie|joke|horoscope|poem|essay|астана|саясат)[\p{L}]*|(?:игнорируй|забудь|ignore|forget).{0,35}(?:инструкц|правил|роль|instructions|rules|role)/u.test(text))return false;
  if(hasImage||hasDomain(text))return true;
  if(text.length>180||!history.length||!/^(?:(?:а|и|and|but)\s+)?(?:как|что|чем|почему|сколько|когда|где|какие|какой|можно|нужно|надо|объясни|поясни|подробнее|продолжи|провер|обработ|помог|это|они|он|она|да|нет|не|два|три|how|what|why|when|where|which|can|should|explain|more|continue|yes|no|it|they|check|two|three|қалай|неге|қашан|қанша|қай|не|түсіндір|иә|жоқ)(?:[^\p{L}]|$)|^\d/u.test(text))return false;
  const previous=history.filter(h=>h.role==='user').flatMap(h=>h.parts??[]).map(p=>p.text??'').join(' ');
  return hasDomain(previous)||previous.includes('[new plant photo');
}
