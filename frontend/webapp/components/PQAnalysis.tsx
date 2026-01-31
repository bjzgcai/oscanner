'use client';

import { useState } from 'react';
import { Card, Spin, Alert, Statistic, Row, Col, Progress, Typography, Divider, Input, Button, Space } from 'antd';
import { TrophyOutlined, CheckCircleOutlined, BarChartOutlined, SearchOutlined } from '@ant-design/icons';
import { useI18n } from './I18nContext';
import { getApiBaseUrl } from '../utils/apiBase';

const { Title, Text } = Typography;

interface Activity {
  activity_name: string;
  total_score: number;
  accuracy_rate: number;
  total_questions: number;
  answered_questions: number;
  correct_answers: number;
  ranking_position: number | null;
  total_participants: number;
  ranking_percentile: number;
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
  const [userId, setUserId] = useState('Q54XCEY5');
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
                  placeholder="Q54XCEY5"
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

          {/* Activities List */}
          <Title level={3} style={{ marginBottom: '24px' }}>
            Activity Performance
          </Title>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {data.activities.map((activity, index) => (
              <Card
                key={index}
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TrophyOutlined style={{ color: '#faad14' }} />
                    <span>{activity.activity_name}</span>
                  </div>
                }
                extra={
                  <Text type="secondary">
                    {t('pq.total_score')}: {activity.total_score}
                  </Text>
                }
              >
                <Row gutter={[16, 16]}>
                  {/* Accuracy Rate */}
                  <Col xs={24} md={12}>
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <Text strong>{t('pq.accuracy_rate')}</Text>
                        <Text>{(activity.accuracy_rate * 100).toFixed(1)}%</Text>
                      </div>
                      <Progress
                        percent={activity.accuracy_rate * 100}
                        strokeColor={{
                          '0%': '#108ee9',
                          '100%': '#87d068',
                        }}
                        format={(percent) => `${percent?.toFixed(1)}%`}
                      />
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {activity.correct_answers} / {activity.total_questions} {t('pq.correct_answers').toLowerCase()}
                      </Text>
                    </div>
                  </Col>

                  {/* Ranking Percentile */}
                  <Col xs={24} md={12}>
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <Text strong>{t('pq.ranking_percentile')}</Text>
                        <Text>{(activity.ranking_percentile * 100).toFixed(1)}%</Text>
                      </div>
                      <Progress
                        percent={activity.ranking_percentile * 100}
                        strokeColor={{
                          '0%': '#faad14',
                          '100%': '#f5222d',
                        }}
                        format={(percent) => `${percent?.toFixed(1)}%`}
                      />
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {t('pq.ranking_position')}: {activity.ranking_position !== null ? `#${activity.ranking_position}` : 'N/A'} / {activity.total_participants} {t('pq.total_participants').toLowerCase()}
                      </Text>
                    </div>
                  </Col>
                </Row>

                {/* Additional Details */}
                <Row gutter={[16, 16]} style={{ marginTop: '16px' }}>
                  <Col xs={12} sm={6}>
                    <Statistic
                      title={t('pq.total_questions')}
                      value={activity.total_questions}
                      valueStyle={{ fontSize: '16px' }}
                    />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic
                      title={t('pq.correct_answers')}
                      value={activity.correct_answers}
                      valueStyle={{ fontSize: '16px', color: '#52c41a' }}
                    />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic
                      title={t('pq.ranking_position')}
                      value={activity.ranking_position !== null ? `#${activity.ranking_position}` : 'N/A'}
                      valueStyle={{ fontSize: '16px', color: '#faad14' }}
                    />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic
                      title={t('pq.total_participants')}
                      value={activity.total_participants}
                      valueStyle={{ fontSize: '16px' }}
                    />
                  </Col>
                </Row>
              </Card>
            ))}
          </div>
        </>
      )}

      {/* No Data After Query */}
      {!loading && data && (!data.activities || data.activities.length === 0) && (
        <Alert message={t('pq.no_data')} type="info" showIcon />
      )}
    </div>
  );
}
