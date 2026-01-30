'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Tabs, Card } from 'antd';
import {
  DatabaseOutlined,
  PlayCircleOutlined,
  HistoryOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import DatasetOverview from './DatasetOverview';
import ValidationRunner from './ValidationRunner';
import ValidationHistory from './ValidationHistory';
import ValidationResults from './ValidationResults';
import { ViewMode, LogEntry, TestRepository } from './types';
import { useI18n } from '../I18nContext';

export default function ValidationDashboard() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<ViewMode>('dataset');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const appendLog = (entry: LogEntry) => {
    setLogs((prev) => {
      const newLogs = [...prev, entry];
      if (newLogs.length > 200) {
        return newLogs.slice(-200);
      }
      return newLogs;
    });
  };

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (showLogs) {
      scrollToBottom();
    }
  }, [logs, showLogs]);

  const handleValidationComplete = (runId: string) => {
    setSelectedRunId(runId);
    setActiveTab('results');
    setHistoryRefresh((prev) => prev + 1);
  };

  const handleViewRun = (runId: string) => {
    setSelectedRunId(runId);
    setActiveTab('results');
  };

  const handleBackToHistory = () => {
    setActiveTab('history');
    setSelectedRunId(null);
  };

  const handleViewEvaluation = (repo: TestRepository) => {
    console.log('View evaluation for:', repo);
    // This could open a modal or navigate to a detail view
    // For now, we'll just log it
  };

  const formatTime = (timestamp: number): string => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const getLogColor = (type: string): string => {
    switch (type) {
      case 'error':
        return '#ff4d4f';
      case 'success':
        return '#52c41a';
      case 'warning':
        return '#faad14';
      default:
        return '#000';
    }
  };

  const tabItems = [
    {
      key: 'dataset',
      label: (
        <span>
          <DatabaseOutlined />
          {t('validation.nav.dataset')}
        </span>
      ),
      children: <DatasetOverview onViewEvaluation={handleViewEvaluation} />,
    },
    {
      key: 'run',
      label: (
        <span>
          <PlayCircleOutlined />
          {t('validation.nav.run')}
        </span>
      ),
      children: (
        <ValidationRunner
          onValidationComplete={handleValidationComplete}
          onLog={appendLog}
        />
      ),
    },
    {
      key: 'history',
      label: (
        <span>
          <HistoryOutlined />
          {t('validation.nav.history')}
        </span>
      ),
      children: (
        <ValidationHistory onViewRun={handleViewRun} refreshTrigger={historyRefresh} />
      ),
    },
    {
      key: 'results',
      label: (
        <span>
          <BarChartOutlined />
          {t('validation.nav.results')}
        </span>
      ),
      children: (
        <ValidationResults runId={selectedRunId} onBackToHistory={handleBackToHistory} />
      ),
    },
  ];

  return (
    <div className="validation-container">
      <h1 style={{ marginBottom: 24 }}>{t('validation.title')}</h1>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as ViewMode)}
        items={tabItems}
        size="large"
      />

      {logs.length > 0 && (
        <Card
          title={t('validation.logs.title')}
          style={{ marginTop: 24 }}
          extra={
            <a onClick={() => setShowLogs(!showLogs)}>
              {showLogs ? t('validation.logs.hide') : t('validation.logs.show')}
            </a>
          }
        >
          {showLogs && (
            <div
              style={{
                maxHeight: 300,
                overflow: 'auto',
                fontFamily: 'monospace',
                fontSize: 13,
                backgroundColor: '#f5f5f5',
                padding: 16,
                borderRadius: 4,
              }}
            >
              {logs.map((log, idx) => (
                <div key={idx} style={{ marginBottom: 4 }}>
                  <span style={{ color: '#999' }}>[{formatTime(log.timestamp)}]</span>{' '}
                  <span style={{ color: getLogColor(log.type) }}>{log.message}</span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
          {!showLogs && logs.length > 0 && (
            <div style={{ fontFamily: 'monospace', fontSize: 13, color: '#666' }}>
              {logs[logs.length - 1].message}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
