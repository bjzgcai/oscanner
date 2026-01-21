'use client';

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

type AppSettings = {
  model: string;
  setModel: (v: string) => void;
};

const STORAGE_KEY_MODEL = 'oscanner_llm_model';
const DEFAULT_MODEL = 'Pro/zai-org/GLM-4.7';

const AppSettingsContext = createContext<AppSettings | null>(null);

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  // Always start with default values to prevent hydration mismatch
  const [model, setModelState] = useState(DEFAULT_MODEL);

  // Load from localStorage after hydration is complete
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_MODEL);
      if (raw) {
        const trimmed = raw.trim();
        if (trimmed) setModelState(trimmed);
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

  const value = useMemo(() => ({ model, setModel }), [model]);

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings(): AppSettings {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}


