'use client';

import React, { useEffect, useState } from 'react';
import { Card, Form, Select, Switch, Button, Descriptions, Alert, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { validationApi } from '../../utils/validationApi';
import { useAppSettings } from '../AppSettingsContext';
import { useI18n } from '../I18nContext';
import { LogEntry, ValidationRunResult } from './types';

interface ValidationRunnerProps {
  onValidationComplete?: (result: ValidationRunResult) => void;
  onLog?: (entry: LogEntry) => void;
}

export default function ValidationRunner({
  onValidationComplete,
  onLog,
}: ValidationRunnerProps) {
  const { t } = useI18n();
  const { model, pluginId } = useAppSettings();
  const [isRunning, setIsRunning] = useState(false);
  const [subset, setSubset] = useState<string | undefined>(undefined);
  const [categories, setCategories] = useState<string[]>([]);
  const [quickMode, setQuickMode] = useState(true);

  useEffect(() => {
    let mounted = true;

    validationApi.getDatasetInfo()
      .then((result) => {
        if (mounted && result.success) {
          setCategories(result.categories || []);
        }
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, []);

  const appendLog = (msg: string, type: 'info' | 'error' | 'success' | 'warning' = 'info') => {
    onLog?.({
      message: msg,
      type,
      timestamp: Date.now(),
    });
  };

  const categoryLabel = (category: string) => {
    const translated = t(`validation.category.${category}`);
    if (translated !== `validation.category.${category}`) return translated;
    return category
      .split(/[-_]/)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
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
        const validationResult = result.result;

        appendLog(
          t('validation.log.complete', { score: score.toFixed(1) }),
          'success'
        );
        message.success(t('validation.run.complete'));

        if (validationResult) {
          onValidationComplete?.(validationResult);
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
          title={t('validation.run.info')}
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
              {categories.map((category) => (
                <Select.Option key={category} value={category}>
                  {categoryLabel(category)}
                </Select.Option>
              ))}
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
        </Descriptions>
      </Card>
    </div>
  );
}
