'use client';

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

type UserSettings = {
  defaultUsername: string;
  setDefaultUsername: (v: string) => void;
  repoUrls: string[];
  setRepoUrls: (v: string[]) => void;
  usernameGroups: string;
  setUsernameGroups: (v: string) => void;
};

const STORAGE_KEY_DEFAULT_USERNAME = 'oscanner_default_username';
const STORAGE_KEY_REPO_URLS = 'oscanner_repo_urls';
const STORAGE_KEY_USERNAME_GROUPS = 'oscanner_username_groups';

const DEFAULT_USERNAME = 'CarterWu';
const DEFAULT_REPO_URLS = ['https://gitee.com/zgcai/oscanner'];
const DEFAULT_USERNAME_GROUPS = '';

const UserSettingsContext = createContext<UserSettings | null>(null);

export function UserSettingsProvider({ children }: { children: React.ReactNode }) {
  // Always start with default values to prevent hydration mismatch
  const [defaultUsername, setDefaultUsernameState] = useState(DEFAULT_USERNAME);
  const [repoUrls, setRepoUrlsState] = useState<string[]>(DEFAULT_REPO_URLS);
  const [usernameGroups, setUsernameGroupsState] = useState(DEFAULT_USERNAME_GROUPS);

  // Load from localStorage after hydration is complete
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_DEFAULT_USERNAME);
      if (raw) {
        const trimmed = raw.trim();
        if (trimmed) {
          setDefaultUsernameState(trimmed);
        }
      }
    } catch {
      // ignore
    }

    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_REPO_URLS);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setRepoUrlsState(parsed);
        }
      }
    } catch {
      // ignore
    }

    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_USERNAME_GROUPS);
      if (raw !== null) {
        setUsernameGroupsState(raw);
      }
    } catch {
      // ignore
    }
  }, []);

  const setDefaultUsername = (v: string) => {
    const next = (v || '').trim() || DEFAULT_USERNAME;
    setDefaultUsernameState(next);
    try {
      localStorage.setItem(STORAGE_KEY_DEFAULT_USERNAME, next);
    } catch {
      // ignore
    }
  };

  const setRepoUrls = (v: string[]) => {
    const next = Array.isArray(v) && v.length > 0 ? v : DEFAULT_REPO_URLS;
    setRepoUrlsState(next);
    try {
      localStorage.setItem(STORAGE_KEY_REPO_URLS, JSON.stringify(next));
    } catch {
      // ignore
    }
  };

  const setUsernameGroups = (v: string) => {
    const next = v || '';
    setUsernameGroupsState(next);
    try {
      localStorage.setItem(STORAGE_KEY_USERNAME_GROUPS, next);
    } catch {
      // ignore
    }
  };

  const value = useMemo(
    () => ({
      defaultUsername,
      setDefaultUsername,
      repoUrls,
      setRepoUrls,
      usernameGroups,
      setUsernameGroups,
    }),
    [defaultUsername, repoUrls, usernameGroups]
  );

  return <UserSettingsContext.Provider value={value}>{children}</UserSettingsContext.Provider>;
}

export function useUserSettings(): UserSettings {
  const ctx = useContext(UserSettingsContext);
  if (!ctx) throw new Error('useUserSettings must be used within UserSettingsProvider');
  return ctx;
}
