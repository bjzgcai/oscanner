'use client';

import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Alert, Button, Empty, Spin, message } from 'antd';
import { DownloadOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { validationApi } from '../../utils/validationApi';
import TestResultCard from './TestResultCard';
import { ValidationRunResult } from './types';
import { useI18n } from '../I18nContext';

interface ValidationResultsProps {
  runId: string | null;
  onBackToHistory?: () => void;
}

export default function ValidationResults({ runId, onBackToHistory }: ValidationResultsProps) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidationRunResult | null>(null);

  useEffect(() => {
    if (!runId) {
      setResult(null);
      return;
    }

    const loadRunDetails = async () => {
      setLoading(true);
      try {
        const response = await validationApi.getRun(runId);
        if (response.success) {
          setResult(response.run);
        }
      } catch (err) {
        message.error(t('validation.results.load_error'));
        console.error('Failed to load run details:', err);
      } finally {
        setLoading(false);
      }
    };

    loadRunDetails();
  }, [runId, t]);

  const handleDownload = () => {
    if (!result) return;

    const dataStr = JSON.stringify(result, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `validation_${result.run_id}.json`;
    link.click();
    URL.revokeObjectURL(url);
    message.success(t('validation.results.download_success'));
  };

  if (!runId) {
    return (
      <Card>
        <Empty
          description={t('validation.results.no_run_selected')}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <p style={{ color: '#666' }}>{t('validation.results.no_run_selected_desc')}</p>
        </Empty>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>{t('validation.results.loading')}</p>
        </div>
      </Card>
    );
  }

  if (!result) {
    return (
      <Card>
        <Empty description={t('validation.results.not_found')} />
      </Card>
    );
  }

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  return (
    <div>
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>{t('validation.results.title')}: {result.run_id}</span>
            <div>
              {onBackToHistory && (
                <Button
                  icon={<ArrowLeftOutlined />}
                  onClick={onBackToHistory}
                  style={{ marginRight: 8 }}
                >
                  {t('validation.results.back_to_history')}
                </Button>
              )}
              <Button icon={<DownloadOutlined />} onClick={handleDownload}>
                {t('validation.results.download')}
              </Button>
            </div>
          </div>
        }
        style={{ marginBottom: 24 }}
      >
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title={t('validation.results.overall_score')}
              value={result.overall_score.toFixed(1)}
              suffix="/100"
              valueStyle={{
                color: result.overall_score >= 80 ? '#3f8600' : result.overall_score >= 60 ? '#faad14' : '#cf1322',
              }}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title={t('validation.results.tests_passed')}
              value={result.validation_results.filter((r) => r.passed).length}
              suffix={`/ ${result.validation_results.length}`}
              valueStyle={{ color: result.overall_passed ? '#3f8600' : '#cf1322' }}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title={t('validation.results.repos_evaluated')}
              value={result.evaluation_count}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title={t('validation.results.duration')}
              value={formatDuration(result.duration_seconds)}
            />
          </Col>
        </Row>

        <Alert
          message={
            result.overall_passed
              ? t('validation.results.all_passed')
              : t('validation.results.some_failed')
          }
          description={
            <div>
              <p>
                {t('validation.results.timestamp')}: {formatTimestamp(result.timestamp)}
              </p>
              <p>
                {t('validation.results.dataset_total')}: {result.dataset_stats.total} {t('validation.results.repos')}
              </p>
            </div>
          }
          type={result.overall_passed ? 'success' : 'warning'}
          showIcon
        />
      </Card>

      <div>
        <h3>{t('validation.results.test_details')}</h3>
        {result.validation_results.map((testResult, idx) => (
          <TestResultCard
            key={idx}
            result={testResult}
            defaultExpanded={!testResult.passed}
          />
        ))}
      </div>
    </div>
  );
}
