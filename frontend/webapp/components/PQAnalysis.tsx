'use client';

import { useState } from 'react';
import { Card, Spin, Alert, Statistic, Row, Col, Typography, Divider, Input, Button, Space } from 'antd';
import { CheckCircleOutlined, BarChartOutlined, SearchOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useI18n } from './I18nContext';
import { getApiBaseUrl } from '../utils/apiBase';

const { Title, Text } = Typography;

interface Activity {
  activity_name: string;
  total_score: number;
  accuracy_rate: number;  // Percentage (0-100), e.g., 85.0 means 85%
  total_questions: number;
  answered_questions: number;
  correct_answers: number;
  ranking_position: number | null;
  total_participants: number;
  ranking_percentile: number;  // Percentage (0-100), e.g., 90.0 means 90%
  activity_started_at: string;
  activity_ended_at: string | null;
}

interface UserScoreData {
  external_user_id: string;
  series_name: string;
  total_activities: number;
  participated_activities: number;
  activities: Activity[];
  query_time: string;
}

interface ApiResponse {
  success: boolean;
  data?: UserScoreData;
  error?: string;
}

// Hardcoded API key
const API_KEY = 'BbjiZsAwDnLNwqXCFRLztOtZfP-0OrfU7nUsykW4s2Y';

export default function PQAnalysis() {
  const { t } = useI18n();
  const [userId, setUserId] = useState('JUFV4ZFT');
  const [seriesName, setSeriesName] = useState('vibe-coding-2026-3');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<UserScoreData | null>(null);

  const fetchData = async () => {
    if (!userId.trim() || !seriesName.trim()) {
      setError('Please enter both User ID and Series Name');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const apiBase = getApiBaseUrl();
      const url = `${apiBase}/api/external/query-score?external_user_id=${encodeURIComponent(userId)}&series_name=${encodeURIComponent(seriesName)}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result: ApiResponse = await response.json();

      if (result.success && result.data) {
        setData(result.data);
      } else {
        setError(result.error || t('pq.error'));
      }
    } catch (err) {
      console.error('Failed to fetch PQ data:', err);
      setError(err instanceof Error ? err.message : t('pq.error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Title level={2}>{t('pq.title')}</Title>

      {/* Query Form */}
      <Card style={{ marginBottom: '24px' }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <div>
                <Text strong style={{ display: 'block', marginBottom: '8px' }}>
                  {t('pq.input_user_id')}
                </Text>
                <Input
                  size="large"
                  placeholder="JUFV4ZFT"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  onPressEnter={fetchData}
                />
              </div>
            </Col>
            <Col xs={24} md={12}>
              <div>
                <Text strong style={{ display: 'block', marginBottom: '8px' }}>
                  {t('pq.input_series_name')}
                </Text>
                <Input
                  size="large"
                  placeholder="vibe-coding-2026-3"
                  value={seriesName}
                  onChange={(e) => setSeriesName(e.target.value)}
                  onPressEnter={fetchData}
                />
              </div>
            </Col>
            <Col xs={24} md={4}>
              <div style={{ paddingTop: '30px' }}>
                <Button
                  type="primary"
                  size="large"
                  icon={<SearchOutlined />}
                  onClick={fetchData}
                  loading={loading}
                  block
                >
                  {loading ? t('pq.querying') : t('pq.query_button')}
                </Button>
              </div>
            </Col>
          </Row>
        </Space>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert
          message={t('pq.error')}
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: '24px' }}
        />
      )}

      {/* Loading State */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text>{t('pq.loading')}</Text>
          </div>
        </div>
      )}

      {/* No Data Yet */}
      {!loading && !error && !data && (
        <Alert
          message={t('pq.enter_params')}
          type="info"
          showIcon
          style={{ marginBottom: '24px' }}
        />
      )}

      {/* Data Display */}
      {!loading && data && data.activities && data.activities.length > 0 && (
        <>
          {/* Summary Statistics */}
          <Row gutter={[16, 16]} style={{ marginBottom: '32px' }}>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('pq.series_name')}
                  value={data.series_name}
                  valueStyle={{ fontSize: '18px' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('pq.user_id')}
                  value={data.external_user_id}
                  valueStyle={{ fontSize: '18px' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('pq.total_activities')}
                  value={data.total_activities}
                  prefix={<BarChartOutlined />}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('pq.participated_activities')}
                  value={data.participated_activities}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
          </Row>

          <Divider />

          {/* Activity Performance Chart */}
          <Title level={3} style={{ marginBottom: '24px' }}>
            Activity Performance
          </Title>

          <Card>
            <ReactECharts
              option={{
                tooltip: {
                  trigger: 'axis',
                  formatter: (params: unknown) => {
                    const paramsArray = params as Array<{ dataIndex: number; marker: string; seriesName: string; value: number }>;
                    if (!paramsArray || paramsArray.length === 0) return '';
                    const dataIndex = paramsArray[0].dataIndex;
                    const activity = data.activities[dataIndex];

                    let tooltip = `<strong>${activity.activity_name}</strong><br/>`;
                    tooltip += `<br/><strong>Performance Metrics:</strong><br/>`;
                    paramsArray.forEach((param: { marker: string; seriesName: string; value: number }) => {
                      tooltip += `${param.marker} ${param.seriesName}: ${param.value.toFixed(1)}%<br/>`;
                    });
                    tooltip += `<br/><strong>Details:</strong><br/>`;
                    tooltip += `Total Score: ${activity.total_score}<br/>`;
                    tooltip += `Correct: ${activity.correct_answers} / ${activity.total_questions}<br/>`;
                    tooltip += `Ranking: ${activity.ranking_position !== null ? `#${activity.ranking_position}` : 'N/A'} / ${activity.total_participants}<br/>`;

                    return tooltip;
                  }
                },
                legend: {
                  data: [t('pq.accuracy_rate'), t('pq.ranking_percentile')],
                  bottom: 10,
                },
                xAxis: {
                  type: 'category',
                  data: data.activities.map((activity) => activity.activity_name),
                  axisLabel: {
                    rotate: 30,
                    interval: 0,
                  },
                },
                yAxis: {
                  type: 'value',
                  min: 0,
                  max: 100,
                  axisLabel: {
                    formatter: '{value}%'
                  },
                },
                series: [
                  {
                    name: t('pq.accuracy_rate'),
                    type: 'line',
                    smooth: true,
                    data: data.activities.map((activity) => activity.accuracy_rate),
                    lineStyle: {
                      width: 3,
                    },
                    itemStyle: {
                      color: '#1890ff',
                    },
                    areaStyle: {
                      color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                          { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
                          { offset: 1, color: 'rgba(24, 144, 255, 0.05)' }
                        ]
                      }
                    },
                  },
                  {
                    name: t('pq.ranking_percentile'),
                    type: 'line',
                    smooth: true,
                    data: data.activities.map((activity) => activity.ranking_percentile),
                    lineStyle: {
                      width: 3,
                    },
                    itemStyle: {
                      color: '#faad14',
                    },
                    areaStyle: {
                      color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                          { offset: 0, color: 'rgba(250, 173, 20, 0.3)' },
                          { offset: 1, color: 'rgba(250, 173, 20, 0.05)' }
                        ]
                      }
                    },
                  },
                ],
              }}
              style={{ height: '500px' }}
            />
          </Card>
        </>
      )}

      {/* No Data After Query */}
      {!loading && data && (!data.activities || data.activities.length === 0) && (
        <Alert message={t('pq.no_data')} type="info" showIcon />
      )}
    </div>
  );
}
