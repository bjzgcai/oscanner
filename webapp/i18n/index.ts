import type { Locale, Messages } from './types';
import { zhCN } from './zh-CN';
import { enUS } from './en-US';

export const DEFAULT_LOCALE: Locale = 'zh-CN';

export const LOCALES: Array<{ key: Locale; label: string }> = [
  { key: 'zh-CN', label: '中文' },
  { key: 'en-US', label: 'English' },
];

const MESSAGES_BY_LOCALE: Record<Locale, Messages> = {
  'zh-CN': zhCN,
  'en-US': enUS,
};

export function getMessages(locale: Locale): Messages {
  return MESSAGES_BY_LOCALE[locale] || MESSAGES_BY_LOCALE[DEFAULT_LOCALE];
}

export function isLocale(v: string): v is Locale {
  return v === 'zh-CN' || v === 'en-US';
}


