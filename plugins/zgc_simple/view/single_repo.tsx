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

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

type EvalData = {
  scores: Record<string, number | string>;
  total_commits_analyzed?: number;
  commits_summary?: { total_additions: number; total_deletions: number; files_changed: number; languages: string[] };
  plugin?: string;
  plugin_version?: string;
};

export default function PluginView(props: { evaluation: EvalData | null; title?: string; loading?: boolean; error?: string }) {
  const { evaluation, title, loading, error } = props;
  if (error) {
    return <Alert type="error" showIcon title="Evaluation failed" description={error} />;
  }
  if (loading) {
    return (
      <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin size="large" />
        <div style={{ color: '#9CA3AF', marginTop: 16 }}>Evaluating with plugin...</div>
      </Card>
    );
  }
  if (!evaluation) {
    return <Alert type="info" showIcon title="No evaluation yet" description="Select an author to start evaluation." />;
  }
  const reasoning = typeof evaluation?.scores?.reasoning === 'string' ? (evaluation.scores.reasoning as string) : '';
  const scores = evaluation?.scores || {};
  const dims: Array<{ key: string; label: string }> = [
    { key: 'ai_fullstack', label: 'AI Full-Stack' },
    { key: 'ai_architecture', label: 'AI Architecture' },
    { key: 'cloud_native', label: 'Cloud Native' },
    { key: 'open_source', label: 'Open Source' },
    { key: 'intelligent_dev', label: 'Intelligent Dev' },
    { key: 'leadership', label: 'Leadership' },
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
        label: 'Engineering Skills',
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
        <h3 style={{ margin: 0, color: '#FBBF24' }}>{title || 'SIMPLE VIEW (Single Repo)'}</h3>
        <div style={{ color: '#9CA3AF', fontSize: 12 }}>
          <span style={{ color: '#FDE68A', fontWeight: 800, marginRight: 10 }}>PLUGIN VIEW ACTIVE</span>
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
        <Descriptions.Item label="Commits">{evaluation?.total_commits_analyzed ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Files Changed">{evaluation?.commits_summary?.files_changed ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Additions">{evaluation?.commits_summary?.total_additions ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Deletions">{evaluation?.commits_summary?.total_deletions ?? '-'}</Descriptions.Item>
      </Descriptions>

      <div style={{ marginTop: 12 }}>
        <div style={{ color: '#F9FAFB', fontWeight: 700, marginBottom: 8 }}>Six-Dimension Scores</div>
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
          <span style={{ color: '#FBBF24', fontWeight: 700, marginRight: 8 }}>Languages:</span>
          {languages.join(', ')}
        </div>
      ) : null}

      {reasoning ? (
        <Card style={{ marginTop: 12, background: '#0A0F1C', border: '1px solid #F59E0B' }}>
          <div style={{ color: '#FBBF24', fontWeight: 800, marginBottom: 8 }}>Notes (Simple)</div>
          <div style={{ color: '#E5E7EB' }}>
            <ReactMarkdown>{reasoning}</ReactMarkdown>
          </div>
        </Card>
      ) : null}
    </Card>
  );
}


