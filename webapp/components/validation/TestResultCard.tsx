'use client';

import React from 'react';
import { Card, Progress, Tag, Collapse, Alert, Descriptions } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { ValidationResult } from './types';
import { useI18n } from '../I18nContext';

const { Panel } = Collapse;

interface TestResultCardProps {
  result: ValidationResult;
  defaultExpanded?: boolean;
}

export default function TestResultCard({ result, defaultExpanded = false }: TestResultCardProps) {
  const { t } = useI18n();

  const getStatusColor = (passed: boolean): string => {
    return passed ? '#52c41a' : '#ff4d4f';
  };

  const getScoreColor = (score: number): string => {
    if (score >= 80) return '#52c41a'; // green
    if (score >= 60) return '#faad14'; // yellow
    return '#ff4d4f'; // red
  };

  const renderDetails = () => {
    const { details } = result;
    if (!details || Object.keys(details).length === 0) {
      return <p>{t('validation.results.no_details')}</p>;
    }

    const entries = Object.entries(details);
    const items = entries.map(([key, value]) => {
      const label = key
        .split('_')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');

      let content: React.ReactNode;
      if (typeof value === 'object' && value !== null) {
        content = <pre style={{ fontSize: 12 }}>{JSON.stringify(value, null, 2)}</pre>;
      } else if (typeof value === 'number') {
        content = value.toFixed(2);
      } else {
        content = String(value);
      }

      return { key, label, children: content };
    });

    return <Descriptions column={1} size="small" items={items} />;
  };

  return (
    <Card
      className={`test-result-card ${result.passed ? 'passed' : 'failed'}`}
      style={{
        borderLeft: `4px solid ${getStatusColor(result.passed)}`,
        marginBottom: 16,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, marginBottom: 8 }}>
            {result.test_name}
            <Tag
              icon={result.passed ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
              color={result.passed ? 'success' : 'error'}
              style={{ marginLeft: 12 }}
            >
              {result.passed ? t('validation.status.passed') : t('validation.status.failed')}
            </Tag>
          </h3>
          {result.test_name.toLowerCase().includes('consistency') && (
            <p style={{ margin: 0, fontSize: 13, color: '#666' }}>
              {t('validation.test.consistency.desc')}
            </p>
          )}
          {result.test_name.toLowerCase().includes('correlation') && (
            <p style={{ margin: 0, fontSize: 13, color: '#666' }}>
              {t('validation.test.correlation.desc')}
            </p>
          )}
          {result.test_name.toLowerCase().includes('dimension') && (
            <p style={{ margin: 0, fontSize: 13, color: '#666' }}>
              {t('validation.test.dimension.desc')}
            </p>
          )}
          {result.test_name.toLowerCase().includes('temporal') && (
            <p style={{ margin: 0, fontSize: 13, color: '#666' }}>
              {t('validation.test.temporal.desc')}
            </p>
          )}
          {result.test_name.toLowerCase().includes('ordering') && (
            <p style={{ margin: 0, fontSize: 13, color: '#666' }}>
              {t('validation.test.ordering.desc')}
            </p>
          )}
        </div>
        <div style={{ textAlign: 'center', minWidth: 100 }}>
          <Progress
            type="circle"
            percent={result.score}
            format={(percent) => `${percent?.toFixed(0)}`}
            strokeColor={getScoreColor(result.score)}
            size={80}
          />
        </div>
      </div>

      {(result.errors.length > 0 || result.warnings.length > 0) && (
        <div style={{ marginTop: 16 }}>
          {result.errors.map((error, idx) => (
            <Alert
              key={`error-${idx}`}
              message={error}
              type="error"
              showIcon
              style={{ marginBottom: 8 }}
            />
          ))}
          {result.warnings.map((warning, idx) => (
            <Alert
              key={`warning-${idx}`}
              message={warning}
              type="warning"
              showIcon
              style={{ marginBottom: 8 }}
            />
          ))}
        </div>
      )}

      <Collapse
        defaultActiveKey={defaultExpanded ? ['1'] : []}
        style={{ marginTop: 16 }}
        items={[
          {
            key: '1',
            label: t('validation.results.test_details'),
            children: renderDetails(),
          },
        ]}
      />
    </Card>
  );
}
