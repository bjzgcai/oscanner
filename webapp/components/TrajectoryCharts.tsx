'use client';

import { Card, Row, Col } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useI18n } from './I18nContext';
import { TrajectoryCache, TrajectoryCheckpoint } from '@/types/trajectory';
import { useState, useEffect } from 'react';

interface TrajectoryChartsProps {
  trajectory: TrajectoryCache;
}

interface CommitByDate {
  date: string;
  count: number;
}

export default function TrajectoryCharts({ trajectory }: TrajectoryChartsProps) {
  const { t } = useI18n();
  const [commitsByDate, setCommitsByDate] = useState<CommitByDate[]>([]);
  const [loadingCommits, setLoadingCommits] = useState(true);

  useEffect(() => {
    // Fetch commits by date from API
    const fetchCommitsByDate = async () => {
      try {
        setLoadingCommits(true);
        const response = await fetch(`/api/trajectory/${trajectory.username}/commits-by-date`);
        const data = await response.json();

        if (data.success && data.data) {
          setCommitsByDate(data.data);
        }
      } catch (error) {
        console.error('Failed to fetch commits by date:', error);
      } finally {
        setLoadingCommits(false);
      }
    };

    if (trajectory && trajectory.username) {
      fetchCommitsByDate();
    }
  }, [trajectory]);

  if (!trajectory || trajectory.total_checkpoints === 0) {
    return null;
  }

  const checkpoints = trajectory.checkpoints;
  const latestCheckpoint = checkpoints[checkpoints.length - 1];
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

  // Chart 1: Radar Chart - Multi-dimensional comparison
  const radarOption = {
    title: {
      text: t('trajectory.charts.radar'),
      left: 'center',
      textStyle: { color: '#fff' },
    },
    backgroundColor: '#1a1a1a',
    legend: {
      data: [t('trajectory.latest'), t('trajectory.first')],
      bottom: 10,
      textStyle: { color: '#fff' },
    },
    radar: {
      indicator: dimensionKeys.map((key) => ({
        name: getDimensionLabel(key),
        max: 100,
      })),
      axisName: { color: '#fff' },
      splitArea: { areaStyle: { color: ['#333', '#444'] } },
      splitLine: { lineStyle: { color: '#555' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: Object.values(getDimensionScores(latestCheckpoint)),
            name: t('trajectory.latest'),
            areaStyle: { opacity: 0.3 },
            lineStyle: { color: '#00A3FF' },
            itemStyle: { color: '#00A3FF' },
          },
          {
            value: Object.values(getDimensionScores(firstCheckpoint)),
            name: t('trajectory.first'),
            areaStyle: { opacity: 0.2 },
            lineStyle: { color: '#10B981' },
            itemStyle: { color: '#10B981' },
          },
        ],
      },
    ],
  };

  // Chart 2: Line Chart - Score trend over time
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

  // Chart 3: Stacked Area Chart - Commit activity
  const activityData = checkpoints.map((cp) => ({
    checkpoint: `#${cp.checkpoint_id}`,
    additions: cp.evaluation.commits_summary.total_additions,
    deletions: cp.evaluation.commits_summary.total_deletions,
    files_changed: cp.evaluation.commits_summary.files_changed,
  }));

  const areaOption = {
    title: {
      text: t('trajectory.charts.activity'),
      left: 'center',
      textStyle: { color: '#fff' },
    },
    backgroundColor: '#1a1a1a',
    legend: {
      data: [
        t('trajectory.additions'),
        t('trajectory.deletions'),
        t('trajectory.files_changed'),
      ],
      bottom: 10,
      textStyle: { color: '#fff' },
    },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: activityData.map((d) => d.checkpoint),
      axisLabel: { color: '#fff' },
      axisLine: { lineStyle: { color: '#555' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#fff' },
      axisLine: { lineStyle: { color: '#555' } },
      splitLine: { lineStyle: { color: '#333' } },
    },
    series: [
      {
        name: t('trajectory.additions'),
        type: 'line',
        stack: 'total',
        areaStyle: {},
        data: activityData.map((d) => d.additions),
        itemStyle: { color: '#10B981' },
      },
      {
        name: t('trajectory.deletions'),
        type: 'line',
        stack: 'total',
        areaStyle: {},
        data: activityData.map((d) => d.deletions),
        itemStyle: { color: '#EF4444' },
      },
      {
        name: t('trajectory.files_changed'),
        type: 'line',
        stack: 'total',
        areaStyle: {},
        data: activityData.map((d) => d.files_changed),
        itemStyle: { color: '#F59E0B' },
      },
    ],
  };

  // Chart 4: Bar Chart - Checkpoint comparison (average score)
  const avgScores = checkpoints.map((cp) => {
    const scores = Object.values(getDimensionScores(cp));
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  });

  const barOption = {
    title: {
      text: t('trajectory.charts.comparison'),
      left: 'center',
      textStyle: { color: '#fff' },
    },
    backgroundColor: '#1a1a1a',
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: checkpoints.map((cp) => `#${cp.checkpoint_id}`),
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
    series: [
      {
        name: t('trajectory.avg_score'),
        type: 'bar',
        data: avgScores,
        itemStyle: {
          color: (params: any) => {
            const score = params.value;
            if (score >= 80) return '#10B981';
            if (score >= 60) return '#3B82F6';
            if (score >= 40) return '#F59E0B';
            return '#EF4444';
          },
        },
        label: {
          show: true,
          position: 'top',
          formatter: '{c}',
          color: '#fff',
        },
      },
    ],
  };

  // Chart 5: Bar Chart - Commit frequency by date (using real commit dates)
  const calendarOption = {
    title: {
      text: t('trajectory.charts.calendar'),
      left: 'center',
      textStyle: { color: '#fff' },
    },
    backgroundColor: '#1a1a1a',
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const data = params[0];
        return `${data.axisValue}<br/>${t('trajectory.charts.calendar')}: ${data.value}`;
      },
    },
    xAxis: {
      type: 'category',
      data: commitsByDate.map((d) => d.date),
      axisLabel: { color: '#fff', rotate: 45, fontSize: 10 },
      axisLine: { lineStyle: { color: '#555' } },
    },
    yAxis: {
      type: 'value',
      name: t('trajectory.commits_count'),
      nameTextStyle: { color: '#fff' },
      axisLabel: { color: '#fff' },
      axisLine: { lineStyle: { color: '#555' } },
      splitLine: { lineStyle: { color: '#333' } },
    },
    series: [
      {
        type: 'bar',
        data: commitsByDate.map((d) => d.count),
        itemStyle: { color: '#00A3FF' },
        barMaxWidth: 40,
      },
    ],
  };

  // Chart 6: Polar Bar Chart - Language distribution
  const firstLanguages = firstCheckpoint.evaluation.commits_summary.languages;
  const latestLanguages = latestCheckpoint.evaluation.commits_summary.languages;

  // Count language occurrences
  const allLanguages = [...new Set([...firstLanguages, ...latestLanguages])];

  const polarOption = {
    title: {
      text: t('trajectory.charts.languages'),
      left: 'center',
      textStyle: { color: '#fff' },
    },
    backgroundColor: '#1a1a1a',
    legend: {
      data: [t('trajectory.first'), t('trajectory.latest')],
      bottom: 10,
      textStyle: { color: '#fff' },
    },
    polar: {},
    angleAxis: {
      type: 'category',
      data: allLanguages,
      axisLabel: { color: '#fff' },
    },
    radiusAxis: {
      axisLabel: { color: '#fff' },
      axisLine: { lineStyle: { color: '#555' } },
      splitLine: { lineStyle: { color: '#333' } },
    },
    tooltip: {},
    series: [
      {
        name: t('trajectory.first'),
        type: 'bar',
        data: allLanguages.map((lang) => (firstLanguages.includes(lang) ? 1 : 0)),
        coordinateSystem: 'polar',
        itemStyle: { color: '#10B981' },
      },
      {
        name: t('trajectory.latest'),
        type: 'bar',
        data: allLanguages.map((lang) => (latestLanguages.includes(lang) ? 1 : 0)),
        coordinateSystem: 'polar',
        itemStyle: { color: '#00A3FF' },
      },
    ],
  };

  return (
    <div>
      <h3 style={{ marginBottom: '24px' }}>{t('trajectory.visualizations')}</h3>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts option={radarOption} style={{ height: '400px' }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts option={lineOption} style={{ height: '400px' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: '16px' }}>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts option={areaOption} style={{ height: '400px' }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts option={barOption} style={{ height: '400px' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: '16px' }}>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts option={calendarOption} style={{ height: '400px' }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card>
            <ReactECharts option={polarOption} style={{ height: '400px' }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
