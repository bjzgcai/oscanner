'use client';

import { useState, useEffect, useMemo } from 'react';
import { Button, Card, message, Modal, Space, Empty, Alert, Collapse, Tag, Descriptions, Input, Switch, Tooltip, Dropdown, Table, Radio } from 'antd';
import { RiseOutlined, LoadingOutlined, CheckCircleOutlined, GithubOutlined, UserOutlined, SettingOutlined, ApiOutlined } from '@ant-design/icons';
import { useUserSettings } from './UserSettingsContext';
import { useAppSettings } from './AppSettingsContext';
import { useI18n } from './I18nContext';
import TrajectoryCharts from './TrajectoryCharts';
import GrowthReport from './GrowthReport';
import LlmConfigModal from './LlmConfigModal';
import { getApiBaseUrl } from '@/utils/apiBase';
import { TrajectoryCache, TrajectoryResponse, TrajectoryCheckpoint } from '@/types/trajectory';
import { LOCALES } from '../i18n';

export default function TrajectoryAnalysis() {
  const [loading, setLoading] = useState(false);
  const [trajectory, setTrajectory] = useState<TrajectoryCache | null>(null);
  const [repoUrl, setRepoUrl] = useState('');
  const [isRepoUrlValid, setIsRepoUrlValid] = useState(false);
  const [authors, setAuthors] = useState<Array<{ author: string; email: string; commits: number }>>([]);
  const [selectedAuthors, setSelectedAuthors] = useState<string[]>([]);
  const [fetchingAuthors, setFetchingAuthors] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { defaultUsername, repoUrls, usernameGroups } = useUserSettings();
  const { model, setModel, pluginId, setPluginId, plugins, useCache, setUseCache, locale, setLocale, setLlmModalOpen } = useAppSettings();
  const { t } = useI18n();

  // Validate repo URL (GitHub or Gitee format)
  const validateRepoUrl = (url: string): boolean => {
    if (!url.trim()) return false;

    const githubPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    const giteePattern = /^https?:\/\/(www\.)?gitee\.com\/[\w-]+\/[\w.-]+\/?$/;

    return githubPattern.test(url.trim()) || giteePattern.test(url.trim());
  };

  // Parse owner and repo from URL
  const parseRepoUrl = (url: string): { owner: string; repo: string; platform: string } | null => {
    if (!url.trim()) return null;

    const githubMatch = url.match(/^https?:\/\/(www\.)?github\.com\/([\w-]+)\/([\w.-]+)\/?$/);
    if (githubMatch) {
      return { owner: githubMatch[2], repo: githubMatch[3], platform: 'github' };
    }

    const giteeMatch = url.match(/^https?:\/\/(www\.)?gitee\.com\/([\w-]+)\/([\w.-]+)\/?$/);
    if (giteeMatch) {
      return { owner: giteeMatch[2], repo: giteeMatch[3], platform: 'gitee' };
    }

    return null;
  };

  // Update validation state when inputs change
  useEffect(() => {
    setIsRepoUrlValid(validateRepoUrl(repoUrl));
  }, [repoUrl]);

  // Fetch authors when repo URL is valid
  useEffect(() => {
    const fetchAuthors = async () => {
      if (!isRepoUrlValid) {
        setAuthors([]);
        setSelectedAuthors([]);
        return;
      }

      const parsed = parseRepoUrl(repoUrl);
      if (!parsed) {
        setAuthors([]);
        setSelectedAuthors([]);
        return;
      }

      setFetchingAuthors(true);
      try {
        const apiBase = getApiBaseUrl();
        const url = `${apiBase}/api/authors/${parsed.owner}/${parsed.repo}?platform=${parsed.platform}`;
        const response = await fetch(url);

        if (!response.ok) {
          throw new Error('Failed to fetch authors');
        }

        const data = await response.json();
        if (data.success && data.data.authors) {
          setAuthors(data.data.authors);
          // Auto-select first author if available
          if (data.data.authors.length > 0) {
            setSelectedAuthors([data.data.authors[0].author]);
          }
        } else {
          setAuthors([]);
          setSelectedAuthors([]);
        }
      } catch (error: any) {
        console.error('Failed to fetch authors:', error);
        message.error('Failed to fetch authors from repository');
        setAuthors([]);
        setSelectedAuthors([]);
      } finally {
        setFetchingAuthors(false);
      }
    };

    fetchAuthors();
  }, [isRepoUrlValid, repoUrl]);

  // Prepare autocomplete options for repo URLs
  const repoUrlOptions = useMemo(() => {
    if (!repoUrls || repoUrls.length === 0) return [];
    return repoUrls.map((url) => ({ value: url }));
  }, [repoUrls]);

  // Check if both inputs are valid
  const isFormValid = isRepoUrlValid && selectedAuthors.length > 0;

  // API docs URL points to backend /docs endpoint
  const apiBase = getApiBaseUrl();
  const apiDocsHref = apiBase ? `${apiBase}/docs` : '/docs';

  // Model items for dropdown
  const modelItems = [
    { key: 'anthropic/claude-sonnet-4.5', label: 'Claude Sonnet 4.5' },
    { key: 'z-ai/glm-4.7', label: 'Z.AI GLM 4.7' },
    { key: 'qwen/qwen3-coder-flash', label: 'Qwen: Qwen3 Coder Flash' },
  ];
  const currentModelLabel = modelItems.find((i) => i.key === model)?.label || model;

  // Plugin items for dropdown
  const pluginItems =
    plugins && plugins.length > 0
      ? plugins.map((p) => ({
          key: p.id,
          label: `${p.name}${p.version ? ` (${p.version})` : ''}`,
        }))
      : [
          { key: 'zgc_simple', label: 'ZGC Simple (Default)' },
          { key: 'zgc_ai_native_2026', label: 'ZGC AI-Native 2026' },
        ];
  const currentPluginLabel = (plugins || []).find((p) => p.id === pluginId)?.name || pluginId || 'zgc_simple';

  const analyzeTrajectory = async () => {
    if (!isFormValid) {
      const errorMsg = 'Please provide valid repo URL and select at least one author';
      setErrorMessage(errorMsg);
      message.error(errorMsg);
      return;
    }

    setLoading(true);
    setErrorMessage(null); // Clear previous errors

    try {
      const apiBase = getApiBaseUrl();
      
      // Check platform token configuration before analysis
      try {
        const checkUrl = `${apiBase}/api/config/check-platform-tokens`;
        const checkResponse = await fetch(checkUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            repo_urls: [repoUrl.trim()],
          }),
        });

        if (!checkResponse.ok) {
          console.warn('[Trajectory] Failed to check platform tokens, proceeding anyway');
          // Continue with analysis even if check fails (non-blocking)
        } else {
          const checkData = await checkResponse.json();
          
          if (!checkData.all_configured) {
            const missing = [];
            if (checkData.missing_tokens.github) {
              missing.push('GitHub Token');
            }
            if (checkData.missing_tokens.gitee) {
              missing.push('Gitee Token');
            }
            
            const errorMsg = `Missing required platform tokens: ${missing.join(', ')}. ` +
              `Please configure them in Settings (LLM Settings) before analyzing. ` +
              `Without tokens, API rate limits are very low (~60 requests/hour for GitHub, lower for Gitee).`;
            setErrorMessage(errorMsg);
            message.error(errorMsg, 8);
            setLoading(false);
            // Optionally open settings modal
            setLlmModalOpen(true);
            return;
          }
        }
      } catch (checkError) {
        console.warn('[Trajectory] Error checking platform tokens:', checkError);
        // Continue with analysis even if check fails (non-blocking)
      }

      // Use selected authors as aliases
      const aliases = selectedAuthors.map(a => a.trim());
      // Create a grouped username from all selected authors (sorted for consistency)
      const groupedUsername = aliases.slice().sort().join(',');

      const url = `${apiBase}/api/trajectory/analyze?plugin=${encodeURIComponent(
        pluginId
      )}&model=${encodeURIComponent(model)}&language=${encodeURIComponent(
        locale
      )}&use_cache=${useCache}`;

      console.log('[Trajectory] Starting analysis:', { url, username: groupedUsername, repoUrl: repoUrl.trim() });

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: groupedUsername,
          repo_urls: [repoUrl.trim()],
          aliases: aliases,
        }),
      });

      console.log('[Trajectory] Response status:', response.status, response.statusText);

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch (e) {
          const text = await response.text();
          if (text) {
            errorMessage = text.substring(0, 200);
          }
        }
        console.error('[Trajectory] API error:', errorMessage);
        throw new Error(errorMessage);
      }

      const data: TrajectoryResponse = await response.json();
      console.log('[Trajectory] Response data:', {
        success: data.success,
        hasTrajectory: !!data.trajectory,
        totalCheckpoints: data.trajectory?.total_checkpoints,
        message: data.message,
        newCheckpointCreated: data.new_checkpoint_created,
        commitsPending: data.commits_pending,
      });

      // Handle successful response
      if (data.success) {
        // Clear any previous errors
        setErrorMessage(null);
        
        // Always set trajectory if it exists (even if empty)
        if (data.trajectory) {
          setTrajectory(data.trajectory);
        } else {
          // If success but no trajectory, clear existing trajectory
          setTrajectory(null);
          console.warn('[Trajectory] Success but no trajectory data returned');
        }

        // Show appropriate message
        if (data.new_checkpoint_created) {
          message.success(t('trajectory.new_checkpoint'));
        } else if (data.commits_pending !== undefined && data.commits_pending > 0) {
          message.info(
            t('trajectory.insufficient_commits', {
              pending: data.commits_pending || 0,
            })
          );
        } else if (data.message) {
          message.info(data.message);
        }

        // If trajectory exists but has no checkpoints, show info
        if (data.trajectory && data.trajectory.total_checkpoints === 0) {
          console.log('[Trajectory] Trajectory loaded but no checkpoints yet');
        }
      } else {
        // Handle failed response
        const errorMsg = data.message || t('trajectory.analysis_failed');
        console.error('[Trajectory] Analysis failed:', errorMsg);
        setErrorMessage(errorMsg);
        message.error(errorMsg);
        setTrajectory(null);
      }
    } catch (error: any) {
      console.error('[Trajectory] Analysis error:', error);
      const errorMsg = error?.message || error?.toString() || t('trajectory.analysis_failed');
      setErrorMessage(errorMsg);
      message.error(errorMsg);
      setTrajectory(null);
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
      <Space orientation="vertical" size="large" style={{ width: '100%' }}>
        {/* Evaluation Scores */}
        <div>
          <h4 style={{ marginBottom: '12px' }}>{t('checkpoint.evaluation_scores')}</h4>
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
            <h4 style={{ marginBottom: '12px' }}>{t('checkpoint.evaluation_reasoning')}</h4>
            <Card size="small" style={{ background: '#f5f5f5' }}>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                {scores.reasoning}
              </div>
            </Card>
          </div>
        )}

        {/* Additional Metadata */}
        <div>
          <h4 style={{ marginBottom: '12px' }}>{t('checkpoint.metadata')}</h4>
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label={t('checkpoint.id')}>
              #{checkpoint.checkpoint_id}
            </Descriptions.Item>
            <Descriptions.Item label={t('checkpoint.created_at')}>
              {new Date(checkpoint.created_at).toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label={t('checkpoint.commits_analyzed')}>
              {checkpoint.commits_range.commit_count} {t('checkpoint.commits')}
            </Descriptions.Item>
            <Descriptions.Item label={t('checkpoint.total_additions')}>
              +{evaluation.commits_summary.total_additions} {t('checkpoint.lines')}
            </Descriptions.Item>
            <Descriptions.Item label={t('checkpoint.total_deletions')}>
              -{evaluation.commits_summary.total_deletions} {t('checkpoint.lines')}
            </Descriptions.Item>
            <Descriptions.Item label={t('checkpoint.files_changed')}>
              {evaluation.commits_summary.files_changed} {t('checkpoint.files')}
            </Descriptions.Item>
            {evaluation.commits_summary.languages.length > 0 && (
              <Descriptions.Item label={t('checkpoint.languages')}>
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
      {/* Configuration Controls Bar */}
      <div style={{
        background: '#F9FAFB',
        borderBottom: '1px solid #E5E7EB',
        padding: '12px 16px',
        marginBottom: '24px',
        borderRadius: '8px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', justifyContent: 'flex-end' }}>
          <Tooltip title={t('nav.cache.tooltip')}>
            <Switch
              checked={useCache}
              onChange={setUseCache}
              checkedChildren={t('nav.cache.on')}
              unCheckedChildren={t('nav.cache.off')}
            />
          </Tooltip>

          <Dropdown
            menu={{
              items: LOCALES.map((l) => ({ key: l.key, label: l.label })),
              selectable: true,
              selectedKeys: [locale],
              onClick: ({ key }) => setLocale(String(key) as typeof locale),
            }}
            trigger={['click']}
          >
            <Button size="middle">
              {t('nav.language')}: {LOCALES.find((l) => l.key === locale)?.label || locale}
            </Button>
          </Dropdown>

          <Dropdown
            menu={{
              items: pluginItems,
              selectable: true,
              selectedKeys: [pluginId || 'zgc_simple'],
              onClick: ({ key }) => setPluginId(String(key)),
            }}
            trigger={['click']}
          >
            <Button size="middle">
              {t('nav.plugin')}: {currentPluginLabel}
            </Button>
          </Dropdown>

          <Dropdown
            menu={{
              items: modelItems,
              selectable: true,
              selectedKeys: [model],
              onClick: ({ key }) => setModel(String(key)),
            }}
            trigger={['click']}
          >
            <Button size="middle">
              {t('nav.model')}: {currentModelLabel}
            </Button>
          </Dropdown>

          <Button
            icon={<SettingOutlined />}
            size="middle"
            onClick={() => setLlmModalOpen(true)}
          >
            {t('nav.llm_settings')}
          </Button>

          <a href={apiDocsHref} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
            <Button icon={<ApiOutlined />} size="middle">
              {t('nav.api')}
            </Button>
          </a>
        </div>
      </div>

      <Card>
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <h2>
              <RiseOutlined /> {t('trajectory.title')}
            </h2>
          </div>

          {/* Input fields */}
          <Card type="inner" title={t('analysis.config')} style={{ marginBottom: '16px' }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                  <GithubOutlined /> {t('analysis.repo_url')}
                </label>
                <Input
                  size="large"
                  placeholder={t('analysis.repo_url.placeholder')}
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  status={repoUrl && !isRepoUrlValid ? 'error' : undefined}
                  disabled={loading}
                  autoComplete="url"
                />
                {repoUrl && !isRepoUrlValid && (
                  <div style={{ color: '#ff4d4f', fontSize: '12px', marginTop: '4px' }}>
                    {t('analysis.repo_url.error')}
                  </div>
                )}
              </div>

              {/* Authors Table */}
              {fetchingAuthors && (
                <div style={{ textAlign: 'center', padding: '20px' }}>
                  <LoadingOutlined style={{ fontSize: 24 }} />
                  <div style={{ marginTop: '8px' }}>{t('analysis.authors.fetching')}</div>
                </div>
              )}

              {!fetchingAuthors && authors.length > 0 && (
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                    <UserOutlined /> {t('analysis.authors.select')} ({t('analysis.authors.found', { total: authors.length, selected: selectedAuthors.length })})
                  </label>
                  {selectedAuthors.length > 1 && (
                    <Alert
                      message={`${t('analysis.authors.grouped_as')}: ${selectedAuthors.slice().sort().join(', ')}`}
                      description={t('analysis.authors.description')}
                      type="info"
                      showIcon
                      style={{ marginBottom: '8px' }}
                    />
                  )}
                  <Table
                    size="small"
                    dataSource={authors}
                    rowKey="author"
                    pagination={authors.length > 10 ? { pageSize: 10 } : false}
                    rowSelection={{
                      type: 'checkbox',
                      selectedRowKeys: selectedAuthors,
                      onChange: (selectedRowKeys) => {
                        setSelectedAuthors(selectedRowKeys as string[]);
                      },
                    }}
                    onRow={(record) => ({
                      onClick: () => {
                        // Toggle selection
                        setSelectedAuthors(prev => {
                          if (prev.includes(record.author)) {
                            return prev.filter(a => a !== record.author);
                          } else {
                            return [...prev, record.author];
                          }
                        });
                      },
                      style: { cursor: 'pointer' },
                    })}
                    columns={[
                      {
                        title: t('analysis.table.author'),
                        dataIndex: 'author',
                        key: 'author',
                        render: (text) => <strong>{text}</strong>,
                      },
                      {
                        title: t('analysis.table.email'),
                        dataIndex: 'email',
                        key: 'email',
                      },
                      {
                        title: t('analysis.table.commits'),
                        dataIndex: 'commits',
                        key: 'commits',
                        align: 'right',
                        render: (count) => <Tag color="blue">{count}</Tag>,
                      },
                    ]}
                  />
                </div>
              )}

              {!fetchingAuthors && isRepoUrlValid && authors.length === 0 && (
                <Alert
                  message={t('analysis.authors.no_data')}
                  description={t('analysis.authors.no_data.description')}
                  type="info"
                  showIcon
                />
              )}

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

          {/* Error Message Display */}
          {errorMessage && (
            <Alert
              title="Analysis Failed"
              description={errorMessage}
              type="error"
              showIcon
              closable
              onClose={() => setErrorMessage(null)}
              style={{ marginBottom: '16px' }}
            />
          )}

          {!trajectory && !loading && !errorMessage && (
            <Empty
              description={t('trajectory.no_data')}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}

          {trajectory && trajectory.total_checkpoints === 0 && (
            <Alert
              title={t('trajectory.no_checkpoints')}
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
                <Space orientation="vertical" size="small">
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
                      <strong>📊 {t('checkpoint.accumulation_progress')}:</strong>{' '}
                      {trajectory.accumulation_state.accumulated_commits.length} {t('checkpoint.accumulated')}
                      {' '}
                      ({t('checkpoint.need_more', { count: 10 - trajectory.accumulation_state.accumulated_commits.length })})
                    </div>
                  )}
                </Space>
              </div>

              <TrajectoryCharts trajectory={trajectory} />

              {/* Checkpoint Details Collapse */}
              <Card title={<span><CheckCircleOutlined /> {t('checkpoint.details')}</span>}>
                <Collapse
                  defaultActiveKey={[trajectory.checkpoints.length - 1]}
                  items={trajectory.checkpoints.map((checkpoint, index) => ({
                    key: index,
                    label: (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                        <span>
                          <strong>{t('checkpoint.number')} #{checkpoint.checkpoint_id}</strong>
                          {index === trajectory.checkpoints.length - 1 && (
                            <Tag color="blue" style={{ marginLeft: '8px' }}>{t('checkpoint.latest')}</Tag>
                          )}
                        </span>
                        <span style={{ color: '#888', fontSize: '12px' }}>
                          {checkpoint.commits_range.period_end
                            ? new Date(checkpoint.commits_range.period_end).toLocaleDateString()
                            : new Date(checkpoint.created_at).toLocaleDateString()
                          } - {checkpoint.commits_range.commit_count} {t('checkpoint.commits')}
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

      <LlmConfigModal />

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
