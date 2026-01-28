'use client';

import { Card } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useI18n } from './I18nContext';
import { TrajectoryCache, TrajectoryCheckpoint } from '@/types/trajectory';

interface TrajectoryChartsProps {
  trajectory: TrajectoryCache;
}

export default function TrajectoryCharts({ trajectory }: TrajectoryChartsProps) {
  const { t } = useI18n();

  if (!trajectory || trajectory.total_checkpoints === 0) {
    return null;
  }

  const checkpoints = trajectory.checkpoints;
  const firstCheckpoint = checkpoints[0];

  // Get plugin ID from the first checkpoint
  const pluginId = firstCheckpoint.evaluation.plugin;

  // Extract dimension keys dynamically from scores (excluding 'reasoning')
  const getDimensionKeys = (scores: any): string[] => {
    return Object.keys(scores).filter(
      (key) => key !== 'reasoning' && scores[key] !== null && scores[key] !== undefined
    );
  };

  // Get all dimension keys from first checkpoint
  const dimensionKeys = getDimensionKeys(firstCheckpoint.evaluation.scores);

  // Extract scores from checkpoints (returns object with dimension keys)
  const getDimensionScores = (checkpoint: TrajectoryCheckpoint) => {
    const scores: any = checkpoint.evaluation.scores;
    const result: Record<string, number> = {};
    dimensionKeys.forEach((key) => {
      result[key] = scores[key] ?? 0;
    });
    return result;
  };

  // Get dimension label with plugin-specific translation
  const getDimensionLabel = (dimensionKey: string): string => {
    const pluginSpecificKey = `plugin.${pluginId}.dim.${dimensionKey}`;
    const translated = t(pluginSpecificKey);
    // If translation not found, fall back to generic dimension key
    if (translated === pluginSpecificKey) {
      return t(`dimensions.${dimensionKey}`) || dimensionKey;
    }
    return translated;
  };

  // Chart 1: Line Chart - Score trend over time
  const trendData = checkpoints.map((cp) => ({
    checkpoint: `#${cp.checkpoint_id}`,
    ...getDimensionScores(cp),
  }));

  const lineOption = {
    title: {
      text: t('trajectory.charts.trend'),
      left: 'center',
      textStyle: { color: '#fff' },
    },
    backgroundColor: '#1a1a1a',
    legend: {
      data: dimensionKeys.map((key) => getDimensionLabel(key)),
      bottom: 10,
      textStyle: { color: '#fff' },
      type: 'scroll',
    },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: trendData.map((d) => d.checkpoint),
      axisLabel: { color: '#fff' },
      axisLine: { lineStyle: { color: '#555' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#fff' },
      axisLine: { lineStyle: { color: '#555' } },
      splitLine: { lineStyle: { color: '#333' } },
    },
    series: dimensionKeys.map((key) => ({
      name: getDimensionLabel(key),
      type: 'line',
      smooth: true,
      data: trendData.map((d: any) => d[key]),
    })),
  };

  return (
    <div>
      <h3 style={{ marginBottom: '24px' }}>{t('trajectory.visualizations')}</h3>

      <Card>
        <ReactECharts option={lineOption} style={{ height: '400px' }} />
      </Card>
    </div>
  );
}
