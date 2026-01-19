'use client';

import { useState, useEffect } from 'react';
import { Input, Button, Card, Alert, Table, Tag, Space, message, Avatar, Collapse, Select, AutoComplete } from 'antd';
import { GithubOutlined, CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined, LoadingOutlined, UserOutlined, TeamOutlined, DownloadOutlined } from '@ant-design/icons';
import ContributorComparison from '../../components/ContributorComparison';
import { exportMultiRepoPDF } from '../../utils/pdfExport';

const { TextArea } = Input;

const API_SERVER_URL = process.env.NEXT_PUBLIC_API_SERVER_URL || 'http://localhost:8000';
const REPO_URLS_STORAGE_KEY = 'github_repo_urls_history';

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

interface ContributorComparisonData {
  success: boolean;
  contributor: string;
  comparisons: Array<{
    repo: string;
    owner: string;
    repo_name: string;
    scores: any;
    total_commits: number;
    cached: boolean;
  }>;
  dimension_keys: string[];
  dimension_names: string[];
  aggregate: any;
  failed_repos?: Array<{ repo: string; reason: string }>;
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
  const [autocompleteOptions, setAutocompleteOptions] = useState<string[]>([]);

  // Load saved URLs from localStorage on mount
  useEffect(() => {
    const savedUrls = localStorage.getItem(REPO_URLS_STORAGE_KEY);
    if (savedUrls) {
      try {
        const urls = JSON.parse(savedUrls);
        setAutocompleteOptions(urls);
      } catch (e) {
        console.error('Failed to load saved URLs:', e);
      }
    }
  }, []);

  // Save URLs to localStorage
  const saveUrlsToHistory = (urls: string[]) => {
    try {
      // Get existing history
      const savedUrls = localStorage.getItem(REPO_URLS_STORAGE_KEY);
      let existingUrls: string[] = [];
      if (savedUrls) {
        existingUrls = JSON.parse(savedUrls);
      }

      // Add new URLs and remove duplicates
      const updatedUrls = Array.from(new Set([...urls, ...existingUrls]));

      // Keep only the last 20 URLs
      const limitedUrls = updatedUrls.slice(0, 20);

      localStorage.setItem(REPO_URLS_STORAGE_KEY, JSON.stringify(limitedUrls));
      setAutocompleteOptions(limitedUrls);
    } catch (e) {
      console.error('Failed to save URLs to history:', e);
    }
  };

  const generateAvatarUrl = (author: string) => {
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(author)}&background=1E40AF&color=FFFFFF&size=128&bold=true`;
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
    } catch (error) {
      message.destroy();
      message.error('Failed to generate PDF report');
      console.error('PDF generation error:', error);
    }
  };

  // Function to compare a specific contributor
  const compareContributor = async (contributorName: string, reposToCompare: Array<{owner: string, repo: string}>) => {
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

    } catch (err: any) {
      console.error('Failed to compare contributor:', err.message);
      message.error(`Failed to compare ${contributorName}: ${err.message}`);
    } finally {
      setLoadingComparison(false);
    }
  };

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
  }, [selectedContributor]);

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

    // Save URLs to history
    saveUrlsToHistory(urls);

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

    } catch (err: any) {
      setError(err.message || 'Failed to extract repositories');
      message.error('Failed to extract repositories');
    } finally {
      setLoading(false);
    }
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
          <div style={{ fontWeight: '600', color: '#1E40AF' }}>
            {record.owner && record.repo ? `${record.owner}/${record.repo}` : 'Invalid URL'}
          </div>
          <div style={{ fontSize: '12px', color: '#9CA3AF', marginTop: '4px' }}>
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
        <span style={{ color: '#6B7280' }}>{message}</span>
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
            <div style={{ fontWeight: '600', color: '#111827' }}>{record.author}</div>
            <div style={{ fontSize: '12px', color: '#9CA3AF' }}>{record.email}</div>
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
        <span style={{ color: '#1E40AF', fontWeight: '700', fontSize: '16px' }}>
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
              <span style={{ color: '#0891B2', fontWeight: '600' }}>
                {repo.owner}/{repo.repo}
              </span>
              <span style={{ color: '#6B7280', marginLeft: '8px' }}>
                {repo.commits} commits
              </span>
            </div>
          ))}
        </div>
      ),
    },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      background: '#FFFFFF',
      padding: '32px 24px',
      color: '#111827'
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ marginBottom: '40px', textAlign: 'center' }}>
          <h1 style={{
            fontSize: '32px',
            fontWeight: '700',
            color: '#111827',
            marginBottom: '10px',
            letterSpacing: '-0.02em'
          }}>
            Multi-Repository Analysis
          </h1>
          <p style={{ color: '#6B7280', fontSize: '16px', lineHeight: '1.6' }}>
            Extract commit data and find common contributors across 2-5 GitHub repositories
          </p>
        </div>

        <Card
          style={{
            background: '#FFFFFF',
            border: '1px solid #E5E7EB',
            borderRadius: '12px',
            marginBottom: '24px',
            boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)'
          }}
        >
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '10px',
              color: '#111827',
              fontSize: '14px',
              fontWeight: '600'
            }}>
              <GithubOutlined style={{ marginRight: '8px' }} />
              Repository URLs (2-5 URLs, one per line)
            </label>

            <div style={{ display: 'flex', gap: '12px' }}>
              <AutoComplete
                value={repoUrls}
                onChange={setRepoUrls}
                options={autocompleteOptions.map(url => ({ value: url }))}
                style={{ flex: 1 }}
                disabled={loading}
                filterOption={(inputValue, option) => {
                  if (!option?.value) return false;
                  // Get the current line being typed
                  const lines = inputValue.split('\n');
                  const currentLine = lines[lines.length - 1];
                  // Filter based on the current line
                  return option.value.toLowerCase().includes(currentLine.toLowerCase());
                }}
              >
                <TextArea
                  placeholder="https://github.com/owner/repo1&#10;https://github.com/owner/repo2&#10;https://github.com/owner/repo3"
                  rows={6}
                  style={{
                    background: '#F9FAFB',
                    border: '1px solid #E5E7EB',
                    color: '#111827',
                    borderRadius: '8px',
                    fontSize: '14px',
                    fontFamily: "'JetBrains Mono', monospace"
                  }}
                />
              </AutoComplete>
              <Button
                type="primary"
                size="large"
                onClick={handleSubmit}
                loading={loading}
                disabled={loading}
                icon={loading ? <LoadingOutlined /> : <GithubOutlined />}
                style={{
                  height: 'auto',
                  background: loading ? '#9CA3AF' : '#1E40AF',
                  border: 'none',
                  color: '#FFFFFF',
                  fontWeight: '600',
                  borderRadius: '8px',
                  padding: '12px 24px'
                }}
              >
                {loading ? 'Processing...' : 'Analyze'}
              </Button>
            </div>
          </div>

          {error && (
            <Alert
              message={error}
              type="error"
              closable
              onClose={() => setError('')}
              style={{
                background: '#FEF2F2',
                border: '1px solid #FCA5A5',
                borderRadius: '8px',
                color: '#DC2626',
                marginTop: '15px'
              }}
            />
          )}

          <div style={{
            marginTop: '20px',
            padding: '16px',
            background: '#F9FAFB',
            border: '1px solid #E5E7EB',
            borderRadius: '8px',
            color: '#6B7280',
            fontSize: '13px'
          }}>
            <strong style={{ color: '#111827' }}>Instructions:</strong>
            <ul style={{ marginTop: '8px', marginBottom: '0', paddingLeft: '20px' }}>
              <li>Enter between 2 and 5 GitHub repository URLs</li>
              <li>Each URL should be on a separate line</li>
              <li>Supports HTTPS format: https://github.com/owner/repo</li>
              <li>Click Analyze to extract commit data and find common contributors</li>
              <li>Existing repositories will be skipped automatically</li>
            </ul>
          </div>
        </Card>

        {loading && (
          <Card style={{
            background: '#FFFFFF',
            border: '1px solid #E5E7EB',
            borderRadius: '12px',
            marginBottom: '24px',
            textAlign: 'center',
            boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)'
          }}>
            <LoadingOutlined style={{ fontSize: '48px', color: '#1E40AF', marginBottom: '20px' }} />
            <h3 style={{ color: '#111827', marginBottom: '10px', fontWeight: '600' }}>
              {loadingCommon ? 'Finding Common Contributors...' : 'Extracting Repository Data...'}
            </h3>
            <p style={{ color: '#6B7280', lineHeight: '1.6' }}>
              {loadingCommon
                ? 'Analyzing contributors across repositories...'
                : 'This may take a few minutes. Please wait while we fetch commits and files from GitHub.'}
            </p>
          </Card>
        )}

        {results && (
          <Card
            title={
              <div style={{ color: '#111827', fontSize: '18px', fontWeight: '600' }}>
                <GithubOutlined style={{ marginRight: '8px' }} />
                Extraction Results
              </div>
            }
            style={{
              background: '#FFFFFF',
              border: '1px solid #E5E7EB',
              borderRadius: '12px',
              marginBottom: '24px',
              boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)'
            }}
            headStyle={{
              background: '#F9FAFB',
              border: 'none',
              borderBottom: '1px solid #E5E7EB'
            }}
          >
            <div style={{ marginBottom: '20px' }}>
              <Space size="large">
                <div>
                  <span style={{ color: '#6B7280' }}>Total: </span>
                  <span style={{ color: '#111827', fontWeight: '700', fontSize: '18px' }}>
                    {results.summary.total}
                  </span>
                </div>
                <div>
                  <span style={{ color: '#6B7280' }}>Extracted: </span>
                  <span style={{ color: '#059669', fontWeight: '700', fontSize: '18px' }}>
                    {results.summary.extracted}
                  </span>
                </div>
                <div>
                  <span style={{ color: '#6B7280' }}>Skipped: </span>
                  <span style={{ color: '#D97706', fontWeight: '700', fontSize: '18px' }}>
                    {results.summary.skipped}
                  </span>
                </div>
                <div>
                  <span style={{ color: '#6B7280' }}>Failed: </span>
                  <span style={{ color: '#DC2626', fontWeight: '700', fontSize: '18px' }}>
                    {results.summary.failed}
                  </span>
                </div>
              </Space>
            </div>

            <Table
              columns={columns}
              dataSource={results.results}
              rowKey="url"
              pagination={false}
              style={{
                background: '#FFFFFF'
              }}
            />
          </Card>
        )}

        {commonContributors && commonContributors.common_contributors.length > 0 && (
          <>
            <Card
              title={
                <div style={{ color: '#111827', fontSize: '20px', fontWeight: '600' }}>
                  <TeamOutlined style={{ marginRight: '8px' }} />
                  Common Contributors
                  <Tag
                    color="purple"
                    style={{ marginLeft: '12px', fontSize: '14px', padding: '4px 12px' }}
                  >
                    {commonContributors.summary.total_common_contributors} Found
                  </Tag>
                </div>
              }
              style={{
                background: '#FFFFFF',
                border: '1px solid #0891B2',
                borderRadius: '12px',
                marginBottom: '24px',
                boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)'
              }}
              headStyle={{
                background: 'rgba(8, 145, 178, 0.05)',
                border: 'none',
                borderBottom: '1px solid #0891B2'
              }}
            >
              <div style={{ marginBottom: '20px', color: '#6B7280', lineHeight: '1.6' }}>
                Contributors who have committed to <strong style={{ color: '#111827' }}>2 or more</strong> of the analyzed repositories
              </div>

              <Table
                columns={contributorColumns}
                dataSource={commonContributors.common_contributors}
                rowKey="author"
                pagination={{ pageSize: 10 }}
                style={{
                  background: '#FFFFFF'
                }}
              />
            </Card>

            {/* Contributor Selector */}
            <Card
              title={
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <span style={{ color: '#111827', fontSize: '18px', fontWeight: '600' }}>
                      Select Contributor to Compare:
                    </span>
                    <Select
                      value={selectedContributor}
                      onChange={setSelectedContributor}
                      style={{ width: 300 }}
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
                    <Button
                      type="primary"
                      icon={<DownloadOutlined />}
                      onClick={handleDownloadPDF}
                      style={{
                        background: '#0891B2',
                        borderColor: '#0891B2',
                        color: '#FFFFFF',
                        fontWeight: '600'
                      }}
                    >
                      Download PDF
                    </Button>
                  )}
                </div>
              }
              style={{
                background: '#FFFFFF',
                border: '1px solid #E5E7EB',
                borderRadius: '12px',
                marginBottom: '24px',
                boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)'
              }}
              headStyle={{
                background: '#F9FAFB',
                border: 'none',
                borderBottom: '1px solid #E5E7EB'
              }}
            >
              <div style={{ color: '#6B7280', fontSize: '14px', lineHeight: '1.6' }}>
                Compare the selected contributor's six-dimensional capability scores across all repositories
              </div>
            </Card>

            {/* Comparison Visualization */}
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
          <Card style={{
            background: '#FFFFFF',
            border: '1px solid #E5E7EB',
            borderRadius: '12px',
            textAlign: 'center',
            boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)'
          }}>
            <TeamOutlined style={{ fontSize: '48px', color: '#9CA3AF', marginBottom: '20px' }} />
            <h3 style={{ color: '#111827', marginBottom: '10px', fontWeight: '600' }}>No Common Contributors Found</h3>
            <p style={{ color: '#6B7280', lineHeight: '1.6' }}>
              {commonContributors.message || 'The analyzed repositories do not have any contributors in common.'}
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
