'use client';

import { useState } from 'react';
import { Button, Card, message, Input, Space, Typography, Steps, Tag, Collapse, Alert, Dropdown } from 'antd';
import {
  GithubOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined
} from '@ant-design/icons';
import { useI18n } from './I18nContext';
import { useAppSettings } from './AppSettingsContext';
import { LOCALES } from '../i18n';
import { getRunnerApiBaseUrl } from '../utils/apiBase';
import { validateRepoUrl } from '../utils/repoUrl.mjs';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;
const RUNNER_API_BASE = getRunnerApiBaseUrl();
const GIT_COMMIT_SHA_PATTERN = /^[0-9a-f]{7,40}$/i;

function getVersionRefPayload(versionRef: string): { sha?: string; tag?: string } {
  const trimmed = versionRef.trim();
  if (!trimmed) return {};
  return GIT_COMMIT_SHA_PATTERN.test(trimmed) ? { sha: trimmed } : { tag: trimmed };
}

interface RepoMetadata {
  repo_name: string;
  default_branch: string;
  latest_commit_id: string;
  clone_path: string;
  platform: string;
  owner: string;
}

interface TestResult {
  name: string;
  status: string;
  duration?: number;
  output?: string;
}

interface TestSummary {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  score: number;
  details: TestResult[];
  message?: string;
  feature_coverage?: FeatureCoverage;
  score_breakdown?: ScoreBreakdown;
}

interface DetectedTests {
  test_commands: string[];
  setup_commands: string[];
  validation_features?: string[];
}

interface FeatureCoverage {
  covered: string[];
  not_covered: string[];
  runtime_covered?: string[];
  coverage_ratio: number;
}

interface ScoreBreakdown {
  code_score: number;
  code_weight: number;
  functionality_score: number;
  functionality_weight: number;
  code_pass_rate: number;
  functionality_coverage_ratio: number;
  weight_explanation?: string;
}

interface RunnerStreamEvent {
  event?: string;
  data?: {
    message?: string;
    status?: string;
    error?: string;
    overview_path?: string;
    results?: TestSummary;
  };
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function readRunnerStream(
  response: Response,
  onEvent: (event: RunnerStreamEvent) => void
) {
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('No response body');
  }

  let buffer = '';

  const processLine = (line: string) => {
    if (!line.startsWith('data: ')) return;
    const data = JSON.parse(line.substring(6));
    onEvent(data);
  };

  while (true) {
    const { done, value } = await reader.read();

    if (done) {
      buffer += decoder.decode();
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      processLine(line.trimEnd());
    }
  }

  if (buffer.trim()) {
    for (const line of buffer.split('\n')) {
      processLine(line.trimEnd());
    }
  }
}

export default function RepositoryRunner() {
  const { t } = useI18n();
  const { locale, setLocale } = useAppSettings();
  const [repoUrl, setRepoUrl] = useState('https://gitee.com/zgcai/eval_test_1');
  const [versionRef, setVersionRef] = useState('');
  const [featureRequirements, setFeatureRequirements] = useState('');
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [progressMessages, setProgressMessages] = useState<string[]>([]);
  const [testResults, setTestResults] = useState<TestSummary | null>(null);
  const [detectedTests, setDetectedTests] = useState<DetectedTests | null>(null);
  const [error, setError] = useState('');

  // Store outputs for each completed step
  const [step1Output, setStep1Output] = useState<RepoMetadata | null>(null);
  const [step2Output, setStep2Output] = useState<{ overviewPath: string; messages: string[] } | null>(null);
  const [step3Output, setStep3Output] = useState<{ results: TestSummary; messages: string[] } | null>(null);

  const featureRequirementsParam = () => featureRequirements.trim();

  const appendFeatureRequirements = (url: string): string => {
    const requirements = featureRequirementsParam();
    if (!requirements) return url;
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}feature_requirements=${encodeURIComponent(requirements)}`;
  };

  const getConclusion = (results: TestSummary): { type: 'success' | 'warning' | 'error' | 'info'; title: string; description: string } => {
    const coverage = results.feature_coverage;
    const codePassed = results.failed === 0 && results.total > 0;

    if (coverage) {
      const ratio = Math.round(coverage.coverage_ratio * 100);
      if (codePassed && coverage.not_covered.length === 0) {
        return {
          type: 'success',
          title: t('runner.step4.conclusion_passed'),
          description: t('runner.step4.conclusion_passed_desc')
            .replace('{tests}', `${results.passed}/${results.total}`)
            .replace('{coverage}', `${ratio}%`),
        };
      }
      if (results.passed > 0 || coverage.covered.length > 0 || (coverage.runtime_covered?.length || 0) > 0) {
        return {
          type: 'warning',
          title: t('runner.step4.conclusion_partial'),
          description: t('runner.step4.conclusion_partial_desc')
            .replace('{tests}', `${results.passed}/${results.total}`)
            .replace('{coverage}', `${ratio}%`),
        };
      }
      return {
        type: 'error',
        title: t('runner.step4.conclusion_failed'),
        description: t('runner.step4.conclusion_failed_desc')
          .replace('{tests}', `${results.passed}/${results.total}`)
          .replace('{coverage}', `${ratio}%`),
      };
    }

    return {
      type: codePassed ? 'success' : 'warning',
      title: codePassed ? t('runner.step4.conclusion_tests_passed') : t('runner.step4.conclusion_tests_attention'),
      description: t('runner.step4.conclusion_tests_only')
        .replace('{tests}', `${results.passed}/${results.total}`),
    };
  };

  // Fetch detected tests
  const fetchDetectedTests = async (overviewPath: string) => {
    try {
      const response = await fetch(
        appendFeatureRequirements(
          `${RUNNER_API_BASE}/api/runner/detect-tests/?overview_path=${encodeURIComponent(overviewPath)}`
        )
      );

      if (!response.ok) {
        throw new Error('Failed to detect tests');
      }

      const data = await response.json() as DetectedTests;
      setDetectedTests(data);
    } catch (err: unknown) {
      console.error('Failed to detect tests:', err);
      setDetectedTests({ test_commands: [], setup_commands: [] });
    }
  };

  // Step 1: Clone repository (internal function)
  const cloneRepository = async (): Promise<RepoMetadata | null> => {
    setProgressMessages([]);
    setCurrentStep(0);

    const response = await fetch(`${RUNNER_API_BASE}/api/runner/clone/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: repoUrl, ...getVersionRefPayload(versionRef) })
    });

    if (!response.ok) {
      const errorData = await response.json() as { detail?: string };
      throw new Error(errorData.detail || 'Failed to clone repository');
    }

    const metadata = await response.json() as RepoMetadata;
    setStep1Output(metadata);
    setCurrentStep(1);
    message.success(t('runner.step1.completed'));
    return metadata;
  };

  // Step 2: Explore repository (internal function)
  const exploreRepository = async (metadata: RepoMetadata): Promise<string> => {
    setProgressMessages([]);
    const explorationMessages: string[] = [];

    const response = await fetch(
      appendFeatureRequirements(
        `${RUNNER_API_BASE}/api/runner/explore/?clone_path=${encodeURIComponent(metadata.clone_path)}`
      ),
      { method: 'POST' }
    );

    if (!response.ok) {
      throw new Error('Failed to start exploration');
    }

    let explorationPath = '';
    await readRunnerStream(response, (data) => {
      if (data.event === 'progress' && data.data?.message) {
        const progressMessage = data.data.message;
        explorationMessages.push(progressMessage);
        setProgressMessages(prev => [...prev, progressMessage]);
      } else if (data.event === 'status') {
        if (data.data?.status === 'completed') {
          explorationPath = data.data.overview_path || '';
        } else if (data.data?.status === 'failed') {
          throw new Error(data.data.error || 'Repository exploration failed');
        }
      }
    });

    if (!explorationPath) {
      throw new Error('No overview path received');
    }

    setStep2Output({ overviewPath: explorationPath, messages: explorationMessages });
    setCurrentStep(2);
    message.success(t('runner.step2.completed'));

    // Fetch detected tests
    await fetchDetectedTests(explorationPath);
    return explorationPath;
  };

  // Step 3: Run tests (internal function)
  const runTests = async (metadata: RepoMetadata, overviewPath: string): Promise<TestSummary> => {
    setProgressMessages([]);
    setTestResults(null);
    const testMessages: string[] = [];

    const response = await fetch(
      appendFeatureRequirements(
        `${RUNNER_API_BASE}/api/runner/run-tests/?clone_path=${encodeURIComponent(metadata.clone_path)}&overview_path=${encodeURIComponent(overviewPath)}`
      ),
      { method: 'POST' }
    );

    if (!response.ok) {
      throw new Error('Failed to start tests');
    }

    let results: TestSummary | null = null;
    await readRunnerStream(response, (data) => {
      if (data.event === 'progress' && data.data?.message) {
        const progressMessage = data.data.message;
        testMessages.push(progressMessage);
        setProgressMessages(prev => [...prev, progressMessage]);
      } else if (data.event === 'status') {
        if (data.data?.status === 'completed') {
          results = data.data.results || null;
        } else if (data.data?.status === 'failed') {
          throw new Error(data.data.error || 'Test run failed');
        }
      }
    });

    if (!results) {
      throw new Error('No test results received');
    }

    setTestResults(results);
    setStep3Output({ results, messages: testMessages });
    setCurrentStep(3);
    message.success(t('runner.step3.completed'));

    return results;
  };

  // Main handler: Execute all steps automatically
  const handleRunAll = async () => {
    if (!validateRepoUrl(repoUrl)) {
      message.error(t('analysis.repo_url.error'));
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Step 1: Clone
      const metadata = await cloneRepository();
      if (!metadata) throw new Error('Failed to get repository metadata');

      // Step 2: Explore
      const explorationPath = await exploreRepository(metadata);
      if (!explorationPath) throw new Error('Failed to get overview path');

      // Step 3: Run tests
      await runTests(metadata, explorationPath);

      // Step 4: Complete (automatically shown when currentStep = 3)
      message.success(t('runner.step4.title'));
    } catch (err: unknown) {
      const errorMessage = getErrorMessage(err);
      setError(errorMessage);
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };


  // Reset to start over
  const handleReset = () => {
    setRepoUrl('');
    setVersionRef('');
    setFeatureRequirements('');
    setCurrentStep(0);
    setProgressMessages([]);
    setTestResults(null);
    setDetectedTests(null);
    setError('');
    setStep1Output(null);
    setStep2Output(null);
    setStep3Output(null);
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
          <div>
            <Title level={2} style={{ marginBottom: '8px' }}>
              <GithubOutlined /> {t('runner.title')}
            </Title>
            <Paragraph style={{ marginBottom: 0 }}>
              {t('runner.description')}
            </Paragraph>
          </div>

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
        </div>

        <Steps
          current={currentStep}
          style={{ marginBottom: '32px' }}
          items={[
            { title: t('runner.step1.title'), icon: currentStep === 0 && loading ? <LoadingOutlined /> : undefined },
            { title: t('runner.step2.title'), icon: currentStep === 1 && loading ? <LoadingOutlined /> : undefined },
            { title: t('runner.step3.title'), icon: currentStep === 2 && loading ? <LoadingOutlined /> : undefined },
            { title: t('runner.step4.title'), icon: currentStep === 3 ? <CheckCircleOutlined /> : undefined }
          ]}
        />

        {error && (
          <Alert
            title={t('runner.error')}
            description={error}
            type="error"
            closable
            onClose={() => setError('')}
            style={{ marginBottom: '16px' }}
          />
        )}

        {/* Step 1: Input repository URL */}
        {currentStep === 0 && (
          <Card title={t('runner.step1.enter_url')} type="inner">
            <Space orientation="vertical" style={{ width: '100%' }}>
              <Input
                size="large"
                placeholder={t('analysis.repo_url.placeholder')}
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                prefix={<GithubOutlined />}
              />
              <Input
                size="large"
                placeholder={t('runner.version_ref.placeholder')}
                value={versionRef}
                onChange={(e) => setVersionRef(e.target.value)}
              />
              <TextArea
                rows={4}
                placeholder={t('runner.feature_requirements.placeholder')}
                value={featureRequirements}
                onChange={(e) => setFeatureRequirements(e.target.value)}
              />
              <Button
                type="primary"
                size="large"
                onClick={handleRunAll}
                loading={loading}
                disabled={!validateRepoUrl(repoUrl)}
                icon={<PlayCircleOutlined />}
              >
                {t('runner.step1.start')}
              </Button>
            </Space>
          </Card>
        )}

        {/* Show Step 1 Output (when step >= 1) */}
        {currentStep >= 1 && step1Output && (
          <Card title={t('runner.step1.completed')} type="inner" style={{ marginBottom: '16px' }}>
            <Paragraph>
              <Text strong>{t('runner.step1.repo_name')}:</Text> {step1Output.repo_name}
            </Paragraph>
            <Paragraph>
              <Text strong>{t('runner.step1.default_branch')}:</Text> {step1Output.default_branch}
            </Paragraph>
            <Paragraph>
              <Text strong>{t('runner.step1.latest_commit')}:</Text> <Text code>{step1Output.latest_commit_id.substring(0, 7)}</Text>
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              <Text strong>{t('runner.step1.clone_path')}:</Text> <Text code>{step1Output.clone_path}</Text>
            </Paragraph>
          </Card>
        )}

        {/* Show Step 2 Progress or Output */}
        {currentStep === 1 && (
          <Card title={t('runner.step2.exploring')} type="inner">
            {loading && <LoadingOutlined style={{ fontSize: 24, marginRight: 8 }} />}
            {progressMessages.length > 0 && (
              <Card style={{ marginTop: '16px' }} title={t('runner.progress')}>
                <Space orientation="vertical" style={{ width: '100%' }}>
                  {progressMessages.map((msg, idx) => (
                    <Text key={idx}>• {msg}</Text>
                  ))}
                </Space>
              </Card>
            )}
          </Card>
        )}

        {currentStep >= 2 && step2Output && (
          <Card title={t('runner.step2.completed')} type="inner" style={{ marginBottom: '16px' }}>
            <Paragraph>
              <CheckCircleOutlined style={{ color: '#52c41a', marginRight: '8px' }} />
              {t('runner.step2.success')}
            </Paragraph>
            <Paragraph style={{ marginBottom: 0 }}>
              <Text strong>{t('runner.step2.overview_path')}:</Text> <Text code>{step2Output.overviewPath}</Text>
            </Paragraph>
            <Collapse ghost style={{ marginTop: '8px' }}>
              <Panel header={t('runner.step2.view_messages')} key="1">
                <Space orientation="vertical" style={{ width: '100%' }}>
                  {step2Output.messages.map((msg, idx) => (
                    <Text key={idx} type="secondary">• {msg}</Text>
                  ))}
                </Space>
              </Panel>
            </Collapse>
          </Card>
        )}

        {/* Show Step 3 Progress or Output */}
        {currentStep === 2 && (
          <Card title={t('runner.step3.running')} type="inner">
            {loading && <LoadingOutlined style={{ fontSize: 24, marginRight: 8 }} />}

            {/* Display detected tests */}
            {detectedTests && (
              <Card style={{ marginBottom: '16px', backgroundColor: '#fafafa' }}>
                <Space orientation="vertical" style={{ width: '100%' }}>
                  {detectedTests.test_commands.length > 0 ? (
                    <>
                      <Text strong>{t('runner.step3.detected_tests')}:</Text>
                      {detectedTests.test_commands.map((cmd, idx) => (
                        <div key={idx} style={{ paddingLeft: '16px' }}>
                          <Text code>{cmd}</Text>
                        </div>
                      ))}
                      {detectedTests.setup_commands.length > 0 && (
                        <>
                          <Text strong style={{ marginTop: '8px' }}>{t('runner.step3.setup_commands')}:</Text>
                          {detectedTests.setup_commands.map((cmd, idx) => (
                            <div key={idx} style={{ paddingLeft: '16px' }}>
                              <Text code>{cmd}</Text>
                            </div>
                          ))}
                        </>
                      )}
                    </>
                  ) : (
                    <Text type="warning">{t('runner.step3.no_tests')}</Text>
                  )}
                  {detectedTests.validation_features && detectedTests.validation_features.length > 0 && (
                    <>
                      <Text strong style={{ marginTop: '8px' }}>{t('runner.step3.validation_features')}:</Text>
                      <Space wrap>
                        {detectedTests.validation_features.map((feature, idx) => (
                          <Tag key={idx} color="processing">{feature}</Tag>
                        ))}
                      </Space>
                    </>
                  )}
                </Space>
              </Card>
            )}

            {progressMessages.length > 0 && (
              <Card style={{ marginTop: '16px' }} title={t('runner.step3.execution_progress')}>
                <Space orientation="vertical" style={{ width: '100%' }}>
                  {progressMessages.map((msg, idx) => (
                    <Text key={idx}>• {msg}</Text>
                  ))}
                </Space>
              </Card>
            )}
          </Card>
        )}

        {currentStep >= 3 && step3Output && (
          <Card title={t('runner.step3.completed')} type="inner" style={{ marginBottom: '16px' }}>
            <Space orientation="vertical" style={{ width: '100%' }}>
              <div>
                <Tag color="success">{t('runner.step4.passed')}: {step3Output.results.passed}</Tag>
                <Tag color="error">{t('runner.step4.failed')}: {step3Output.results.failed}</Tag>
                <Tag color="default">{t('runner.step4.total')}: {step3Output.results.total}</Tag>
                <Tag color={step3Output.results.score >= 70 ? 'success' : step3Output.results.score >= 40 ? 'warning' : 'error'}>
                  {t('runner.step4.score')}: {step3Output.results.score}/100
                </Tag>
                {step3Output.results.feature_coverage && (
                  <Tag color={step3Output.results.feature_coverage.not_covered.length === 0 ? 'success' : 'warning'}>
                    {t('runner.step4.feature_coverage')}: {Math.round(step3Output.results.feature_coverage.coverage_ratio * 100)}%
                  </Tag>
                )}
              </div>
              <Collapse ghost>
                <Panel header={t('runner.step3.view_messages')} key="1">
                  <Space orientation="vertical" style={{ width: '100%' }}>
                    {step3Output.messages.map((msg, idx) => (
                      <Text key={idx} type="secondary">• {msg}</Text>
                    ))}
                  </Space>
                </Panel>
              </Collapse>
            </Space>
          </Card>
        )}

        {/* Step 4: Show full results */}
        {currentStep === 3 && testResults && (
          <Card title={t('runner.step4.title')} type="inner">
            <Space orientation="vertical" style={{ width: '100%' }} size="large">
              <Alert
                type={getConclusion(testResults).type}
                showIcon
                title={getConclusion(testResults).title}
                description={getConclusion(testResults).description}
              />

              <div style={{ textAlign: 'center' }}>
                <Title level={1} style={{ margin: 0, color: testResults.score >= 70 ? '#52c41a' : testResults.score >= 40 ? '#faad14' : '#ff4d4f' }}>
                  {testResults.score}
                </Title>
                <Text type="secondary">{t('runner.step4.score')}</Text>
              </div>

              <Space size="large" style={{ justifyContent: 'center', width: '100%' }}>
                <div>
                  <Tag color="success">{t('runner.step4.passed')}: {testResults.passed}</Tag>
                </div>
                <div>
                  <Tag color="error">{t('runner.step4.failed')}: {testResults.failed}</Tag>
                </div>
                <div>
                  <Tag color="default">{t('runner.step4.total')}: {testResults.total}</Tag>
                </div>
              </Space>

              {testResults.feature_coverage && (
                <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, padding: 16 }}>
                  <Space orientation="vertical" style={{ width: '100%' }}>
                    <Text strong>{t('runner.step4.feature_validation')}</Text>
                    {testResults.score_breakdown && (
                      <Space wrap>
                        <Tag color="blue">
                          {t('runner.step4.code_score')}: {testResults.score_breakdown.code_score}/{testResults.score_breakdown.code_weight}
                        </Tag>
                        <Tag color="purple">
                          {t('runner.step4.functionality_score')}: {testResults.score_breakdown.functionality_score}/{testResults.score_breakdown.functionality_weight}
                        </Tag>
                      </Space>
                    )}
                    {testResults.feature_coverage.covered.length > 0 && (
                      <div>
                        <Text strong>{t('runner.step4.covered_features')}:</Text>
                        <div style={{ marginTop: '8px' }}>
                          <Space wrap>
                            {testResults.feature_coverage.covered.map((feature, idx) => (
                              <Tag key={idx} color="success">{feature}</Tag>
                            ))}
                          </Space>
                        </div>
                      </div>
                    )}
                    {(testResults.feature_coverage.runtime_covered || []).length > 0 && (
                      <div>
                        <Text strong>{t('runner.step4.runtime_covered_features')}:</Text>
                        <div style={{ marginTop: '8px' }}>
                          <Space wrap>
                            {testResults.feature_coverage.runtime_covered?.map((feature, idx) => (
                              <Tag key={idx} color="cyan">{feature}</Tag>
                            ))}
                          </Space>
                        </div>
                      </div>
                    )}
                    {testResults.feature_coverage.not_covered.length > 0 && (
                      <div>
                        <Text strong>{t('runner.step4.missing_features')}:</Text>
                        <div style={{ marginTop: '8px' }}>
                          <Space wrap>
                            {testResults.feature_coverage.not_covered.map((feature, idx) => (
                              <Tag key={idx} color="error">{feature}</Tag>
                            ))}
                          </Space>
                        </div>
                      </div>
                    )}
                  </Space>
                </div>
              )}

              {testResults.message && (
                <Alert title={testResults.message} type="info" />
              )}

              {testResults.details && testResults.details.length > 0 && (
                <Collapse>
                  {testResults.details.map((test, idx) => (
                    <Panel
                      header={
                        <Space>
                          {test.status === 'passed' ? (
                            <CheckCircleOutlined style={{ color: '#52c41a' }} />
                          ) : (
                            <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                          )}
                          <Text>{test.name}</Text>
                          {test.duration && <Text type="secondary">({test.duration.toFixed(2)}s)</Text>}
                        </Space>
                      }
                      key={idx}
                    >
                      {test.output && (
                        <TextArea
                          value={test.output}
                          rows={10}
                          readOnly
                          style={{ fontFamily: 'monospace', fontSize: '12px' }}
                        />
                      )}
                    </Panel>
                  ))}
                </Collapse>
              )}

              <Button type="default" onClick={handleReset}>
                {t('runner.step4.run_another')}
              </Button>
            </Space>
          </Card>
        )}
      </Card>
    </div>
  );
}
