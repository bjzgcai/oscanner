'use client';
import { getApiBaseUrl } from '../utils/apiBase';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
const API_SERVER_URL = getApiBaseUrl();
type AppSettings = {
  useCache: boolean;
  setUseCache: (v: boolean) => void;
  model: string;
  setModel: (v: string) => void;
  pluginId: string;
  setPluginId: (v: string) => void;
  plugins: Array<{ id: string; name: string; version: string; description?: string; default?: boolean; has_view?: boolean }>;
  refreshPlugins: () => Promise<void>;
};

const STORAGE_KEY_USE_CACHE = 'oscanner_use_cache';
const STORAGE_KEY_MODEL = 'oscanner_llm_model';
const STORAGE_KEY_PLUGIN = 'oscanner_plugin_id';
const DEFAULT_MODEL = 'Pro/zai-org/GLM-4.7';
const DEFAULT_PLUGIN = 'zgc_simple';

const AppSettingsContext = createContext<AppSettings | null>(null);

export function AppSettingsProvider({ children }: { children: React.ReactNode }) {
  // Always start with default values to prevent hydration mismatch
  const [model, setModelState] = useState(DEFAULT_MODEL);
  const [pluginId, setPluginIdState] = useState(DEFAULT_PLUGIN);
  const [plugins, setPlugins] = useState<AppSettings['plugins']>([]);
  const [useCache, setUseCacheState] = useState(true);

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
    () => ({ useCache, setUseCache, model, setModel, pluginId, setPluginId, plugins, refreshPlugins }),
    [useCache, model, pluginId, plugins, refreshPlugins]
  );

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings(): AppSettings {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}


