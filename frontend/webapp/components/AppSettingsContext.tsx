'use client';
import { getApiBaseUrl } from '../utils/apiBase';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { DEFAULT_LOCALE, isLocale } from '../i18n';
import type { Locale } from '../i18n/types';

const API_SERVER_URL = getApiBaseUrl();
type AppSettings = {
  useCache: boolean;
  setUseCache: (v: boolean) => void;
  model: string;
  setModel: (v: string) => void;
  pluginId: string;
  setPluginId: (v: string) => void;
  locale: Locale;
  setLocale: (v: Locale) => void;
  plugins: Array<{ id: string; name: string; version: string; description?: string; default?: boolean; has_view?: boolean }>;
  refreshPlugins: () => Promise<void>;
  llmModalOpen: boolean;
  setLlmModalOpen: (v: boolean) => void;
};

const STORAGE_KEY_USE_CACHE = 'oscanner_use_cache';
const STORAGE_KEY_MODEL = 'oscanner_llm_model';
const STORAGE_KEY_PLUGIN = 'oscanner_plugin_id';
const STORAGE_KEY_LOCALE = 'oscanner_locale';
const DEFAULT_MODEL = 'qwen/qwen3-coder-flash';
const DEFAULT_PLUGIN = 'zgc_simple';

const AppSettingsContext = createContext<AppSettings | null>(null);

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  // Always start with default values to prevent hydration mismatch
  const [model, setModelState] = useState(DEFAULT_MODEL);
  const [pluginId, setPluginIdState] = useState(DEFAULT_PLUGIN);
  const [plugins, setPlugins] = useState<AppSettings['plugins']>([]);
  const [useCache, setUseCacheState] = useState(true);
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);
  const [llmModalOpen, setLlmModalOpen] = useState(false);

  // Load from localStorage after hydration is complete
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_USE_CACHE);
      if (raw === 'true') {
        setUseCacheState(true);
      } else if (raw === 'false') {
        setUseCacheState(false);
      }
    } catch {
      // ignore
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_MODEL);
      if (raw) {
        const trimmed = raw.trim();
        if (trimmed) {
          setModelState(trimmed);
        }
      }
    } catch {
      // ignore
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_PLUGIN);
      if (raw) {
        const trimmed = raw.trim();
        if (trimmed) {
          setPluginIdState(trimmed);
        }
      }
    } catch {
      // ignore
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_LOCALE);
      const trimmed = (raw || '').trim();
      if (trimmed && isLocale(trimmed)) {
        setLocaleState(trimmed);
      } else if (!trimmed) {
        // Prefer browser language when user hasn't chosen yet.
        const navLang = (navigator.language || '').trim();
        if (isLocale(navLang)) {
          setLocaleState(navLang);
        } else if (navLang.toLowerCase().startsWith('zh')) {
          setLocaleState('zh-CN');
        } else if (navLang) {
          setLocaleState('en-US');
        }
      }
    } catch {
      // ignore
    }
  }, []);

  const setModel = (v: string) => {
    const next = (v || '').trim() || DEFAULT_MODEL;
    setModelState(next);
    try {
      localStorage.setItem(STORAGE_KEY_MODEL, next);
    } catch {
      // ignore
    }
  };

  const setUseCache = (v: boolean) => {
    const next = Boolean(v);
    setUseCacheState(next);
    try {
      localStorage.setItem(STORAGE_KEY_USE_CACHE, String(next));
    } catch {
      // ignore
    }
  };

  const setPluginId = (v: string) => {
    const next = (v || '').trim() || DEFAULT_PLUGIN;
    setPluginIdState(next);
    try {
      localStorage.setItem(STORAGE_KEY_PLUGIN, next);
    } catch {
      // ignore
    }
  };

  const setLocale = (v: Locale) => {
    const next = isLocale(String(v)) ? (v as Locale) : DEFAULT_LOCALE;
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY_LOCALE, next);
    } catch {
      // ignore
    }
  };

  const refreshPlugins = useCallback(async () => {
    try {
      console.log('[Info] Refreshing plugin list from backend');
      const resp = await fetch(`${API_SERVER_URL}/api/plugins`);
      console.log(`[Info] /api/plugins response: ${resp.status} ${resp.statusText}`);
      if (!resp.ok) return;
      const data = await resp.json();
      const list = Array.isArray(data.plugins) ? data.plugins : [];
      setPlugins(list);
      // If user has no selection yet, snap to backend default.
      if (typeof data.default === 'string' && data.default) {
        setPluginIdState((cur) => cur || data.default);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshPlugins();
  }, [refreshPlugins]);

  const value = useMemo(
    () => ({ useCache, setUseCache, model, setModel, pluginId, setPluginId, locale, setLocale, plugins, refreshPlugins, llmModalOpen, setLlmModalOpen }),
    [useCache, model, pluginId, locale, plugins, refreshPlugins, llmModalOpen]
  );

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings(): AppSettings {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}


