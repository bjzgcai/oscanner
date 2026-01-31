'use client';

import dynamic from 'next/dynamic';
import React from 'react';

import type { ContributorComparisonData } from '../types';
import { MULTI_REPO_COMPARE_VIEW_IMPORTERS } from './generated/pluginViewMap';
import { useI18n } from './I18nContext';
import type { I18nParams } from '../i18n/types';

export type PluginCompareViewProps = {
  data: ContributorComparisonData | null;
  loading?: boolean;
  error?: string;
  locale?: string;
  t?: (key: string, params?: I18nParams) => string;
};

type Props = {
  pluginId: string;
  data: ContributorComparisonData | null;
  loading?: boolean;
  error?: string;
};

type Importer = () => Promise<{ default: React.ComponentType<PluginCompareViewProps> }>;
const VIEW_MAP: Record<string, React.ComponentType<PluginCompareViewProps>> = Object.fromEntries(
  Object.entries(MULTI_REPO_COMPARE_VIEW_IMPORTERS).map(([pluginId, importer]) => [
    pluginId,
    dynamic<PluginCompareViewProps>(importer as Importer, { ssr: false }),
  ])
) as Record<string, React.ComponentType<PluginCompareViewProps>>;

export default function PluginComparisonRenderer(props: Props) {
  const { pluginId, data, loading, error } = props;
  const i18n = useI18n();
  const View = VIEW_MAP[pluginId];
  if (!View) {
    return (
      <div style={{ padding: 12, border: '1px solid #EF4444', borderRadius: 12, color: '#991B1B', background: '#FEF2F2' }}>
        Plugin compare view not found for pluginId=<b>{pluginId}</b>. Please ensure this plugin provides `view/multi_repo_compare.tsx`.
      </div>
    );
  }
  return <View data={data} loading={loading} error={error} locale={i18n.locale} t={i18n.t} />;
}


