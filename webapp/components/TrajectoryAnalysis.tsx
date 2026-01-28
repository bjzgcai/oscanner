'use client';

import { useState, useEffect, useMemo } from 'react';
import { Button, Card, message, Modal, Space, Empty, Alert, Collapse, Tag, Descriptions, AutoComplete } from 'antd';
import { RiseOutlined, LoadingOutlined, CheckCircleOutlined, GithubOutlined, UserOutlined } from '@ant-design/icons';
import { useUserSettings } from './UserSettingsContext';
import { useAppSettings } from './AppSettingsContext';
import { useI18n } from './I18nContext';
import TrajectoryCharts from './TrajectoryCharts';
import GrowthReport from './GrowthReport';
import { getApiBaseUrl } from '@/utils/apiBase';
import { TrajectoryCache, TrajectoryResponse, TrajectoryCheckpoint } from '@/types/trajectory';

export default function TrajectoryAnalysis() {
  const [loading, setLoading] = useState(false);
  const [trajectory, setTrajectory] = useState<TrajectoryCache | null>(null);
  const [repoUrl, setRepoUrl] = useState('');
  const [authorName, setAuthorName] = useState('');
  const [isRepoUrlValid, setIsRepoUrlValid] = useState(false);
  const [isAuthorNameValid, setIsAuthorNameValid] = useState(false);
  const { defaultUsername, repoUrls, usernameGroups } = useUserSettings();
  const { model, pluginId, useCache, language } = useAppSettings();
  const { t } = useI18n();

  // Validate repo URL (GitHub or Gitee format)
  const validateRepoUrl = (url: string): boolean => {
    if (!url.trim()) return false;

    const githubPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    const giteePattern = /^https?:\/\/(www\.)?gitee\.com\/[\w-]+\/[\w.-]+\/?$/;

    return githubPattern.test(url.trim()) || giteePattern.test(url.trim());
  };

  // Validate author name (not empty)
  const validateAuthorName = (name: string): boolean => {
    return name.trim().length > 0;
  };

  // Update validation state when inputs change
  useEffect(() => {
    setIsRepoUrlValid(validateRepoUrl(repoUrl));
  }, [repoUrl]);

  useEffect(() => {
    setIsAuthorNameValid(validateAuthorName(authorName));
  }, [authorName]);

  // Prepare autocomplete options for repo URLs
  const repoUrlOptions = useMemo(() => {
    if (!repoUrls || repoUrls.length === 0) return [];
    return repoUrls.map((url) => ({ value: url }));
  }, [repoUrls]);

  // Prepare autocomplete options for author names
  const authorNameOptions = useMemo(() => {
    const names = new Set<string>();

    if (defaultUsername) {
      names.add(defaultUsername);
    }

    if (usernameGroups) {
      usernameGroups.split(',').forEach((name) => {
        const trimmed = name.trim();
        if (trimmed) names.add(trimmed);
      });
    }

    return Array.from(names).map((name) => ({ value: name }));
  }, [defaultUsername, usernameGroups]);

  // Check if both inputs are valid
  const isFormValid = isRepoUrlValid && isAuthorNameValid;

  const analyzeTrajectory = async () => {
    if (!isFormValid) {
      message.error('Please provide valid repo URL and author name');
      return;
    }

    setLoading(true);

    try {
      // Use input values instead of settings
      const aliases = [authorName.trim()];

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
          username: authorName.trim(),
          repo_urls: [repoUrl.trim()],
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

  // Helper function to get dimension label
  const getDimensionLabel = (dimensionKey: string, pluginId: string): string => {
    const pluginSpecificKey = `plugin.${pluginId}.dim.${dimensionKey}`;
    const translated = t(pluginSpecificKey);
    if (translated === pluginSpecificKey) {
      return t(`dimensions.${dimensionKey}`) || dimensionKey;
    }
    return translated;
  };

  // Render checkpoint details in collapse panel
  const renderCheckpointDetails = (checkpoint: TrajectoryCheckpoint) => {
    const { evaluation } = checkpoint;
    const scores = evaluation.scores;

    // Get all dimension keys (excluding reasoning)
    const dimensionKeys = Object.keys(scores).filter(
      (key) => key !== 'reasoning' && scores[key] !== null && scores[key] !== undefined
    );

    // Get score color based on value
    const getScoreColor = (score: number) => {
      if (score >= 80) return 'green';
      if (score >= 60) return 'blue';
      if (score >= 40) return 'orange';
      return 'red';
    };

    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Evaluation Scores */}
        <div>
          <h4 style={{ marginBottom: '12px' }}>Evaluation Scores</h4>
          <Descriptions bordered column={2} size="small">
            {dimensionKeys.map((key) => {
              const score = scores[key as keyof typeof scores] as number;
              return (
                <Descriptions.Item
                  key={key}
                  label={getDimensionLabel(key, evaluation.plugin)}
                >
                  <Tag color={getScoreColor(score)} style={{ fontSize: '14px', padding: '4px 12px' }}>
                    {score}/100
                  </Tag>
                </Descriptions.Item>
              );
            })}
          </Descriptions>
        </div>

        {/* Reasoning */}
        {scores.reasoning && (
          <div>
            <h4 style={{ marginBottom: '12px' }}>Evaluation Reasoning</h4>
            <Card size="small" style={{ background: '#f5f5f5' }}>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                {scores.reasoning}
              </div>
            </Card>
          </div>
        )}

        {/* Additional Metadata */}
        <div>
          <h4 style={{ marginBottom: '12px' }}>Checkpoint Metadata</h4>
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="Checkpoint ID">
              #{checkpoint.checkpoint_id}
            </Descriptions.Item>
            <Descriptions.Item label="Created At">
              {new Date(checkpoint.created_at).toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="Commits Analyzed">
              {checkpoint.commits_range.commit_count} commits
            </Descriptions.Item>
            <Descriptions.Item label="Total Additions">
              +{evaluation.commits_summary.total_additions} lines
            </Descriptions.Item>
            <Descriptions.Item label="Total Deletions">
              -{evaluation.commits_summary.total_deletions} lines
            </Descriptions.Item>
            <Descriptions.Item label="Files Changed">
              {evaluation.commits_summary.files_changed} files
            </Descriptions.Item>
            {evaluation.commits_summary.languages.length > 0 && (
              <Descriptions.Item label="Languages">
                {evaluation.commits_summary.languages.join(', ')}
              </Descriptions.Item>
            )}
          </Descriptions>
        </div>
      </Space>
    );
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <h2>
              <RiseOutlined /> {t('trajectory.title')}
            </h2>
          </div>

          {/* Input fields */}
          <Card type="inner" title="Analysis Configuration" style={{ marginBottom: '16px' }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                  <GithubOutlined /> Repository URL
                </label>
                <AutoComplete
                  size="large"
                  placeholder="https://github.com/owner/repo or https://gitee.com/owner/repo"
                  value={repoUrl}
                  onChange={setRepoUrl}
                  options={repoUrlOptions}
                  status={repoUrl && !isRepoUrlValid ? 'error' : undefined}
                  disabled={loading}
                  style={{ width: '100%' }}
                  filterOption={(inputValue, option) =>
                    option?.value.toLowerCase().includes(inputValue.toLowerCase())
                  }
                />
                {repoUrl && !isRepoUrlValid && (
                  <div style={{ color: '#ff4d4f', fontSize: '12px', marginTop: '4px' }}>
                    Please enter a valid GitHub or Gitee repository URL
                  </div>
                )}
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                  <UserOutlined /> Author Name
                </label>
                <AutoComplete
                  size="large"
                  placeholder="Enter author username"
                  value={authorName}
                  onChange={setAuthorName}
                  options={authorNameOptions}
                  status={authorName && !isAuthorNameValid ? 'error' : undefined}
                  disabled={loading}
                  style={{ width: '100%' }}
                  filterOption={(inputValue, option) =>
                    option?.value.toLowerCase().includes(inputValue.toLowerCase())
                  }
                />
                {authorName && !isAuthorNameValid && (
                  <div style={{ color: '#ff4d4f', fontSize: '12px', marginTop: '4px' }}>
                    Author name cannot be empty
                  </div>
                )}
              </div>

              <Button
                type="primary"
                size="large"
                icon={loading ? <LoadingOutlined /> : <RiseOutlined />}
                onClick={analyzeTrajectory}
                loading={loading}
                disabled={!isFormValid || loading}
                block
              >
                {t('trajectory.analyze_button')}
              </Button>
            </Space>
          </Card>

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

              {/* Checkpoint Details Collapse */}
              <Card title={<span><CheckCircleOutlined /> Checkpoint Details</span>}>
                <Collapse
                  defaultActiveKey={[trajectory.checkpoints.length - 1]}
                  items={trajectory.checkpoints.map((checkpoint, index) => ({
                    key: index,
                    label: (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                        <span>
                          <strong>Checkpoint #{checkpoint.checkpoint_id}</strong>
                          {index === trajectory.checkpoints.length - 1 && (
                            <Tag color="blue" style={{ marginLeft: '8px' }}>Latest</Tag>
                          )}
                        </span>
                        <span style={{ color: '#888', fontSize: '12px' }}>
                          {checkpoint.commits_range.period_end
                            ? new Date(checkpoint.commits_range.period_end).toLocaleDateString()
                            : new Date(checkpoint.created_at).toLocaleDateString()
                          } - {checkpoint.commits_range.commit_count} commits
                        </span>
                      </div>
                    ),
                    children: renderCheckpointDetails(checkpoint),
                  }))}
                />
              </Card>

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
