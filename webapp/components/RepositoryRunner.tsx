'use client';

import { useState } from 'react';
import { Button, Card, message, Input, Space, Typography, Steps, Progress, Tag, Collapse, Alert } from 'antd';
import {
  GithubOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  BugOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

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
}

interface DetectedTests {
  test_commands: string[];
  setup_commands: string[];
}

export default function RepositoryRunner() {
  const [repoUrl, setRepoUrl] = useState('https://gitee.com/zgcai/eval_test_1');
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [repoMetadata, setRepoMetadata] = useState<RepoMetadata | null>(null);
  const [overviewPath, setOverviewPath] = useState('');
  const [progressMessages, setProgressMessages] = useState<string[]>([]);
  const [testResults, setTestResults] = useState<TestSummary | null>(null);
  const [detectedTests, setDetectedTests] = useState<DetectedTests | null>(null);
  const [error, setError] = useState('');

  // Validate repo URL
  const validateRepoUrl = (url: string): boolean => {
    if (!url.trim()) return false;
    const githubPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    const giteePattern = /^https?:\/\/(www\.)?gitee\.com\/[\w-]+\/[\w.-]+\/?$/;
    return githubPattern.test(url.trim()) || giteePattern.test(url.trim());
  };

  // Fetch detected tests
  const fetchDetectedTests = async (overviewPath: string) => {
    try {
      const response = await fetch(
        `http://localhost:8001/api/runner/detect-tests?overview_path=${encodeURIComponent(overviewPath)}`
      );

      if (!response.ok) {
        throw new Error('Failed to detect tests');
      }

      const data = await response.json();
      setDetectedTests(data);
    } catch (err: any) {
      console.error('Failed to detect tests:', err);
      setDetectedTests({ test_commands: [], setup_commands: [] });
    }
  };

  // Step 1: Clone repository
  const handleClone = async () => {
    if (!validateRepoUrl(repoUrl)) {
      message.error('Please enter a valid GitHub or Gitee repository URL');
      return;
    }

    setLoading(true);
    setError('');
    setProgressMessages([]);

    try {
      const response = await fetch('http://localhost:8001/api/runner/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to clone repository');
      }

      const metadata = await response.json();
      setRepoMetadata(metadata);
      setCurrentStep(1);
      message.success('Repository cloned successfully!');
    } catch (err: any) {
      setError(err.message);
      message.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Explore repository
  const handleExplore = async () => {
    if (!repoMetadata) return;

    setLoading(true);
    setError('');
    setProgressMessages([]);

    try {
      const response = await fetch(
        `http://localhost:8001/api/runner/explore?clone_path=${encodeURIComponent(repoMetadata.clone_path)}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to start exploration');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete lines
        const lines = buffer.split('\n');
        // Keep the last incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.event === 'progress') {
                setProgressMessages(prev => [...prev, data.data.message]);
              } else if (data.event === 'status') {
                if (data.data.status === 'completed') {
                  setOverviewPath(data.data.overview_path);
                  setCurrentStep(2);
                  message.success('Repository exploration completed!');
                  // Fetch detected tests
                  await fetchDetectedTests(data.data.overview_path);
                } else if (data.data.status === 'failed') {
                  throw new Error(data.data.error);
                }
              }
            } catch (e) {
              console.error('Failed to parse SSE event:', line, e);
            }
          }
        }
      }
    } catch (err: any) {
      setError(err.message);
      message.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Run tests
  const handleRunTests = async () => {
    if (!repoMetadata || !overviewPath) return;

    setLoading(true);
    setError('');
    setProgressMessages([]);
    setTestResults(null);

    try {
      const response = await fetch(
        `http://localhost:8001/api/runner/run-tests?clone_path=${encodeURIComponent(repoMetadata.clone_path)}&overview_path=${encodeURIComponent(overviewPath)}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to start tests');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete lines
        const lines = buffer.split('\n');
        // Keep the last incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.event === 'progress') {
                setProgressMessages(prev => [...prev, data.data.message]);
              } else if (data.event === 'status') {
                if (data.data.status === 'completed') {
                  setTestResults(data.data.results);
                  setCurrentStep(3);
                  message.success('Tests completed!');
                } else if (data.data.status === 'failed') {
                  throw new Error(data.data.error);
                }
              }
            } catch (e) {
              console.error('Failed to parse SSE event:', line, e);
            }
          }
        }
      }
    } catch (err: any) {
      setError(err.message);
      message.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Reset to start over
  const handleReset = () => {
    setRepoUrl('');
    setCurrentStep(0);
    setRepoMetadata(null);
    setOverviewPath('');
    setProgressMessages([]);
    setTestResults(null);
    setDetectedTests(null);
    setError('');
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card>
        <Title level={2}>
          <GithubOutlined /> Repository Runner
        </Title>
        <Paragraph>
          Clone, explore, and test repositories automatically using Claude Code SDK.
        </Paragraph>

        <Steps
          current={currentStep}
          style={{ marginBottom: '32px' }}
          items={[
            { title: 'Clone Repository', icon: currentStep === 0 && loading ? <LoadingOutlined /> : undefined },
            { title: 'Explore & Document', icon: currentStep === 1 && loading ? <LoadingOutlined /> : undefined },
            { title: 'Run Tests', icon: currentStep === 2 && loading ? <LoadingOutlined /> : undefined },
            { title: 'Results', icon: currentStep === 3 ? <CheckCircleOutlined /> : undefined }
          ]}
        />

        {error && (
          <Alert
            message="Error"
            description={error}
            type="error"
            closable
            onClose={() => setError('')}
            style={{ marginBottom: '16px' }}
          />
        )}

        {/* Step 1: Input repository URL */}
        {currentStep === 0 && (
          <Card title="Step 1: Enter Repository URL" type="inner">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Input
                size="large"
                placeholder="https://github.com/owner/repo or https://gitee.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                prefix={<GithubOutlined />}
              />
              <Button
                type="primary"
                size="large"
                onClick={handleClone}
                loading={loading}
                disabled={!validateRepoUrl(repoUrl)}
                icon={<PlayCircleOutlined />}
              >
                Clone Repository
              </Button>
            </Space>
          </Card>
        )}

        {/* Step 2: Show metadata and explore */}
        {currentStep === 1 && repoMetadata && (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Card title="Repository Metadata" type="inner">
              <Paragraph>
                <Text strong>Repository Name:</Text> {repoMetadata.repo_name}
              </Paragraph>
              <Paragraph>
                <Text strong>Default Branch:</Text> {repoMetadata.default_branch}
              </Paragraph>
              <Paragraph>
                <Text strong>Latest Commit:</Text> <Text code>{repoMetadata.latest_commit_id.substring(0, 7)}</Text>
              </Paragraph>
              <Paragraph>
                <Text strong>Clone Path:</Text> <Text code>{repoMetadata.clone_path}</Text>
              </Paragraph>
            </Card>

            <Card title="Step 2: Explore Repository" type="inner">
              <Button
                type="primary"
                size="large"
                onClick={handleExplore}
                loading={loading}
                icon={<FileTextOutlined />}
              >
                Generate REPO_OVERVIEW.md
              </Button>

              {progressMessages.length > 0 && (
                <Card style={{ marginTop: '16px' }} title="Progress">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {progressMessages.map((msg, idx) => (
                      <Text key={idx}>• {msg}</Text>
                    ))}
                  </Space>
                </Card>
              )}
            </Card>
          </Space>
        )}

        {/* Step 3: Run tests */}
        {currentStep === 2 && (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Card title="Exploration Complete" type="inner">
              <Paragraph>
                <CheckCircleOutlined style={{ color: '#52c41a', marginRight: '8px' }} />
                REPO_OVERVIEW.md has been generated successfully!
              </Paragraph>
              <Paragraph>
                <Text strong>Overview Path:</Text> <Text code>{overviewPath}</Text>
              </Paragraph>
            </Card>

            <Card title="Step 3: Run Tests" type="inner">
              {/* Display detected tests */}
              {detectedTests && (
                <Card style={{ marginBottom: '16px', backgroundColor: '#fafafa' }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {detectedTests.test_commands.length > 0 ? (
                      <>
                        <Text strong>Detected Test Commands:</Text>
                        {detectedTests.test_commands.map((cmd, idx) => (
                          <div key={idx} style={{ paddingLeft: '16px' }}>
                            <Text code>{cmd}</Text>
                          </div>
                        ))}
                        {detectedTests.setup_commands.length > 0 && (
                          <>
                            <Text strong style={{ marginTop: '8px' }}>Setup Commands:</Text>
                            {detectedTests.setup_commands.map((cmd, idx) => (
                              <div key={idx} style={{ paddingLeft: '16px' }}>
                                <Text code>{cmd}</Text>
                              </div>
                            ))}
                          </>
                        )}
                      </>
                    ) : (
                      <Text type="warning">No tests detected in this repository</Text>
                    )}
                  </Space>
                </Card>
              )}

              <Button
                type="primary"
                size="large"
                onClick={handleRunTests}
                loading={loading}
                icon={<BugOutlined />}
                disabled={!detectedTests || detectedTests.test_commands.length === 0}
              >
                Run Tests
              </Button>

              {progressMessages.length > 0 && (
                <Card style={{ marginTop: '16px' }} title="Execution Progress">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {progressMessages.map((msg, idx) => (
                      <Text key={idx}>• {msg}</Text>
                    ))}
                  </Space>
                </Card>
              )}
            </Card>
          </Space>
        )}

        {/* Step 4: Show results */}
        {currentStep === 3 && testResults && (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Card title="Test Results" type="inner">
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                <div style={{ textAlign: 'center' }}>
                  <Title level={1} style={{ margin: 0, color: testResults.score >= 70 ? '#52c41a' : testResults.score >= 40 ? '#faad14' : '#ff4d4f' }}>
                    {testResults.score}
                  </Title>
                  <Text type="secondary">Score (out of 100)</Text>
                </div>

                <Space size="large" style={{ justifyContent: 'center', width: '100%' }}>
                  <div>
                    <Tag color="success">Passed: {testResults.passed}</Tag>
                  </div>
                  <div>
                    <Tag color="error">Failed: {testResults.failed}</Tag>
                  </div>
                  <div>
                    <Tag color="default">Total: {testResults.total}</Tag>
                  </div>
                </Space>

                {testResults.message && (
                  <Alert message={testResults.message} type="info" />
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
              </Space>
            </Card>

            <Button type="default" onClick={handleReset}>
              Run Another Repository
            </Button>
          </Space>
        )}
      </Card>
    </div>
  );
}
