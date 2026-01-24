import React from 'react';
import { Alert, Card, Spin, Tag } from 'antd';
import ReactMarkdown from 'react-markdown';
import { Radar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import type { PluginSingleRepoViewProps } from '../../_shared/view/types';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

function levelFromScore(score: number): string {
  if (score >= 85) return 'L5';
  if (score >= 70) return 'L4';
  if (score >= 50) return 'L3';
  if (score >= 30) return 'L2';
  return 'L1';
}

function levelColor(level: string): string {
  if (level === 'L5') return 'purple';
  if (level === 'L4') return 'geekblue';
  if (level === 'L3') return 'green';
  if (level === 'L2') return 'gold';
  return 'red';
}

export default function PluginView(props: PluginSingleRepoViewProps) {
  const { evaluation, title, loading, error, t: tFromProps } = props;
  if (typeof tFromProps !== 'function') {
    throw new Error('zgc_ai_native_2026 plugin view requires `t(key, params?)` prop from host app.');
  }
  const t = tFromProps;
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        title={t('plugin.zgc_ai_native_2026.single.error_title')}
        description={error}
      />
    );
  }
  if (loading) {
    return (
      <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin size="large" />
        <div style={{ color: '#9CA3AF', marginTop: 16 }}>
          {t('plugin.zgc_ai_native_2026.single.loading')}
        </div>
      </Card>
    );
  }
  if (!evaluation) {
    return (
      <Alert
        type="info"
        showIcon
        title={t('plugin.zgc_ai_native_2026.single.no_eval.title')}
        description={t('plugin.zgc_ai_native_2026.single.no_eval.desc')}
      />
    );
  }
  const s = evaluation?.scores || {};
  const keys = ['spec_quality', 'cloud_architecture', 'ai_engineering', 'mastery_professionalism'];
  const avg =
    keys.reduce((acc, k) => acc + (typeof s[k] === 'number' ? (s[k] as number) : 0), 0) / (keys.length || 1);
  const lvl = levelFromScore(avg);
  const reasoning = typeof s.reasoning === 'string' ? (s.reasoning as string) : '';

  // Prepare radar chart data for 4 dimensions
  const dims: Array<{ key: string; label: string }> = [
    { key: 'spec_quality', label: t('plugin.zgc_ai_native_2026.dim.spec_quality') },
    { key: 'cloud_architecture', label: t('plugin.zgc_ai_native_2026.dim.cloud_architecture') },
    { key: 'ai_engineering', label: t('plugin.zgc_ai_native_2026.dim.ai_engineering') },
    { key: 'mastery_professionalism', label: t('plugin.zgc_ai_native_2026.dim.mastery_professionalism') },
  ];

  const scoreValue = (key: string) => {
    const raw = s[key];
    const n = typeof raw === 'number' ? raw : typeof raw === 'string' ? Number(raw) : 0;
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
  };

  const chartData = {
    labels: dims.map((d) => d.label),
    datasets: [
      {
        label: t('plugin.zgc_ai_native_2026.single.chart.label') || 'Scores',
        data: dims.map((d) => scoreValue(d.key)),
        fill: true,
        backgroundColor: 'rgba(110, 231, 183, 0.15)',
        borderColor: '#10B981',
        pointBackgroundColor: '#6EE7B7',
        pointBorderColor: '#052e2b',
        pointHoverBackgroundColor: '#FBBF24',
        pointHoverBorderColor: '#10B981',
        pointRadius: 6,
        pointHoverRadius: 10,
        borderWidth: 3,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      r: {
        suggestedMin: 0,
        suggestedMax: 100,
        ticks: { stepSize: 20, backdropColor: 'transparent', color: '#9CA3AF' },
        pointLabels: { color: '#E5E7EB' },
        angleLines: { display: true, color: '#064E3B', lineWidth: 2 },
        grid: { color: '#064E3B', lineWidth: 2 },
      },
    },
  };

  return (
    <Card
      style={{
        border: '2px solid #10B981',
        background: 'linear-gradient(180deg, #052e2b 0%, #0B1220 60%, #0A0F1C 100%)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <h3 style={{ margin: 0, color: '#6EE7B7' }}>
          {title || t('plugin.zgc_ai_native_2026.single.title_default')}
        </h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Tag color={levelColor(lvl)}>
            {lvl} ({t('plugin.zgc_ai_native_2026.single.tag.avg')} {avg.toFixed(1)})
          </Tag>
          <div style={{ color: '#9CA3AF', fontSize: 12 }}>
            <span style={{ color: '#93C5FD', fontWeight: 800, marginRight: 10 }}>
              {t('plugin.zgc_ai_native_2026.single.banner.active')}
            </span>
            {evaluation?.plugin ? `plugin=${evaluation.plugin}` : 'plugin=zgc_ai_native_2026'}
            {evaluation?.plugin_version ? ` @ ${evaluation.plugin_version}` : ''}
          </div>
        </div>
      </div>

      <div id="radar-chart-export" style={{ marginTop: 12, height: 300 }}>
        <Radar data={chartData} options={chartOptions as any} />
      </div>

      <div style={{ marginTop: 12 }}>
        <div style={{ color: '#E5E7EB', fontWeight: 700, marginBottom: 8 }}>
          {t('plugin.zgc_ai_native_2026.single.section.mapping')}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {keys.map((k) => {
            const v = typeof s[k] === 'number' ? (s[k] as number) : 0;
            const lv = levelFromScore(v);
            return (
              <Tag key={k} color={levelColor(lv)}>
                {k}: {v} → {lv}
              </Tag>
            );
          })}
        </div>
      </div>

      <div style={{ marginTop: 12, border: '1px solid #064E3B', borderRadius: 12, padding: 12, background: '#061A18' }}>
        <div style={{ color: '#6EE7B7', fontWeight: 700, marginBottom: 8 }}>
          {t('plugin.zgc_ai_native_2026.single.section.focus_title')}
        </div>
        <div style={{ color: '#D1FAE5', fontSize: 13, lineHeight: 1.6 }}>
          {(['1', '2', '3', '4', '5'] as const).map((n) => (
            <span key={n}>
              - {t(`plugin.zgc_ai_native_2026.single.focus.${n}`)}
              <br />
            </span>
          ))}
        </div>
      </div>

      {reasoning ? (
        <Card style={{ marginTop: 12, background: '#071A17', border: '1px solid #10B981' }}>
          <div style={{ color: '#6EE7B7', fontWeight: 800, marginBottom: 8 }}>
            {t('plugin.zgc_ai_native_2026.single.section.summary')}
          </div>
          <div style={{ color: '#E5E7EB' }}>
            <ReactMarkdown>{reasoning}</ReactMarkdown>
          </div>
        </Card>
      ) : null}
    </Card>
  );
}


