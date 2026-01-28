'use client';

import { useState } from 'react';
import { Button, Card, message, Modal, Space, Empty, Alert } from 'antd';
import { RiseOutlined, LoadingOutlined } from '@ant-design/icons';
import { useUserSettings } from './UserSettingsContext';
import { useAppSettings } from './AppSettingsContext';
import { useI18n } from './I18nContext';
import TrajectoryCharts from './TrajectoryCharts';
import GrowthReport from './GrowthReport';
import { getApiBaseUrl } from '@/utils/apiBase';
import { TrajectoryCache, TrajectoryResponse } from '@/types/trajectory';

export default function TrajectoryAnalysis() {
  const [loading, setLoading] = useState(false);
  const [trajectory, setTrajectory] = useState<TrajectoryCache | null>(null);
  const { defaultUsername, repoUrls, usernameGroups } = useUserSettings();
  const { model, pluginId, useCache, language } = useAppSettings();
  const { t } = useI18n();

  const analyzeTrajectory = async () => {
    if (!defaultUsername) {
      message.error(t('trajectory.no_username'));
      return;
    }

    if (!repoUrls || repoUrls.length === 0) {
      message.error(t('trajectory.no_repos'));
      return;
    }

    setLoading(true);

    try {
      // Parse aliases from usernameGroups
      const aliases = usernameGroups
        ? usernameGroups.split(',').map((s) => s.trim()).filter(Boolean)
        : [defaultUsername];

      const apiBase = getApiBaseUrl();
      const url = `${apiBase}/api/trajectory/analyze?plugin=${encodeURIComponent(
        pluginId
      )}&model=${encodeURIComponent(model)}&language=${encodeURIComponent(
        language
      )}&use_cache=${useCache}`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: defaultUsername,
          repo_urls: repoUrls,
          aliases: aliases,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Analysis failed');
      }

      const data: TrajectoryResponse = await response.json();

      if (data.success && data.trajectory) {
        setTrajectory(data.trajectory);

        if (data.new_checkpoint_created) {
          message.success(t('trajectory.new_checkpoint'));
        } else {
          message.info(
            t('trajectory.insufficient_commits', {
              pending: data.commits_pending || 0,
            })
          );
        }
      } else {
        message.error(data.message || t('trajectory.analysis_failed'));
      }
    } catch (error: any) {
      console.error('Trajectory analysis error:', error);
      message.error(error.message || t('trajectory.analysis_failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>
              <RiseOutlined /> {t('trajectory.title')}
            </h2>
            <Button
              type="primary"
              size="large"
              icon={loading ? <LoadingOutlined /> : <RiseOutlined />}
              onClick={analyzeTrajectory}
              loading={loading}
            >
              {t('trajectory.analyze_button')}
            </Button>
          </div>

          {!trajectory && !loading && (
            <Empty
              description={t('trajectory.no_data')}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}

          {trajectory && trajectory.total_checkpoints === 0 && (
            <Alert
              message={t('trajectory.no_checkpoints')}
              type="info"
              showIcon
            />
          )}

          {trajectory && trajectory.total_checkpoints > 0 && (
            <>
              <div
                style={{
                  padding: '16px',
                  background: '#f5f5f5',
                  borderRadius: '8px',
                }}
              >
                <Space direction="vertical" size="small">
                  <div>
                    <strong>{t('trajectory.username')}:</strong> {trajectory.username}
                  </div>
                  <div>
                    <strong>{t('trajectory.total_checkpoints')}:</strong>{' '}
                    {trajectory.total_checkpoints}
                  </div>
                  <div>
                    <strong>{t('trajectory.repos_tracked')}:</strong>{' '}
                    {trajectory.repo_urls.length}
                  </div>
                  {trajectory.last_synced_at && (
                    <div>
                      <strong>{t('trajectory.last_synced')}:</strong>{' '}
                      {new Date(trajectory.last_synced_at).toLocaleString()}
                    </div>
                  )}
                  {trajectory.accumulation_state && trajectory.accumulation_state.accumulated_commits.length > 0 && (
                    <div style={{ marginTop: '8px', padding: '8px', background: '#fff3cd', borderRadius: '4px' }}>
                      <strong>📊 Accumulation Progress:</strong>{' '}
                      {trajectory.accumulation_state.accumulated_commits.length} commits accumulated
                      {' '}
                      (Need {10 - trajectory.accumulation_state.accumulated_commits.length} more for next checkpoint)
                    </div>
                  )}
                </Space>
              </div>

              <TrajectoryCharts trajectory={trajectory} />
              <GrowthReport trajectory={trajectory} />
            </>
          )}
        </Space>
      </Card>

      <Modal
        open={loading}
        footer={null}
        closable={false}
        centered
        maskClosable={false}
      >
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <LoadingOutlined style={{ fontSize: 48, color: '#1890ff' }} />
          <h3 style={{ marginTop: '16px' }}>{t('trajectory.analyzing')}</h3>
          <p>{t('trajectory.please_wait')}</p>
        </div>
      </Modal>
    </div>
  );
}
