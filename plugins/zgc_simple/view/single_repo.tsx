import React from 'react';
import { Alert, Card, Descriptions, Spin } from 'antd';
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

export default function PluginView(props: PluginSingleRepoViewProps) {
  const { evaluation, title, loading, error, t: tFromProps } = props;
  if (typeof tFromProps !== 'function') {
    throw new Error('zgc_simple plugin view requires `t(key, params?)` prop from host app.');
  }
  const t = tFromProps;
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        title={t('plugin.zgc_simple.single.error_title')}
        description={error}
      />
    );
  }
  if (loading) {
    return (
      <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin size="large" />
        <div style={{ color: '#9CA3AF', marginTop: 16 }}>
          {t('plugin.zgc_simple.single.loading')}
        </div>
      </Card>
    );
  }
  if (!evaluation) {
    return (
      <Alert
        type="info"
        showIcon
        title={t('plugin.zgc_simple.single.no_eval.title')}
        description={t('plugin.zgc_simple.single.no_eval.desc')}
      />
    );
  }
  const reasoning = typeof evaluation?.scores?.reasoning === 'string' ? (evaluation.scores.reasoning as string) : '';
  const scores = evaluation?.scores || {};
  const dims: Array<{ key: string; label: string }> = [
    { key: 'ai_fullstack', label: t('plugin.zgc_simple.dim.ai_fullstack') },
    { key: 'ai_architecture', label: t('plugin.zgc_simple.dim.ai_architecture') },
    { key: 'cloud_native', label: t('plugin.zgc_simple.dim.cloud_native') },
    { key: 'open_source', label: t('plugin.zgc_simple.dim.open_source') },
    { key: 'intelligent_dev', label: t('plugin.zgc_simple.dim.intelligent_dev') },
    { key: 'leadership', label: t('plugin.zgc_simple.dim.leadership') },
  ];
  const languages = evaluation?.commits_summary?.languages || [];
  const scoreValue = (key: string) => {
    const raw = scores[key];
    const n = typeof raw === 'number' ? raw : typeof raw === 'string' ? Number(raw) : 0;
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
  };

  const chartData = {
    labels: dims.map((d) => d.label),
    datasets: [
      {
        label: t('plugin.zgc_simple.single.chart.label'),
        data: dims.map((d) => scoreValue(d.key)),
        fill: true,
        backgroundColor: 'rgba(255, 235, 0, 0.15)',
        borderColor: '#FFEB00',
        pointBackgroundColor: '#00F0FF',
        pointBorderColor: '#0A0A0A',
        pointHoverBackgroundColor: '#FF006B',
        pointHoverBorderColor: '#FFEB00',
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
        ticks: { stepSize: 20, backdropColor: 'transparent', color: '#B0B0B0' },
        pointLabels: { color: '#FFFFFF' },
        angleLines: { display: true, color: '#333', lineWidth: 2 },
        grid: { color: '#333', lineWidth: 2 },
      },
    },
  };

  return (
    <Card
      style={{
        border: '1px solid #F59E0B',
        background: 'linear-gradient(180deg, #111827 0%, #0B1220 100%)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <h3 style={{ margin: 0, color: '#FBBF24' }}>
          {title || t('plugin.zgc_simple.single.title_default')}
        </h3>
        <div style={{ color: '#9CA3AF', fontSize: 12 }}>
          <span style={{ color: '#FDE68A', fontWeight: 800, marginRight: 10 }}>
            {t('plugin.zgc_simple.single.banner.active')}
          </span>
          {evaluation?.plugin ? `plugin=${evaluation.plugin}` : 'plugin=zgc_simple'}
          {evaluation?.plugin_version ? ` @ ${evaluation.plugin_version}` : ''}
        </div>
      </div>

      <div style={{ marginTop: 12, height: 360 }}>
        <Radar data={chartData} options={chartOptions as any} />
      </div>

      <Descriptions
        size="small"
        column={2}
        style={{ marginTop: 12 }}
        styles={{
          label: { color: '#9CA3AF' },
          content: { color: '#E5E7EB' },
        }}
        bordered
      >
        <Descriptions.Item label={t('plugin.zgc_simple.single.desc.commits')}>
          {evaluation?.total_commits_analyzed ?? '-'}
        </Descriptions.Item>
        <Descriptions.Item label={t('plugin.zgc_simple.single.desc.files_changed')}>
          {evaluation?.commits_summary?.files_changed ?? '-'}
        </Descriptions.Item>
        <Descriptions.Item label={t('plugin.zgc_simple.single.desc.additions')}>
          {evaluation?.commits_summary?.total_additions ?? '-'}
        </Descriptions.Item>
        <Descriptions.Item label={t('plugin.zgc_simple.single.desc.deletions')}>
          {evaluation?.commits_summary?.total_deletions ?? '-'}
        </Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 12 }}>
        <div style={{ color: '#F9FAFB', fontWeight: 700, marginBottom: 8 }}>
          {t('plugin.zgc_simple.single.section.scores')}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {dims.map((d) => {
            const v = typeof scores[d.key] === 'number' ? (scores[d.key] as number) : 0;
            return (
              <div
                key={d.key}
                style={{
                  border: '1px solid #1F2937',
                  borderRadius: 10,
                  padding: 10,
                  background: '#0A0F1C',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div style={{ color: '#E5E7EB', fontWeight: 600 }}>{d.label}</div>
                  <div style={{ color: '#FBBF24', fontWeight: 700 }}>{v}</div>
                </div>
                <div style={{ height: 8, background: '#111827', borderRadius: 999, overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${Math.min(100, Math.max(0, v))}%`,
                      height: 8,
                      background: 'linear-gradient(90deg, #FBBF24 0%, #F59E0B 100%)',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {languages.length ? (
        <div style={{ marginTop: 12, color: '#D1D5DB', fontSize: 13 }}>
          <span style={{ color: '#FBBF24', fontWeight: 700, marginRight: 8 }}>
            {t('plugin.zgc_simple.single.section.languages')}
          </span>
          {languages.join(', ')}
        </div>
      ) : null}

      {reasoning ? (
        <Card style={{ marginTop: 12, background: '#0A0F1C', border: '1px solid #F59E0B' }}>
          <div style={{ color: '#FBBF24', fontWeight: 800, marginBottom: 8 }}>
            {t('plugin.zgc_simple.single.section.notes')}
          </div>
          <div style={{ color: '#E5E7EB' }}>
            <ReactMarkdown>{reasoning}</ReactMarkdown>
          </div>
        </Card>
      ) : null}
    </Card>
  );
}


