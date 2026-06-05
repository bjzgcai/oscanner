'use client';

import dynamic from 'next/dynamic';
import React from 'react';

import { TRAJECTORY_CHECKPOINT_VIEW_IMPORTERS } from './generated/pluginViewMap';
import { useI18n } from './I18nContext';
import type { EvidenceLink, TrajectoryCheckpoint } from '@/types/trajectory';
import type { I18nParams } from '../i18n/types';

export type PluginCheckpointViewProps = {
  checkpoint: TrajectoryCheckpointData;
  previousCheckpoint?: TrajectoryCheckpointData | null;
  locale?: string;
  t?: (key: string, params?: I18nParams) => string;
};

type TrajectoryCheckpointData = {
  checkpoint_id: number;
  created_at: string;
  commits_range: {
    start_sha: string;
    end_sha: string;
    commit_count: number;
    period_start?: string | null;
    period_end?: string | null;
    accumulated_from_periods?: number;
  };
  evaluation: {
    scores: Record<string, number | string>;
    commits_summary: {
      total_additions: number;
      total_deletions: number;
      files_changed: number;
      languages: string[];
    };
    plugin: string;
    plugin_version: string;
    total_commits_analyzed: number;
    evidence_links?: EvidenceLink[] | null;
  };
  repos_analyzed?: string[] | null;
  aliases_used?: string[] | null;
  previous_checkpoint_id?: number | null;
  growth_comparison?: {
    dimension_changes: Record<string, number>;
    overall_trend: 'increasing' | 'stable' | 'decreasing';
    improved_dimensions: string[];
    regressed_dimensions: string[];
  } | null;
};

type Props = {
  pluginId: string;
  checkpoint: TrajectoryCheckpoint;
  previousCheckpoint?: TrajectoryCheckpoint | null;
};

type Importer = () => Promise<{ default: React.ComponentType<PluginCheckpointViewProps> }>;
const VIEW_MAP: Record<string, React.ComponentType<PluginCheckpointViewProps>> = Object.fromEntries(
  Object.entries(TRAJECTORY_CHECKPOINT_VIEW_IMPORTERS).map(([pluginId, importer]) => [
    pluginId,
    dynamic<PluginCheckpointViewProps>(importer as Importer, { ssr: false }),
  ])
) as Record<string, React.ComponentType<PluginCheckpointViewProps>>;

export default function PluginCheckpointRenderer(props: Props) {
  const { pluginId, checkpoint, previousCheckpoint } = props;
  const i18n = useI18n();

  const View = VIEW_MAP[pluginId];
  if (!View) {
    return (
      <div style={{ padding: 12, border: '1px solid #EF4444', borderRadius: 12, color: '#991B1B', background: '#FEF2F2' }}>
        Plugin checkpoint view not found for pluginId=<b>{pluginId}</b>. Please ensure this plugin provides `view/trajectory_checkpoint.tsx`.
      </div>
    );
  }

  // Convert TrajectoryCheckpoint to TrajectoryCheckpointData format
  const checkpointData: TrajectoryCheckpointData = {
    checkpoint_id: checkpoint.checkpoint_id,
    created_at: checkpoint.created_at,
    commits_range: {
      start_sha: checkpoint.commits_range.start_sha,
      end_sha: checkpoint.commits_range.end_sha,
      commit_count: checkpoint.commits_range.commit_count,
      period_start: checkpoint.commits_range.period_start,
      period_end: checkpoint.commits_range.period_end,
      accumulated_from_periods: checkpoint.commits_range.accumulated_from_periods,
    },
    evaluation: {
      scores: checkpoint.evaluation.scores as unknown as Record<string, number | string>,
      commits_summary: checkpoint.evaluation.commits_summary,
      plugin: checkpoint.evaluation.plugin,
      plugin_version: checkpoint.evaluation.plugin_version,
      total_commits_analyzed: checkpoint.evaluation.total_commits_analyzed,
      evidence_links: checkpoint.evaluation.evidence_links,
    },
    repos_analyzed: checkpoint.repos_analyzed,
    aliases_used: checkpoint.aliases_used,
    previous_checkpoint_id: checkpoint.previous_checkpoint_id,
    growth_comparison: checkpoint.growth_comparison,
  };

  const previousCheckpointData: TrajectoryCheckpointData | null = previousCheckpoint ? {
    checkpoint_id: previousCheckpoint.checkpoint_id,
    created_at: previousCheckpoint.created_at,
    commits_range: {
      start_sha: previousCheckpoint.commits_range.start_sha,
      end_sha: previousCheckpoint.commits_range.end_sha,
      commit_count: previousCheckpoint.commits_range.commit_count,
      period_start: previousCheckpoint.commits_range.period_start,
      period_end: previousCheckpoint.commits_range.period_end,
      accumulated_from_periods: previousCheckpoint.commits_range.accumulated_from_periods,
    },
    evaluation: {
      scores: previousCheckpoint.evaluation.scores as unknown as Record<string, number | string>,
      commits_summary: previousCheckpoint.evaluation.commits_summary,
      plugin: previousCheckpoint.evaluation.plugin,
      plugin_version: previousCheckpoint.evaluation.plugin_version,
      total_commits_analyzed: previousCheckpoint.evaluation.total_commits_analyzed,
      evidence_links: previousCheckpoint.evaluation.evidence_links,
    },
    repos_analyzed: previousCheckpoint.repos_analyzed,
    aliases_used: previousCheckpoint.aliases_used,
    previous_checkpoint_id: previousCheckpoint.previous_checkpoint_id,
    growth_comparison: previousCheckpoint.growth_comparison,
  } : null;

  return (
    <View
      checkpoint={checkpointData}
      previousCheckpoint={previousCheckpointData}
      locale={i18n.locale}
      t={i18n.t}
    />
  );
}
