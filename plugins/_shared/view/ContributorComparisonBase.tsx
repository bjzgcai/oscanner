import React, { useState } from 'react';
import { Alert, Card, Descriptions, Empty, Radio, Space, Spin } from 'antd';
import { BarChartOutlined, RadarChartOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import type { RadioChangeEvent } from 'antd';

type ChartType = 'radar' | 'bar';

import type { ContributorComparisonBaseProps } from './types';
export type { Comparison, ComparisonScore, ContributorComparisonData, ContributorComparisonBaseProps } from './types';

export default function ContributorComparisonBase(props: ContributorComparisonBaseProps) {
  const { data, loading = false, error, theme = 'simple' } = props;
  const [chartType, setChartType] = useState<ChartType>('radar');

  if (loading) {
    return (
      <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Spin size="large" />
        <div style={{ color: 'rgba(0, 0, 0, 0.65)', marginTop: 20 }}>Evaluating contributor across repositories...</div>
      </Card>
    );
  }

  if (error) {
    return <Alert title="Error" description={error} type="error" showIcon style={{ borderRadius: 8 }} />;
  }

  if (!data || !data.success || !data.comparisons || data.comparisons.length === 0) {
    return (
      <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Empty description={<span style={{ color: 'rgba(0, 0, 0, 0.65)' }}>No comparison data available</span>} />
      </Card>
    );
  }

  const shortDimensionNames = [
    'AI Model\nFull-Stack',
    'AI Native\nArchitecture',
    'Cloud\nNative',
    'Open Source\nCollaboration',
    'Intelligent\nDevelopment',
    'Engineering\nLeadership',
  ];

  const colors =
    theme === 'rubric'
      ? ['#7C3AED', '#8B5CF6', '#A78BFA', '#C4B5FD', '#DDD6FE', '#5B21B6']
      : ['#0891B2', '#1E40AF', '#059669', '#D97706', '#DC2626', '#6D28D9'];

  const dimensionKeys = [
    'ai_model_fullstack',
    'ai_native_architecture',
    'cloud_native',
    'open_source_collaboration',
    'intelligent_development',
    'engineering_leadership',
  ] as const;

  const getRadarOptions = () => {
    const seriesData = data.comparisons.map((comp, idx) => ({
      name: comp.repo,
      value: Object.values(comp.scores),
      itemStyle: { color: colors[idx % colors.length] },
    }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#ffffff',
        borderColor: '#d9d9d9',
        borderWidth: 1,
        textStyle: { color: 'rgba(0, 0, 0, 0.85)' },
      },
      legend: {
        data: data.comparisons.map((c) => c.repo),
        textStyle: { color: 'rgba(0, 0, 0, 0.65)' },
        bottom: 0,
      },
      radar: {
        indicator: shortDimensionNames.map((name) => ({ name, max: 100 })),
        splitArea: { areaStyle: { color: ['rgba(0,0,0,0.02)', 'rgba(0,0,0,0.06)'] } },
        axisLine: { lineStyle: { color: 'rgba(0, 0, 0, 0.15)' } },
        splitLine: { lineStyle: { color: 'rgba(0, 0, 0, 0.15)' } },
        name: { textStyle: { color: 'rgba(0, 0, 0, 0.65)', fontSize: 12, fontWeight: 600 } },
      },
      series: [
        {
          type: 'radar',
          data: seriesData,
          lineStyle: { width: 3 },
          areaStyle: { opacity: 0.15 },
          symbol: 'circle',
          symbolSize: 8,
        },
      ],
    };
  };

  const getBarOptions = () => {
    const categories = shortDimensionNames;
    const series = data.comparisons.map((comp, idx) => ({
      name: comp.repo,
      type: 'bar',
      data: Object.values(comp.scores),
      itemStyle: { color: colors[idx % colors.length] },
    }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: '#ffffff',
        borderColor: '#d9d9d9',
        borderWidth: 1,
        textStyle: { color: 'rgba(0, 0, 0, 0.85)' },
      },
      legend: {
        data: data.comparisons.map((c) => c.repo),
        textStyle: { color: 'rgba(0, 0, 0, 0.65)' },
        bottom: 0,
      },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { color: 'rgba(0,0,0,0.65)', fontWeight: 600, interval: 0 },
        axisLine: { lineStyle: { color: 'rgba(0,0,0,0.15)' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: { color: 'rgba(0,0,0,0.65)' },
        splitLine: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
      },
      series,
    };
  };

  const pluginUsed = data?.plugin_used || '';
  const isRubric = theme === 'rubric' || String(pluginUsed).includes('ai_native') || String(pluginUsed).includes('2026');

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ fontSize: 18, fontWeight: 800 }}>
            Contributor Comparison <span style={{ color: 'rgba(0,0,0,0.45)', fontWeight: 600, fontSize: 12 }}>(plugin={pluginUsed || '-'})</span>
          </div>
          <Radio.Group value={chartType} onChange={(e: RadioChangeEvent) => setChartType(e.target.value)} buttonStyle="solid">
            <Radio.Button value="radar">
              <RadarChartOutlined /> Radar
            </Radio.Button>
            <Radio.Button value="bar">
              <BarChartOutlined /> Bar
            </Radio.Button>
          </Radio.Group>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <ReactECharts option={chartType === 'radar' ? getRadarOptions() : getBarOptions()} style={{ height: 520, width: '100%' }} notMerge={true} lazyUpdate={true} />
      </Card>

      <Card>
        <Space orientation="vertical" size={12} style={{ width: '100%' }}>
          <Descriptions
            bordered
            size="small"
            column={{ xs: 1, sm: 1, md: 2, lg: 3, xl: 3, xxl: 3 }}
            styles={{
              label: { fontWeight: 700, width: 220 },
              content: { color: 'rgba(0,0,0,0.85)' },
            }}
          >
            <Descriptions.Item label="Contributor">{data.contributor}</Descriptions.Item>
            <Descriptions.Item label="Repos Evaluated">{data.aggregate.total_repos_evaluated}</Descriptions.Item>
            <Descriptions.Item label="Total Commits">{data.aggregate.total_commits}</Descriptions.Item>
          </Descriptions>

          <div style={{ fontWeight: 800, marginTop: 4 }}>Average Scores</div>
          <Descriptions
            bordered
            size="small"
            column={{ xs: 1, sm: 2, md: 3, lg: 3, xl: 3, xxl: 3 }}
            styles={{
              label: { fontWeight: 700, width: 220 },
              content: { color: 'rgba(0,0,0,0.85)' },
            }}
          >
            {dimensionKeys.map((k) => (
              <Descriptions.Item key={k} label={k}>
                {Number((data.aggregate.average_scores as any)[k] || 0).toFixed(1)}
              </Descriptions.Item>
            ))}
          </Descriptions>

          {data.failed_repos && data.failed_repos.length > 0 ? (
            <Alert
              type={isRubric ? 'warning' : 'info'}
              showIcon
              title="Some repos failed"
              description={
                <div>
                  {data.failed_repos.slice(0, 8).map((r) => (
                    <div key={r.repo}>
                      <b>{r.repo}</b>: {r.reason}
                    </div>
                  ))}
                </div>
              }
            />
          ) : null}
        </Space>
      </Card>
    </div>
  );
}


