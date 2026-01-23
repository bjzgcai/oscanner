'use client';

import React, { createContext, useContext, useMemo, useRef } from 'react';

import { DEFAULT_LOCALE, getMessages } from '../i18n';
import type { I18nParams, Locale, Messages } from '../i18n/types';

export type I18n = {
  locale: Locale;
  t: (key: string, params?: I18nParams) => string;
};

const I18nContext = createContext<I18n | null>(null);

function interpolate(template: string, params?: I18nParams): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_m, k: string) => {
    const v = params[k];
    return v == null ? `{${k}}` : String(v);
  });
}

export function I18nProvider({
  locale,
  extraMessages,
  children,
}: {
  locale: Locale;
  extraMessages?: Partial<Record<Locale, Messages>>;
  children: React.ReactNode;
}) {
  const missingKeysRef = useRef<Set<string> | null>(null);
  if (missingKeysRef.current == null) missingKeysRef.current = new Set<string>();

  const value = useMemo<I18n>(() => {
    const activeLocale = locale || DEFAULT_LOCALE;
    const baseActive = getMessages(activeLocale);
    const baseFallback = getMessages(DEFAULT_LOCALE);
    const pluginActive = (extraMessages && extraMessages[activeLocale]) || {};
    const pluginFallback = (extraMessages && extraMessages[DEFAULT_LOCALE]) || {};
    const active = { ...baseActive, ...pluginActive };
    const fallback = { ...baseFallback, ...pluginFallback };

    const t = (key: string, params?: I18nParams): string => {
      const msg = (active as Messages)[key] ?? (fallback as Messages)[key];
      if (msg == null) {
        // Dev-only warning, once per key.
        if (process.env.NODE_ENV !== 'production') {
          const s = missingKeysRef.current!;
          if (!s.has(key)) {
            s.add(key);
            // eslint-disable-next-line no-console
            console.warn(`[i18n] missing key: ${key} (locale=${activeLocale})`);
          }
        }
        return key;
      }
      return interpolate(String(msg), params);
    };

    return { locale: activeLocale, t };
  }, [extraMessages, locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}


