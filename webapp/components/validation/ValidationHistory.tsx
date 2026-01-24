'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Card, Table, Tag, Button, Empty, message } from 'antd';
import type { TableColumnsType } from 'antd';
import { EyeOutlined, ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { validationApi } from '../../utils/validationApi';
import { ValidationRunSummary } from './types';
import { useI18n } from '../I18nContext';

interface ValidationHistoryProps {
  onViewRun?: (runId: string) => void;
  refreshTrigger?: number;
}

export default function ValidationHistory({ onViewRun, refreshTrigger }: ValidationHistoryProps) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [runs, setRuns] = useState<ValidationRunSummary[]>([]);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const result = await validationApi.listRuns();
      if (result.success) {
        setRuns(result.runs);
      }
    } catch (err) {
      message.error(t('validation.history.load_error'));
      console.error('Failed to load validation runs:', err);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns, refreshTrigger]);

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const formatDuration = (seconds?: number): string => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const columns: TableColumnsType<ValidationRunSummary> = [
    {
      title: t('validation.history.run_id'),
      dataIndex: 'run_id',
      key: 'run_id',
      width: 200,
      render: (runId: string) => <code>{runId}</code>,
    },
    {
      title: t('validation.history.timestamp'),
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 200,
      render: (timestamp: string) => formatTimestamp(timestamp),
    },
    {
      title: t('validation.history.score'),
      dataIndex: 'overall_score',
      key: 'overall_score',
      width: 120,
      render: (score: number) => {
        if (score === undefined || score === null) {
          return <Tag color="default">N/A</Tag>;
        }
        let color = 'default';
        if (score >= 80) color = 'success';
        else if (score >= 60) color = 'warning';
        else color = 'error';
        return <Tag color={color}>{score.toFixed(1)}/100</Tag>;
      },
      sorter: (a, b) => (a.overall_score || 0) - (b.overall_score || 0),
    },
    {
      title: t('validation.history.status'),
      dataIndex: 'overall_passed',
      key: 'overall_passed',
      width: 120,
      render: (passed: boolean) => (
        <Tag
          icon={passed ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          color={passed ? 'success' : 'error'}
        >
          {passed ? t('validation.history.passed') : t('validation.history.failed')}
        </Tag>
      ),
      filters: [
        { text: t('validation.history.passed'), value: true },
        { text: t('validation.history.failed'), value: false },
      ],
      onFilter: (value, record) => record.overall_passed === value,
    },
    {
      title: t('validation.history.duration'),
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 100,
      render: (seconds?: number) => formatDuration(seconds),
    },
    {
      title: t('validation.history.actions'),
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Button
          type="primary"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => onViewRun?.(record.run_id)}
        >
          {t('validation.history.view_details')}
        </Button>
      ),
    },
  ];

  return (
    <Card
      title={t('validation.history.title')}
      extra={
        <Button icon={<ReloadOutlined />} onClick={loadRuns} loading={loading}>
          {t('validation.history.refresh')}
        </Button>
      }
    >
      {runs.length === 0 && !loading ? (
        <Empty
          description={t('validation.history.no_runs')}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <p style={{ color: '#666' }}>{t('validation.history.no_runs_desc')}</p>
        </Empty>
      ) : (
        <Table
          columns={columns}
          dataSource={runs}
          loading={loading}
          rowKey={(record) => record.run_id}
          pagination={{
            pageSize: 10,
            showSizeChanger: false,
            showTotal: (total) => `${total} ${t('validation.history.total_runs')}`,
          }}
        />
      )}
    </Card>
  );
}
