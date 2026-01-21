import React from 'react';
import { Card, Tag } from 'antd';
import ContributorComparisonBase from '../../_shared/view/ContributorComparisonBase';

type Props = {
  data: any;
  loading?: boolean;
  error?: string;
};

function levelFromScore(score: number): string {
  if (score >= 85) return 'L5';
  if (score >= 70) return 'L4';
  if (score >= 50) return 'L3';
  if (score >= 30) return 'L2';
  return 'L1';
}

export default function CompareView(props: Props) {
  const { data, loading, error } = props;
  const pluginUsed = data?.plugin_used || 'zgc_ai_native_2026';
  const pluginVersion = data?.comparisons?.[0]?.plugin_version || '';

  const avgScores = data?.aggregate?.average_scores || {};
  const avg =
    (Number(avgScores.ai_model_fullstack || 0) +
      Number(avgScores.ai_native_architecture || 0) +
      Number(avgScores.cloud_native || 0) +
      Number(avgScores.open_source_collaboration || 0) +
      Number(avgScores.intelligent_development || 0) +
      Number(avgScores.engineering_leadership || 0)) /
    6;
  const lvl = levelFromScore(avg);

  return (
    <Card
      style={{
        border: '3px solid #7C3AED',
        background: 'linear-gradient(180deg, #1F1638 0%, #0B1220 60%, #0A0F1C 100%)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ color: '#C4B5FD', fontWeight: 900, letterSpacing: 0.2, fontSize: 18 }}>
            RUBRIC COMPARE VIEW (Multi-Repo, AI-Native 2026)
          </div>
          <div style={{ color: '#DDD6FE', fontSize: 12, marginTop: 4 }}>
            Compare is rubric-themed (L1–L5). If you see this wrapper, plugin compare view is active.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Tag color="purple" style={{ fontWeight: 900 }}>
            MULTI-REPO COMPARE VIEW ACTIVE
          </Tag>
          <Tag color="geekblue" style={{ fontWeight: 900 }}>
            {lvl} (avg {Number.isFinite(avg) ? avg.toFixed(1) : '0.0'})
          </Tag>
          <Tag color="blue" style={{ fontWeight: 900 }}>
            plugin={pluginUsed}
            {pluginVersion ? ` @ ${pluginVersion}` : ''}
          </Tag>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <ContributorComparisonBase data={data} loading={loading} error={error} theme="rubric" />
      </div>
    </Card>
  );
}


