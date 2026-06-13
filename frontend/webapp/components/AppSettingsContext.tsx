'use client';
import { getApiBaseUrl } from '../utils/apiBase';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { DEFAULT_LOCALE, isLocale } from '../i18n';
import type { Locale } from '../i18n/types';

const API_SERVER_URL = getApiBaseUrl();
type AppSettings = {
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
  forcedCheckerId: string | null;
  setForcedCheckerId: (v: string | null) => void;
  checkers: Array<{ id: string; name: string; keyword: string; description?: string; enabled?: boolean }>;
  refreshCheckers: () => Promise<void>;
  worktreeBase: 'build' | 'temp';
  setWorktreeBase: (v: 'build' | 'temp') => void;
};

const STORAGE_KEY_MODEL = 'oscanner_llm_model';
const STORAGE_KEY_PLUGIN = 'oscanner_plugin_id';
const STORAGE_KEY_PLUGIN_USER_SELECTED = 'oscanner_plugin_user_selected';
const STORAGE_KEY_LOCALE = 'oscanner_locale';
const STORAGE_KEY_FORCED_CHECKER = 'oscanner_forced_checker_id';
const STORAGE_KEY_WORKTREE_BASE = 'oscanner_worktree_base';
const DEFAULT_MODEL = 'deepseek/deepseek-v4-pro';
const LEGACY_MODEL_ALIASES = new Set([
  'qwen/qwen3-coder-flash',
]);
const DEFAULT_PLUGIN = 'zgc_ai_native_2026';
const DEFAULT_WORKTREE_BASE: 'build' | 'temp' = 'build';

const AppSettingsContext = createContext<AppSettings | null>(null);

function normalizeModel(value: string | null | undefined): string {
  const trimmed = (value || '').trim();
  if (!trimmed || LEGACY_MODEL_ALIASES.has(trimmed)) {
    return DEFAULT_MODEL;
  }
  return trimmed;
}

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  // Always start with default values to prevent hydration mismatch
  const [model, setModelState] = useState(DEFAULT_MODEL);
  const [pluginId, setPluginIdState] = useState(DEFAULT_PLUGIN);
  const [plugins, setPlugins] = useState<AppSettings['plugins']>([]);
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);
  const [llmModalOpen, setLlmModalOpen] = useState(false);
  const [forcedCheckerId, setForcedCheckerIdState] = useState<string | null>(null);
  const [checkers, setCheckers] = useState<AppSettings['checkers']>([]);
  const [worktreeBase, setWorktreeBaseState] = useState<'build' | 'temp'>(DEFAULT_WORKTREE_BASE);

  // Load from localStorage after hydration is complete
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_MODEL);
      const trimmed = (raw || '').trim();
      if (trimmed) {
        const next = normalizeModel(trimmed);
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setModelState(next);
        if (next !== trimmed) {
          localStorage.setItem(STORAGE_KEY_MODEL, next);
        }
      }
    } catch {
      // ignore
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_PLUGIN);
      const userSelected = window.localStorage.getItem(STORAGE_KEY_PLUGIN_USER_SELECTED) === '1';
      if (raw && userSelected) {
        const trimmed = raw.trim();
        if (trimmed) {
          setPluginIdState(trimmed);
        }
      } else if (raw && raw.trim() && raw.trim() !== DEFAULT_PLUGIN) {
        window.localStorage.setItem(STORAGE_KEY_PLUGIN, DEFAULT_PLUGIN);
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
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_FORCED_CHECKER);
      if (raw) {
        const trimmed = raw.trim();
        if (trimmed) {
          setForcedCheckerIdState(trimmed);
        }
      }
    } catch {
      // ignore
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_WORKTREE_BASE);
      if (raw === 'build' || raw === 'temp') {
        setWorktreeBaseState(raw);
      }
    } catch {
      // ignore
    }
  }, []);

  const setForcedCheckerId = (v: string | null) => {
    const next = v ? v.trim() || null : null;
    setForcedCheckerIdState(next);
    try {
      if (next) {
        localStorage.setItem(STORAGE_KEY_FORCED_CHECKER, next);
      } else {
        localStorage.removeItem(STORAGE_KEY_FORCED_CHECKER);
      }
    } catch {
      // ignore
    }
  };

  const setWorktreeBase = (v: 'build' | 'temp') => {
    const next = v === 'build' || v === 'temp' ? v : DEFAULT_WORKTREE_BASE;
    setWorktreeBaseState(next);
    try {
      localStorage.setItem(STORAGE_KEY_WORKTREE_BASE, next);
    } catch {
      // ignore
    }
  };

  const setModel = (v: string) => {
    const next = normalizeModel(v);
    setModelState(next);
    try {
      localStorage.setItem(STORAGE_KEY_MODEL, next);
    } catch {
      // ignore
    }
  };

  const setPluginId = (v: string) => {
    const next = (v || '').trim() || DEFAULT_PLUGIN;
    setPluginIdState(next);
    try {
      localStorage.setItem(STORAGE_KEY_PLUGIN, next);
      localStorage.setItem(STORAGE_KEY_PLUGIN_USER_SELECTED, '1');
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

  const refreshCheckers = useCallback(async () => {
    try {
      console.log('[Info] Refreshing checker list from backend');
      const resp = await fetch(`${API_SERVER_URL}/api/checkers/list`);
      console.log(`[Info] /api/checkers/list response: ${resp.status} ${resp.statusText}`);
      if (!resp.ok) return;
      const data = await resp.json();
      const list = Array.isArray(data.checkers) ? data.checkers : [];
      setCheckers(list);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshPlugins();
    refreshCheckers();
  }, [refreshPlugins, refreshCheckers]);

  const value = useMemo(
    () => ({ model, setModel, pluginId, setPluginId, locale, setLocale, plugins, refreshPlugins, llmModalOpen, setLlmModalOpen, forcedCheckerId, setForcedCheckerId, checkers, refreshCheckers, worktreeBase, setWorktreeBase }),
    [model, pluginId, locale, plugins, refreshPlugins, llmModalOpen, forcedCheckerId, checkers, refreshCheckers, worktreeBase]
  );

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings(): AppSettings {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}
