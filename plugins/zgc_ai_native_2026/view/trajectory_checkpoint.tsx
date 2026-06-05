import React from 'react';
import { Card, Descriptions, Space, Tag } from 'antd';
import type { PluginTrajectoryCheckpointViewProps } from '../../_shared/view/types';
import ReasoningMarkdown from './ReasoningMarkdown';

export default function PluginTrajectoryCheckpointView(props: PluginTrajectoryCheckpointViewProps) {
  const { checkpoint, previousCheckpoint, t: tFromProps } = props;
  
  if (typeof tFromProps !== 'function') {
    throw new Error('zgc_ai_native_2026 plugin trajectory checkpoint view requires `t(key, params?)` prop from host app.');
  }
  const t = tFromProps;
  
  const { evaluation } = checkpoint;
  const scores = evaluation.scores;
  const repoUrl = Array.isArray(checkpoint.repos_analyzed) ? checkpoint.repos_analyzed[0] : undefined;

  // Get all dimension keys (excluding reasoning)
  const dimensionKeys = Object.keys(scores).filter(
    (key) => key !== 'reasoning' && scores[key] !== null && scores[key] !== undefined
  );

  // Get score color based on value
  const getScoreColor = (score: number) => {
    if (score >= 80) return 'green';
    if (score >= 60) return 'blue';
    if (score >= 40) return 'orange';
    return 'red';
  };

  // Get dimension label - try plugin-specific first, then fallback to generic
  const getDimensionLabel = (dimensionKey: string) => {
    const pluginSpecificKey = `plugin.${evaluation.plugin}.dim.${dimensionKey}`;
    const translated = t(pluginSpecificKey);
    if (translated === pluginSpecificKey) {
      return t(`dimensions.${dimensionKey}`) || dimensionKey;
    }
    return translated;
  };

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      {/* Evaluation Scores */}
      <div>
        <h4 style={{ marginBottom: '12px' }}>{t('checkpoint.evaluation_scores')}</h4>
        <Descriptions bordered column={2} size="small">
          {dimensionKeys.map((key) => {
            const score = scores[key] as number;
            return (
              <Descriptions.Item
                key={key}
                label={getDimensionLabel(key)}
              >
                <Tag color={getScoreColor(score)} style={{ fontSize: '14px', padding: '4px 12px' }}>
                  {score}/100
                </Tag>
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      </div>

      {/* Reasoning */}
      {scores.reasoning && (
        <div>
          <h4 style={{ marginBottom: '12px' }}>{t('checkpoint.evaluation_reasoning')}</h4>
          <Card size="small" style={{ background: '#f5f5f5' }}>
            <div style={{ lineHeight: '1.6' }}>
              <ReasoningMarkdown
                reasoning={scores.reasoning as string}
                repoUrl={repoUrl}
                evidenceLinks={evaluation.evidence_links}
              />
            </div>
          </Card>
        </div>
      )}

      {/* Additional Metadata */}
      <div>
        <h4 style={{ marginBottom: '12px' }}>{t('checkpoint.metadata')}</h4>
        <Descriptions bordered column={1} size="small">
          <Descriptions.Item label={t('checkpoint.id')}>
            #{checkpoint.checkpoint_id}
          </Descriptions.Item>
          <Descriptions.Item label={t('checkpoint.created_at')}>
            {new Date(checkpoint.created_at).toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label={t('checkpoint.commits_analyzed')}>
            {checkpoint.commits_range.commit_count} {t('checkpoint.commits')}
          </Descriptions.Item>
          <Descriptions.Item label={t('checkpoint.total_additions')}>
            +{evaluation.commits_summary.total_additions} {t('checkpoint.lines')}
          </Descriptions.Item>
          <Descriptions.Item label={t('checkpoint.total_deletions')}>
            -{evaluation.commits_summary.total_deletions} {t('checkpoint.lines')}
          </Descriptions.Item>
          <Descriptions.Item label={t('checkpoint.files_changed')}>
            {evaluation.commits_summary.files_changed} {t('checkpoint.files')}
          </Descriptions.Item>
          {evaluation.commits_summary.languages.length > 0 && (
            <Descriptions.Item label={t('checkpoint.languages')}>
              {evaluation.commits_summary.languages.join(', ')}
            </Descriptions.Item>
          )}
        </Descriptions>
      </div>
    </Space>
  );
}
