import React from 'react';
import { Alert, Card, Descriptions, Empty, Progress, Space, Spin, Tag } from 'antd';
import ContributorComparisonBase from './ContributorComparisonBase';
import type {
  PluginMultiRepoCompareViewProps,
  PluginSingleRepoViewProps,
  PluginTrajectoryCheckpointViewProps,
} from './types';

type StandardViewConfig = {
  pluginId: string;
  title: string;
  subtitle: string;
  accent: string;
};

function numericDimensionKeys(scores: Record<string, number | string> | undefined): string[] {
  return Object.keys(scores || {}).filter((key) => {
    if (key === 'reasoning' || key.endsWith('_collaboration')) return false;
    return typeof scores?.[key] === 'number';
  });
}

function scoreColor(score: number): string {
  if (score >= 85) return 'purple';
  if (score >= 70) return 'geekblue';
  if (score >= 50) return 'green';
  if (score >= 30) return 'gold';
  return 'red';
}

function scoreLevel(score: number): string {
  if (score >= 85) return 'Advanced';
  if (score >= 70) return 'Strong';
  if (score >= 50) return 'Developing';
  if (score >= 30) return 'Basic';
  return 'Insufficient';
}

function translateDimension(
  t: ((key: string, params?: Record<string, string | number>) => string) | undefined,
  pluginId: string,
  key: string,
): string {
  if (typeof t !== 'function') return key.replace(/_/g, ' ');
  const pluginKey = `plugin.${pluginId}.dim.${key}`;
  const translated = t(pluginKey);
  if (translated && translated !== pluginKey) return translated;
  const generic = t(`dimensions.${key}`);
  return generic && generic !== `dimensions.${key}` ? generic : key.replace(/_/g, ' ');
}

function averageScore(scores: Record<string, number | string> | undefined, keys: string[]): number {
  if (!keys.length) return 0;
  return keys.reduce((sum, key) => sum + Number(scores?.[key] || 0), 0) / keys.length;
}

export function StandardSingleRepoView(props: PluginSingleRepoViewProps & { config: StandardViewConfig }) {
  const { evaluation, title, loading, error, config, t } = props;
  if (error) return <Alert type="error" showIcon title="Evaluation failed" description={error} />;
  if (loading) {
    return (
      <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>Evaluating with {config.title}...</div>
      </Card>
    );
  }
  if (!evaluation) {
    return (
      <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Empty description="No evaluation data available" />
      </Card>
    );
  }

  const scores = evaluation.scores || {};
  const keys = numericDimensionKeys(scores);
  const avg = averageScore(scores, keys);

  return (
    <Card style={{ border: `2px solid ${config.accent}` }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0 }}>{title || config.title}</h3>
          <div style={{ color: 'rgba(0,0,0,0.55)', marginTop: 4 }}>{config.subtitle}</div>
        </div>
        <Space wrap>
          <Tag color={scoreColor(avg)}>{scoreLevel(avg)} avg {avg.toFixed(1)}</Tag>
          <Tag color="blue">plugin={evaluation.plugin || config.pluginId}</Tag>
        </Space>
      </div>

      <Descriptions
        bordered
        size="small"
        column={{ xs: 1, sm: 1, md: 2, lg: 3, xl: 3, xxl: 3 }}
        style={{ marginTop: 16 }}
      >
        {keys.map((key) => {
          const value = Number(scores[key] || 0);
          return (
            <Descriptions.Item key={key} label={translateDimension(t, config.pluginId, key)}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Tag color={scoreColor(value)}>{value}/100</Tag>
                <Progress percent={Math.max(0, Math.min(100, value))} size="small" showInfo={false} />
              </Space>
            </Descriptions.Item>
          );
        })}
      </Descriptions>

      {typeof scores.reasoning === 'string' && scores.reasoning.trim() ? (
        <Card size="small" style={{ marginTop: 16, background: '#fafafa' }}>
          <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'inherit', lineHeight: 1.6 }}>{scores.reasoning}</pre>
        </Card>
      ) : null}
    </Card>
  );
}

export function StandardCompareView(props: PluginMultiRepoCompareViewProps & { config: StandardViewConfig }) {
  const { config } = props;
  return (
    <Card style={{ border: `2px solid ${config.accent}` }}>
      <div style={{ fontWeight: 900, fontSize: 18 }}>{config.title} Compare</div>
      <div style={{ color: 'rgba(0,0,0,0.55)', marginBottom: 12 }}>{config.subtitle}</div>
      <ContributorComparisonBase {...props} theme="rubric" />
    </Card>
  );
}

export function StandardTrajectoryCheckpointView(
  props: PluginTrajectoryCheckpointViewProps & { config: StandardViewConfig },
) {
  const { checkpoint, config, t } = props;
  const scores = checkpoint.evaluation.scores || {};
  const keys = numericDimensionKeys(scores);

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <Card title={config.title} style={{ border: `2px solid ${config.accent}` }}>
        <Descriptions bordered size="small" column={{ xs: 1, sm: 1, md: 2 }}>
          {keys.map((key) => {
            const value = Number(scores[key] || 0);
            return (
              <Descriptions.Item key={key} label={translateDimension(t, config.pluginId, key)}>
                <Tag color={scoreColor(value)}>{value}/100</Tag>
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      </Card>

      {typeof scores.reasoning === 'string' && scores.reasoning.trim() ? (
        <Card size="small" title="Evaluation reasoning" style={{ background: '#fafafa' }}>
          <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'inherit', lineHeight: 1.6 }}>{scores.reasoning}</pre>
        </Card>
      ) : null}
    </Space>
  );
}
