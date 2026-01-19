'use client';

import { useState, useEffect, useCallback } from 'react';
import { Input, Button, Card, Alert, Table, Tag, Space, message, Avatar, Select } from 'antd';
import { GithubOutlined, CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined, LoadingOutlined, UserOutlined, TeamOutlined, DownloadOutlined } from '@ant-design/icons';
import ContributorComparison from '../../components/ContributorComparison';
import { exportMultiRepoPDF } from '../../utils/pdfExport';
import type { ContributorComparisonData } from '../../types';
import './repos.css';

const { TextArea } = Input;

// Default to same-origin so the bundled dashboard works when served by the backend.
// For separate frontend dev server, set NEXT_PUBLIC_API_SERVER_URL=http://localhost:8000
const API_SERVER_URL = process.env.NEXT_PUBLIC_API_SERVER_URL || '';

interface RepoResult {
  url: string;
  owner?: string;
  repo?: string;
  status: 'extracted' | 'skipped' | 'failed';
  message: string;
  data_exists: boolean;
}

interface BatchResult {
  success: boolean;
  results: RepoResult[];
  summary: {
    total: number;
    extracted: number;
    skipped: number;
    failed: number;
  };
}

interface CommonContributor {
  author: string;
  email: string;
  repos: Array<{
    owner: string;
    repo: string;
    commits: number;
    email: string;
  }>;
  total_commits: number;
  repo_count: number;
}

interface CommonContributorsResult {
  success: boolean;
  common_contributors: CommonContributor[];
  summary: {
    total_repos: number;
    total_common_contributors: number;
  };
  message?: string;
}

export default function ReposPage() {
  const [repoUrls, setRepoUrls] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<BatchResult | null>(null);
  const [commonContributors, setCommonContributors] = useState<CommonContributorsResult | null>(null);
  const [loadingCommon, setLoadingCommon] = useState(false);
  const [selectedContributor, setSelectedContributor] = useState<string>('');
  const [comparisonData, setComparisonData] = useState<ContributorComparisonData | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  const generateAvatarUrl = (author: string) => {
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(author)}&background=FFEB00&color=0A0A0A&size=128&bold=true`;
  };

  const handleDownloadPDF = async () => {
    if (!comparisonData || !selectedContributor) {
      message.error('No comparison data available to export');
      return;
    }

    try {
      message.loading('Generating PDF report...', 0);
      await exportMultiRepoPDF(comparisonData, selectedContributor);
      message.destroy();
      message.success('PDF report downloaded successfully!');
    } catch (error: unknown) {
      message.destroy();
      message.error('Failed to generate PDF report');
      console.error('PDF generation error:', error);
    }
  };

  // Function to compare a specific contributor
  const compareContributor = useCallback(async (contributorName: string, reposToCompare: Array<{ owner: string, repo: string }>) => {
    setLoadingComparison(true);
    setComparisonData(null);

    try {
      const response = await fetch(`${API_SERVER_URL}/api/batch/compare-contributor`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          contributor: contributorName.trim(),
          repos: reposToCompare
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to compare contributor');
      }

      const data: ContributorComparisonData = await response.json();

      if (!data.success) {
        throw new Error('No evaluation data found');
      }

      setComparisonData(data);
      message.success(`Compared ${contributorName} across ${data.comparisons.length} repositories!`);

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('Failed to compare contributor:', msg);
      message.error(`Failed to compare ${contributorName}: ${msg}`);
    } finally {
      setLoadingComparison(false);
    }
  }, []);

  // Effect to auto-compare when selected contributor changes
  useEffect(() => {
    if (selectedContributor && results) {
      const reposWithData = results.results.filter(r => r.data_exists && r.owner && r.repo);
      if (reposWithData.length >= 2) {
        const reposToCompare = reposWithData.map(r => ({
          owner: r.owner!,
          repo: r.repo!
        }));
        compareContributor(selectedContributor, reposToCompare);
      }
    }
  }, [selectedContributor, results, compareContributor]);

  const handleSubmit = async () => {
    setError('');
    setResults(null);
    setCommonContributors(null);
    setSelectedContributor('');
    setComparisonData(null);

    // Split by newline and filter out empty lines
    const urls = repoUrls
      .split('\n')
      .map(url => url.trim())
      .filter(url => url.length > 0);

    // Validate: at least 2, at most 5
    if (urls.length < 2) {
      setError('Please enter at least 2 repository URLs');
      return;
    }

    if (urls.length > 5) {
      setError('Please enter at most 5 repository URLs');
      return;
    }

    setLoading(true);

    try {
      // Step 1: Extract repositories
      const response = await fetch(`${API_SERVER_URL}/api/batch/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ urls }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to extract repositories');
      }

      const data: BatchResult = await response.json();
      setResults(data);

      // Show success message
      if (data.summary.failed === 0) {
        message.success(`Successfully processed ${data.summary.total} repositories!`);
      } else if (data.summary.extracted > 0 || data.summary.skipped > 0) {
        message.warning(`Processed with some failures: ${data.summary.failed} failed`);
      } else {
        message.error('All repositories failed to process');
        setLoading(false);
        return;
      }

      // Step 2: Find common contributors
      // Get repos that have data
      const reposWithData = data.results.filter(r => r.data_exists && r.owner && r.repo);

      if (reposWithData.length >= 2) {
        setLoadingCommon(true);

        const commonResponse = await fetch(`${API_SERVER_URL}/api/batch/common-contributors`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            repos: reposWithData.map(r => ({
              owner: r.owner,
              repo: r.repo
            }))
          }),
        });

        if (commonResponse.ok) {
          const commonData: CommonContributorsResult = await commonResponse.json();
          setCommonContributors(commonData);

          if (commonData.common_contributors.length > 0) {
            message.info(`Found ${commonData.common_contributors.length} common contributors!`);

            // Automatically select and compare the first contributor
            const firstContributor = commonData.common_contributors[0].author;
            setSelectedContributor(firstContributor);
          }
        } else {
          console.error('Failed to fetch common contributors');
        }

        setLoadingCommon(false);
      }

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || 'Failed to extract repositories');
      message.error('Failed to extract repositories');
    } finally {
      setLoading(false);
    }
  };

  const useTestRepo = () => {
    setRepoUrls('https://gitee.com/zgcai/eval_test_1\nhttps://gitee.com/zgcai/eval_test_2');
    setError('');
    setResults(null);
    setCommonContributors(null);
    setSelectedContributor('');
    setComparisonData(null);
    message.info('Filled test repositories. Click Analyze to run the baseline comparison.');
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'extracted':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'skipped':
        return <MinusCircleOutlined style={{ color: '#faad14' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return null;
    }
  };

  const getStatusTag = (status: string) => {
    switch (status) {
      case 'extracted':
        return <Tag color="success">Extracted</Tag>;
      case 'skipped':
        return <Tag color="warning">Skipped</Tag>;
      case 'failed':
        return <Tag color="error">Failed</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  const columns = [
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Space>
          {getStatusIcon(status)}
          {getStatusTag(status)}
        </Space>
      ),
    },
    {
      title: 'Repository',
      key: 'repository',
      render: (record: RepoResult) => (
        <div>
          <div style={{ fontWeight: 'bold' }}>
            {record.owner && record.repo ? `${record.owner}/${record.repo}` : 'Invalid URL'}
          </div>
          <div style={{ fontSize: '12px', color: '#888', marginTop: '4px' }}>
            {record.url}
          </div>
        </div>
      ),
    },
    {
      title: 'Message',
      dataIndex: 'message',
      key: 'message',
      render: (message: string) => (
        <span style={{ color: '#666' }}>{message}</span>
      ),
    },
  ];

  const contributorColumns = [
    {
      title: 'Contributor',
      key: 'contributor',
      width: 250,
      render: (record: CommonContributor) => (
        <Space>
          <Avatar size={40} src={generateAvatarUrl(record.author)} icon={<UserOutlined />} />
          <div>
            <div style={{ fontWeight: 'bold' }}>{record.author}</div>
            <div style={{ fontSize: '12px', color: '#888' }}>{record.email}</div>
          </div>
        </Space>
      ),
    },
    {
      title: 'Repositories',
      dataIndex: 'repo_count',
      key: 'repo_count',
      width: 120,
      render: (count: number) => (
        <Tag color="purple" style={{ fontSize: '14px', padding: '4px 12px' }}>
          {count} repos
        </Tag>
      ),
    },
    {
      title: 'Total Commits',
      dataIndex: 'total_commits',
      key: 'total_commits',
      width: 120,
      render: (commits: number) => (
        <span style={{ fontWeight: 'bold', fontSize: '16px' }}>
          {commits}
        </span>
      ),
    },
    {
      title: 'Details',
      key: 'details',
      render: (record: CommonContributor) => (
        <div>
          {record.repos.map((repo, idx) => (
            <div key={idx} style={{ marginBottom: '4px' }}>
              <span style={{ fontWeight: 'bold' }}>
                {repo.owner}/{repo.repo}
              </span>
              <span style={{ color: '#666', marginLeft: '8px' }}>
                {repo.commits} commits
              </span>
            </div>
          ))}
        </div>
      ),
    },
  ];

  return (
    <div className="repos-page">
      <div className="repos-container">
        <div className="repos-header">
          <h1>Multi-Repository Analysis</h1>
          <p>Extract commit data and find common contributors across 2-5 GitHub/Gitee repositories</p>
        </div>

        <Card className="repos-card">
          <div className="repos-form">
            <label className="repos-label">
              <GithubOutlined />
              <span>Repository URLs (2-5 URLs, one per line)</span>
            </label>

            <div className="repos-input-row">
              <TextArea
                value={repoUrls}
                onChange={(e) => setRepoUrls(e.target.value)}
                placeholder="https://github.com/owner/repo1&#10;https://gitee.com/owner/repo2&#10;https://github.com/owner/repo3"
                rows={6}
                disabled={loading}
              />
              <div className="repos-actions">
                <Button onClick={useTestRepo} disabled={loading}>
                  use_test_repo
                </Button>

                <Button
                  type="primary"
                  size="large"
                  onClick={handleSubmit}
                  loading={loading}
                  disabled={loading}
                  icon={loading ? <LoadingOutlined /> : <GithubOutlined />}
                >
                  {loading ? 'Processing...' : 'Analyze'}
                </Button>
              </div>
            </div>
          </div>

          {error && (
            <Alert
              message={error}
              type="error"
              closable
              onClose={() => setError('')}
              style={{ marginTop: 16 }}
            />
          )}

          <Alert
            style={{ marginTop: 16 }}
            type="info"
            showIcon
            message="Instructions"
            description={
              <ul className="repos-instructions">
                <li>Enter between 2 and 5 GitHub/Gitee repository URLs</li>
                <li>Each URL should be on a separate line</li>
                <li>Supports HTTPS format: https://github.com/owner/repo or https://gitee.com/owner/repo</li>
                <li>Click Analyze to extract commit data and find common contributors</li>
                <li>Existing repositories will be skipped automatically</li>
              </ul>
            }
          />
        </Card>

        {loading && (
          <Card className="repos-loading-card">
            <LoadingOutlined className="repos-loading-icon" />
            <h3>
              {loadingCommon ? 'Finding Common Contributors...' : 'Extracting Repository Data...'}
            </h3>
            <p>
              {loadingCommon
                ? 'Analyzing contributors across repositories...'
                : 'This may take a few minutes. Please wait while we fetch commits and files from GitHub.'}
            </p>
          </Card>
        )}

        {results && (
          <Card
            title={
              <div className="repos-section-title">
                <GithubOutlined />
                <span>Extraction Results</span>
              </div>
            }
            className="repos-card"
          >
            <div className="repos-summary-row">
              <Space size="large" wrap>
                <div><span className="repos-summary-label">Total:</span> <span className="repos-summary-value">{results.summary.total}</span></div>
                <div><span className="repos-summary-label">Extracted:</span> <span className="repos-summary-value repos-good">{results.summary.extracted}</span></div>
                <div><span className="repos-summary-label">Skipped:</span> <span className="repos-summary-value repos-warn">{results.summary.skipped}</span></div>
                <div><span className="repos-summary-label">Failed:</span> <span className="repos-summary-value repos-bad">{results.summary.failed}</span></div>
              </Space>
            </div>

            <Table
              columns={columns}
              dataSource={results.results}
              rowKey="url"
              pagination={false}
            />
          </Card>
        )}

        {commonContributors && commonContributors.common_contributors.length > 0 && (
          <>
            <Card
              title={
                <div className="repos-section-title">
                  <TeamOutlined />
                  <span>Common Contributors</span>
                  <Tag color="purple" style={{ marginLeft: 12 }}>
                    {commonContributors.summary.total_common_contributors} Found
                  </Tag>
                </div>
              }
              className="repos-card"
            >
              <div style={{ marginBottom: 12, color: '#666' }}>
                Contributors who have committed to <strong>2 or more</strong> of the analyzed repositories
              </div>

              <Table
                columns={contributorColumns}
                dataSource={commonContributors.common_contributors}
                rowKey="author"
                pagination={{ pageSize: 10 }}
              />
            </Card>

            <Card
              title={
                <div className="repos-compare-title">
                  <div className="repos-compare-left">
                    <span className="repos-compare-label">Select Contributor to Compare:</span>
                    <Select
                      value={selectedContributor}
                      onChange={setSelectedContributor}
                      style={{ width: 320 }}
                      size="large"
                    >
                      {commonContributors.common_contributors.map(contributor => (
                        <Select.Option key={contributor.author} value={contributor.author}>
                          {contributor.author} ({contributor.total_commits} commits)
                        </Select.Option>
                      ))}
                    </Select>
                  </div>
                  {comparisonData && selectedContributor && (
                    <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownloadPDF}>
                      Download PDF
                    </Button>
                  )}
                </div>
              }
              className="repos-card"
            >
              <div style={{ color: '#666', fontSize: 14 }}>
                Compare the selected contributor&apos;s six-dimensional capability scores across all repositories
              </div>
            </Card>

            {selectedContributor && (
              <ContributorComparison
                data={comparisonData}
                loading={loadingComparison}
                error={comparisonData === null && !loadingComparison ? 'Failed to load comparison data' : undefined}
              />
            )}
          </>
        )}

        {commonContributors && commonContributors.common_contributors.length === 0 && (
          <Card className="repos-empty-card">
            <TeamOutlined className="repos-empty-icon" />
            <h3>No Common Contributors Found</h3>
            <p>
              {commonContributors.message || 'The analyzed repositories do not have any contributors in common.'}
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
