'use client';

import React, { useState } from 'react';
import { Card, Form, Select, Switch, Button, Descriptions, Alert, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { validationApi } from '../../utils/validationApi';
import { useAppSettings } from '../AppSettingsContext';
import { useI18n } from '../I18nContext';
import { LogEntry } from './types';

interface ValidationRunnerProps {
  onValidationComplete?: (runId: string) => void;
  onLog?: (entry: LogEntry) => void;
}

export default function ValidationRunner({
  onValidationComplete,
  onLog,
}: ValidationRunnerProps) {
  const { t } = useI18n();
  const { model, pluginId, useCache } = useAppSettings();
  const [isRunning, setIsRunning] = useState(false);
  const [subset, setSubset] = useState<string | undefined>(undefined);
  const [quickMode, setQuickMode] = useState(true);

  const appendLog = (msg: string, type: 'info' | 'error' | 'success' | 'warning' = 'info') => {
    onLog?.({
      message: msg,
      type,
      timestamp: Date.now(),
    });
  };

  const handleRunValidation = async () => {
    setIsRunning(true);
    appendLog(t('validation.log.starting'), 'info');

    try {
      const config = {
        subset,
        quick_mode: quickMode,
        plugin_id: pluginId,
        model,
      };

      appendLog(
        `${t('validation.run.config')}: ${JSON.stringify(
          {
            subset: subset || t('validation.run.subset.all'),
            quickMode,
            plugin: pluginId,
            model,
          },
          null,
          2
        )}`,
        'info'
      );

      const result = await validationApi.runValidation(config);

      if (result.success) {
        const score = result.overall_score || result.result?.overall_score || 0;
        const runId = result.run_id || result.result?.run_id || '';

        appendLog(
          t('validation.log.complete', { score: score.toFixed(1) }),
          'success'
        );
        message.success(t('validation.run.complete'));

        if (runId) {
          onValidationComplete?.(runId);
        }
      } else {
        throw new Error(result.message || t('validation.run.failed'));
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      appendLog(t('validation.log.error', { error: errorMessage }), 'error');
      message.error(t('validation.run.error'));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div>
      <Card title={t('validation.run.title')} style={{ marginBottom: 16 }}>
        <Alert
          message={t('validation.run.info')}
          description={t('validation.run.info_desc')}
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />

        <Form layout="vertical">
          <Form.Item label={t('validation.run.subset.label')}>
            <Select
              style={{ width: '100%' }}
              placeholder={t('validation.run.subset.placeholder')}
              allowClear
              value={subset}
              onChange={setSubset}
              disabled={isRunning}
            >
              <Select.Option value={undefined}>{t('validation.run.subset.all')}</Select.Option>
              <Select.Option value="ground_truth">
                {t('validation.category.ground_truth')}
              </Select.Option>
              <Select.Option value="famous_developer">
                {t('validation.category.famous_developer')}
              </Select.Option>
              <Select.Option value="dimension_specialist">
                {t('validation.category.dimension_specialist')}
              </Select.Option>
              <Select.Option value="rising_star">
                {t('validation.category.rising_star')}
              </Select.Option>
              <Select.Option value="temporal_evolution">
                {t('validation.category.temporal_evolution')}
              </Select.Option>
              <Select.Option value="edge_case">
                {t('validation.category.edge_case')}
              </Select.Option>
              <Select.Option value="corporate_team">
                {t('validation.category.corporate_team')}
              </Select.Option>
              <Select.Option value="domain_specialist">
                {t('validation.category.domain_specialist')}
              </Select.Option>
              <Select.Option value="international">
                {t('validation.category.international')}
              </Select.Option>
              <Select.Option value="comparison_pair">
                {t('validation.category.comparison_pair')}
              </Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label={t('validation.run.quick_mode.label')} tooltip={t('validation.run.quick_mode.tooltip')}>
            <Switch checked={quickMode} onChange={setQuickMode} disabled={isRunning} />
            <span style={{ marginLeft: 12, color: '#666' }}>
              {quickMode
                ? t('validation.run.quick_mode.enabled')
                : t('validation.run.quick_mode.disabled')}
            </span>
          </Form.Item>
        </Form>

        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={handleRunValidation}
          loading={isRunning}
          disabled={isRunning}
          block
        >
          {isRunning ? t('validation.run.running') : t('validation.run.start')}
        </Button>
      </Card>

      <Card title={t('validation.run.current_settings')}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label={t('validation.settings.model')}>{model}</Descriptions.Item>
          <Descriptions.Item label={t('validation.settings.plugin')}>{pluginId}</Descriptions.Item>
          <Descriptions.Item label={t('validation.settings.cache')}>
            {useCache ? t('validation.settings.enabled') : t('validation.settings.disabled')}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
