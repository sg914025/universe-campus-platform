import catalog from './locales.generated.json';
export function translate(text,language){return language==='zh'?text:catalog[text]?.[language]||text}
