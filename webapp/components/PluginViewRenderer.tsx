'use client';

import dynamic from 'next/dynamic';
import React from 'react';

import { SINGLE_REPO_VIEW_IMPORTERS } from './generated/pluginViewMap';
import { useI18n } from './I18nContext';
import type { I18nParams } from '../i18n/types';

export type PluginEvaluation = {
  scores: Record<string, number | string>;
  total_commits_analyzed?: number;
  commits_summary?: { total_additions: number; total_deletions: number; files_changed: number; languages: string[] };
  plugin?: string;
  plugin_version?: string;
};

type PluginViewProps = {
  evaluation: PluginEvaluation | null;
  title?: string;
  loading?: boolean;
  error?: string;
  locale?: string;
  t?: (key: string, params?: I18nParams) => string;
};

type Props = {
  pluginId: string;
  evaluation: PluginEvaluation | null;
  title?: string;
  loading?: boolean;
  error?: string;
};

type Importer = () => Promise<{ default: React.ComponentType<PluginViewProps> }>;
const VIEW_MAP: Record<string, React.ComponentType<PluginViewProps>> = Object.fromEntries(
  Object.entries(SINGLE_REPO_VIEW_IMPORTERS).map(([pluginId, importer]) => [
    pluginId,
    dynamic<PluginViewProps>(importer as Importer, { ssr: false }),
  ])
) as Record<string, React.ComponentType<PluginViewProps>>;

export default function PluginViewRenderer(props: Props) {
  const { pluginId, evaluation, title, loading, error } = props;
  const i18n = useI18n();

  const View = VIEW_MAP[pluginId];
  if (!View) {
    return (
      <div style={{ padding: 12, border: '1px solid #EF4444', borderRadius: 12, color: '#991B1B', background: '#FEF2F2' }}>
        Plugin view not found for pluginId=<b>{pluginId}</b>. Please ensure this plugin provides `view/single_repo.tsx`.
      </div>
    );
  }
  return <View evaluation={evaluation} title={title} loading={loading} error={error} locale={i18n.locale} t={i18n.t} />;
}


