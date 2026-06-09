'use client';

import { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Input,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  BranchesOutlined,
  GithubOutlined,
  GitlabOutlined,
  LinkOutlined,
  MailOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { getApiBaseUrl } from '../utils/apiBase';

const { Title, Paragraph, Text } = Typography;

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

interface AnalysisCommit {
  platform: string;
  repo_full_name: string;
  repo_url: string;
  sha: string;
  short_sha: string;
  title: string;
  author: string;
  matched_email: string;
  date: string;
  url: string;
  stats: {
    additions: number;
    deletions: number;
    total: number;
    files_changed: number;
  };
}

interface CollaborationEvidence {
  source: string;
  label: string;
  detail: string;
  url?: string;
  updated_at?: string;
  platform: string;
  repo_full_name: string;
  repo_url: string;
}

interface AnalysisResult {
  success: boolean;
  emails: string[];
  scope: string;
  repos_scanned: number;
  matched_repos: Array<{
    platform: string;
    repo_full_name: string;
    repo_url: string;
  }>;
  summary: {
    matched_repo_count: number;
    commit_count: number;
    collaboration_evidence_count: number;
  };
  commits: AnalysisCommit[];
  collaboration_evidence: CollaborationEvidence[];
  warnings: string[];
  limitations: string[];
}

function splitEmails(value: string): { emails: string[]; error: string } {
  const trimmed = value.trim();
  if (!trimmed) {
    return { emails: [], error: '请输入邮箱，多个邮箱必须用英文逗号分隔。' };
  }
  if (/，|;|；|\n|\t/.test(trimmed)) {
    return { emails: [], error: '多个邮箱请只使用英文逗号 “,” 分隔。' };
  }

  const parts = trimmed.split(',').map((item) => item.trim());
  if (parts.some((item) => !item)) {
    return { emails: [], error: '邮箱之间不能出现空项，请检查逗号位置。' };
  }

  const invalid = parts.filter((item) => !EMAIL_RE.test(item));
  if (invalid.length > 0) {
    return { emails: [], error: `邮箱格式不正确：${invalid.join(', ')}` };
  }

  return {
    emails: Array.from(new Set(parts.map((item) => item.toLowerCase()))),
    error: '',
  };
}

function formatDate(value: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function platformTag(platform: string) {
  const color = platform === 'github' ? 'geekblue' : 'green';
  const icon = platform === 'github' ? <GithubOutlined /> : <GitlabOutlined />;
  return (
    <Tag color={color} icon={icon}>
      {platform}
    </Tag>
  );
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    pr_discussions: 'PR discussions',
    review_comments: 'Review comments',
    issue_triage: 'Issue triage',
    approvals: 'Approvals',
    maintainer_decisions: 'Maintainer decisions',
  };
  return labels[source] || source;
}

export default function GiteeGithubFullAnalysis() {
  const [emailsText, setEmailsText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const apiBase = getApiBaseUrl();

  const validation = useMemo(() => splitEmails(emailsText), [emailsText]);
  const canSubmit = !loading && emailsText.trim().length > 0 && !validation.error;

  const analyze = async () => {
    const parsed = splitEmails(emailsText);
    if (parsed.error) {
      setError(parsed.error);
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await fetch(`${apiBase}/api/gitee-github/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emails: parsed.emails.join(',') }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || '分析失败');
      }
      setResult(data as AnalysisResult);
      message.success('分析完成');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const commitColumns: ColumnsType<AnalysisCommit> = [
    {
      title: '平台',
      dataIndex: 'platform',
      width: 110,
      render: (platform: string) => platformTag(platform),
    },
    {
      title: '仓库',
      dataIndex: 'repo_full_name',
      width: 220,
      render: (repo: string, record) => (
        <a href={record.repo_url} target="_blank" rel="noreferrer">
          {repo}
        </a>
      ),
    },
    {
      title: '邮箱',
      dataIndex: 'matched_email',
      width: 220,
      render: (email: string) => <Tag icon={<MailOutlined />}>{email}</Tag>,
    },
    {
      title: 'Commit',
      dataIndex: 'title',
      render: (title: string, record) => (
        <Space direction="vertical" size={2}>
          <a href={record.url} target="_blank" rel="noreferrer">
            <BranchesOutlined /> {record.short_sha || record.sha.slice(0, 8)}
          </a>
          <Text>{title || '(no message)'}</Text>
          <Text type="secondary">{record.author || '-'}</Text>
        </Space>
      ),
    },
    {
      title: '变更',
      width: 160,
      render: (_, record) => (
        <Space size={4} wrap>
          <Tag color="green">+{record.stats.additions}</Tag>
          <Tag color="red">-{record.stats.deletions}</Tag>
          <Tag>{record.stats.files_changed} files</Tag>
        </Space>
      ),
    },
    {
      title: '时间',
      dataIndex: 'date',
      width: 190,
      render: formatDate,
    },
  ];

  const evidenceColumns: ColumnsType<CollaborationEvidence> = [
    {
      title: '来源',
      dataIndex: 'source',
      width: 190,
      render: (source: string) => <Tag>{sourceLabel(source)}</Tag>,
    },
    {
      title: '平台',
      dataIndex: 'platform',
      width: 110,
      render: (platform: string) => platformTag(platform),
    },
    {
      title: '仓库',
      dataIndex: 'repo_full_name',
      width: 220,
      render: (repo: string, record) => (
        <a href={record.repo_url} target="_blank" rel="noreferrer">
          {repo}
        </a>
      ),
    },
    {
      title: '证据',
      dataIndex: 'label',
      render: (label: string, record) => (
        <Space direction="vertical" size={2}>
          {record.url ? (
            <a href={record.url} target="_blank" rel="noreferrer">
              <LinkOutlined /> {label}
            </a>
          ) : (
            <Text>{label}</Text>
          )}
          <Text type="secondary">{record.detail}</Text>
        </Space>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 190,
      render: formatDate,
    },
  ];

  return (
    <main style={{ maxWidth: 1400, margin: '0 auto', padding: '32px 24px' }}>
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <div>
          <Title level={2} style={{ marginBottom: 8 }}>
            全 github/gitee评估
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            输入一个或多个邮箱，系统会在本地已收集的 GitHub/Gitee 仓库中汇总该邮箱的 commits，并拉取相关 PR、Review、Issue、审批和维护者决策证据。
          </Paragraph>
        </div>

        <Card>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              size="large"
              value={emailsText}
              prefix={<MailOutlined />}
              placeholder="alice@example.com,bob@example.com"
              status={emailsText && validation.error ? 'error' : undefined}
              onChange={(event) => {
                setEmailsText(event.target.value);
                setError('');
              }}
              onPressEnter={analyze}
            />
            <Button
              size="large"
              type="primary"
              icon={<SearchOutlined />}
              loading={loading}
              disabled={!canSubmit}
              onClick={analyze}
            >
              gitee/github全量分析
            </Button>
          </Space.Compact>
          {emailsText && validation.error && (
            <Text type="danger" style={{ display: 'block', marginTop: 8 }}>
              {validation.error}
            </Text>
          )}
        </Card>

        {error && <Alert type="error" showIcon message={error} />}

        {result && (
          <>
            <Space size={16} wrap>
              <Card>
                <Statistic title="扫描仓库" value={result.repos_scanned} />
              </Card>
              <Card>
                <Statistic title="命中仓库" value={result.summary.matched_repo_count} />
              </Card>
              <Card>
                <Statistic title="Commits" value={result.summary.commit_count} />
              </Card>
              <Card>
                <Statistic title="协作证据" value={result.summary.collaboration_evidence_count} />
              </Card>
            </Space>

            {result.limitations.length > 0 && (
              <Alert
                type="info"
                showIcon
                message="范围说明"
                description={result.limitations.join(' ')}
              />
            )}

            {result.warnings.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message="采集警告"
                description={result.warnings.slice(0, 8).join('\n')}
              />
            )}

            <Card title="Commits">
              <Table
                rowKey={(record) => `${record.platform}:${record.repo_full_name}:${record.sha}:${record.matched_email}`}
                columns={commitColumns}
                dataSource={result.commits}
                pagination={{ pageSize: 20 }}
                scroll={{ x: 1100 }}
              />
            </Card>

            <Card title="PR / Review / Issue / 决策证据">
              <Table
                rowKey={(record, index) => `${record.platform}:${record.repo_full_name}:${record.source}:${record.url || record.label}:${index}`}
                columns={evidenceColumns}
                dataSource={result.collaboration_evidence}
                pagination={{ pageSize: 20 }}
                scroll={{ x: 1000 }}
              />
            </Card>
          </>
        )}
      </Space>
    </main>
  );
}
