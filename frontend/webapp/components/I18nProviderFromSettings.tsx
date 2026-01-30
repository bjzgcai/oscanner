'use client';

import React, { useEffect, useState } from 'react';

import { useAppSettings } from './AppSettingsContext';
import { I18nProvider } from './I18nContext';
import { PLUGIN_I18N_IMPORTERS } from './generated/pluginViewMap';
import type { Locale, Messages } from '../i18n/types';

export default function I18nProviderFromSettings({ children }: { children: React.ReactNode }) {
  const { locale, pluginId } = useAppSettings();
  const [extraMessages, setExtraMessages] = useState<Partial<Record<Locale, Messages>> | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const pid = (pluginId || '').trim();
    const importer = pid ? PLUGIN_I18N_IMPORTERS[pid] : undefined;
    if (!importer) {
      setExtraMessages(undefined);
      return;
    }
    (async () => {
      try {
        const mod = await importer();
        const pack = mod && (mod as any).default;
        const messages = pack && pack.messages ? (pack.messages as Partial<Record<Locale, Messages>>) : undefined;
        if (!cancelled) setExtraMessages(messages || undefined);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn(`[i18n] failed to load plugin i18n for pluginId=${pid}`, e);
        if (!cancelled) setExtraMessages(undefined);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pluginId]);

  return (
    <I18nProvider locale={locale} extraMessages={extraMessages}>
      {children}
    </I18nProvider>
  );
}


