'use client';

import React, { createContext, useContext, useMemo, useState } from 'react';

type AppSettings = {
  useCache: boolean;
  setUseCache: (v: boolean) => void;
  model: string;
  setModel: (v: string) => void;
};

const STORAGE_KEY_USE_CACHE = 'oscanner_use_cache';
const STORAGE_KEY_MODEL = 'oscanner_llm_model';
const DEFAULT_MODEL = 'anthropic/claude-sonnet-4.5';

const AppSettingsContext = createContext<AppSettings | null>(null);

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  const [useCache, setUseCacheState] = useState(() => {
    try {
      if (typeof window === 'undefined') return false;
      const raw = window.localStorage.getItem(STORAGE_KEY_USE_CACHE);
      if (raw === 'true') return true;
      if (raw === 'false') return false;
      return false;
    } catch {
      return false;
    }
  });

  const [model, setModelState] = useState(() => {
    try {
      if (typeof window === 'undefined') return DEFAULT_MODEL;
      const raw = window.localStorage.getItem(STORAGE_KEY_MODEL);
      return (raw || DEFAULT_MODEL).trim() || DEFAULT_MODEL;
    } catch {
      return DEFAULT_MODEL;
    }
  });

  const setUseCache = (v: boolean) => {
    setUseCacheState(v);
    try {
      localStorage.setItem(STORAGE_KEY_USE_CACHE, String(v));
    } catch {
      // ignore
    }
  };

  const setModel = (v: string) => {
    const next = (v || '').trim() || DEFAULT_MODEL;
    setModelState(next);
    try {
      localStorage.setItem(STORAGE_KEY_MODEL, next);
    } catch {
      // ignore
    }
  };

  const value = useMemo(() => ({ useCache, setUseCache, model, setModel }), [useCache, model]);

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings(): AppSettings {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}


