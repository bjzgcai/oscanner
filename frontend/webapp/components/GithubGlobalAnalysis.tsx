"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  InputNumber,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  BranchesOutlined,
  GithubOutlined,
  GitlabOutlined,
  InfoCircleOutlined,
  LinkOutlined,
  MailOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { getApiBaseUrl } from "../utils/apiBase";
import { useAppSettings } from "./AppSettingsContext";
import PluginViewRenderer from "./PluginViewRenderer";

const { Title, Paragraph, Text } = Typography;

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const DEFAULT_EMAILS_TEXT = "nkwuyanbiao@163.com";
const DEFAULT_COMMIT_LIMIT = 10;

interface AnalysisCommit {
  platform: string;
  repo_full_name: string;
  repo_url: string;
  sha: string;
  short_sha: string;
  title: string;
  author: string;
  matched_email: string;
  matched_roles?: Array<{
    role: string;
    email: string;
    name?: string;
    date?: string;
    github_login?: string;
  }>;
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
  attribution?: string;
  github_login?: string;
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
  evaluation?: {
    scores: Record<string, number | string>;
    total_commits_analyzed?: number;
    files_loaded?: number;
    commits_summary?: {
      total_additions: number;
      total_deletions: number;
      files_changed: number;
      languages: string[];
    };
    plugin?: string;
    plugin_version?: string;
    evidence_links?: Array<{
      type?: string;
      label?: string;
      url?: string;
      sha?: string;
      commit_sha?: string;
      path?: string;
    }> | null;
  };
  warnings: string[];
  limitations: string[];
}

function splitEmails(value: string): { emails: string[]; error: string } {
  const trimmed = value.trim();
  if (!trimmed) {
    return { emails: [], error: "请输入邮箱，多个邮箱必须用英文逗号分隔。" };
  }
  if (/，|;|；|\n|\t/.test(trimmed)) {
    return { emails: [], error: "多个邮箱请只使用英文逗号 “,” 分隔。" };
  }

  const parts = trimmed.split(",").map((item) => item.trim());
  if (parts.some((item) => !item)) {
    return { emails: [], error: "邮箱之间不能出现空项，请检查逗号位置。" };
  }

  const invalid = parts.filter((item) => !EMAIL_RE.test(item));
  if (invalid.length > 0) {
    return { emails: [], error: `邮箱格式不正确：${invalid.join(", ")}` };
  }

  return {
    emails: Array.from(new Set(parts.map((item) => item.toLowerCase()))),
    error: "",
  };
}

function formatDate(value: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function platformTag(platform: string) {
  const color = platform === "github" ? "geekblue" : "green";
  const icon = platform === "github" ? <GithubOutlined /> : <GitlabOutlined />;
  return (
    <Tag color={color} icon={icon}>
      {platform}
    </Tag>
  );
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    pr_discussions: "PR discussions",
    review_comments: "Review comments",
    issue_triage: "Issue triage",
    approvals: "Approvals",
    maintainer_decisions: "Maintainer decisions",
  };
  return labels[source] || source;
}

function FlowNode({
  x,
  y,
  width,
  label,
  fill,
}: {
  x: number;
  y: number;
  width: number;
  label: string;
  fill: string;
}) {
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={38}
        rx={6}
        fill={fill}
        stroke="#d9d9d9"
      />
      <text
        x={x + width / 2}
        y={y + 24}
        textAnchor="middle"
        fontSize={13}
        fill="#262626"
      >
        {label}
      </text>
    </g>
  );
}

function FlowArrow({
  x1,
  y1,
  x2,
  y2,
  markerId,
  label,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  markerId: string;
  label?: string;
}) {
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke="#8c8c8c"
        strokeWidth={1.6}
        markerEnd={`url(#${markerId})`}
      />
      {label && (
        <text
          x={midX}
          y={midY - 6}
          textAnchor="middle"
          fontSize={11}
          fill="#595959"
        >
          {label}
        </text>
      )}
    </g>
  );
}

function RelationshipDiagram({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div
      style={{
        border: "1px solid #f0f0f0",
        borderRadius: 8,
        padding: 12,
        background: "#fff",
        minWidth: 320,
        flex: "1 1 520px",
      }}
    >
      <Text strong>{title}</Text>
      <div style={{ marginTop: 8, overflowX: "auto" }}>{children}</div>
    </div>
  );
}

function EvidenceRelationshipSvg() {
  return (
    <svg
      viewBox="0 0 680 260"
      role="img"
      aria-label="PR issue review comment relationship"
      style={{ width: "100%", minWidth: 560, display: "block" }}
    >
      <title>PR issue review comment relationship</title>
      <defs>
        <marker
          id="evidence-arrow"
          markerWidth="8"
          markerHeight="8"
          refX="7"
          refY="4"
          orient="auto"
        >
          <path d="M0,0 L8,4 L0,8 Z" fill="#8c8c8c" />
        </marker>
      </defs>
      <FlowNode x={24} y={92} width={112} label="GitHub login" fill="#e6f4ff" />
      <FlowNode x={210} y={26} width={112} label="PR" fill="#f6ffed" />
      <FlowNode x={210} y={158} width={112} label="Issue" fill="#fff7e6" />
      <FlowNode x={418} y={10} width={132} label="Review" fill="#f9f0ff" />
      <FlowNode x={418} y={80} width={132} label="PR comment" fill="#fff1f0" />
      <FlowNode
        x={418}
        y={150}
        width={132}
        label="Issue comment"
        fill="#fffbe6"
      />
      <FlowNode x={418} y={214} width={132} label="Merged PR" fill="#f0f5ff" />
      <FlowArrow
        x1={136}
        y1={103}
        x2={210}
        y2={45}
        markerId="evidence-arrow"
        label="author"
      />
      <FlowArrow
        x1={136}
        y1={111}
        x2={210}
        y2={177}
        markerId="evidence-arrow"
        label="author"
      />
      <FlowArrow
        x1={322}
        y1={45}
        x2={418}
        y2={29}
        markerId="evidence-arrow"
        label="reviewed-by"
      />
      <FlowArrow
        x1={322}
        y1={45}
        x2={418}
        y2={99}
        markerId="evidence-arrow"
        label="commenter"
      />
      <FlowArrow
        x1={322}
        y1={177}
        x2={418}
        y2={169}
        markerId="evidence-arrow"
        label="commenter"
      />
      <FlowArrow
        x1={322}
        y1={45}
        x2={418}
        y2={233}
        markerId="evidence-arrow"
        label="merged-by"
      />
      <text x={24} y={244} fontSize={12} fill="#595959">
        Default evidence cap: 100 items per GitHub login per search type.
      </text>
    </svg>
  );
}

function IdentityRelationshipSvg() {
  return (
    <svg
      viewBox="0 0 680 260"
      role="img"
      aria-label="author email committer email github login email relationship"
      style={{ width: "100%", minWidth: 560, display: "block" }}
    >
      <title>Author email committer email GitHub login relationship</title>
      <defs>
        <marker
          id="identity-arrow"
          markerWidth="8"
          markerHeight="8"
          refX="7"
          refY="4"
          orient="auto"
        >
          <path d="M0,0 L8,4 L0,8 Z" fill="#8c8c8c" />
        </marker>
      </defs>
      <FlowNode x={24} y={92} width={120} label="Input email" fill="#e6f4ff" />
      <FlowNode
        x={214}
        y={42}
        width={138}
        label="author-email"
        fill="#f6ffed"
      />
      <FlowNode
        x={214}
        y={142}
        width={138}
        label="committer-email"
        fill="#fff7e6"
      />
      <FlowNode x={438} y={42} width={116} label="Commit" fill="#f0f5ff" />
      <FlowNode
        x={438}
        y={142}
        width={132}
        label="GitHub login"
        fill="#f9f0ff"
      />
      <FlowArrow
        x1={144}
        y1={103}
        x2={214}
        y2={61}
        markerId="identity-arrow"
        label="search"
      />
      <FlowArrow
        x1={144}
        y1={111}
        x2={214}
        y2={161}
        markerId="identity-arrow"
        label="search"
      />
      <FlowArrow
        x1={352}
        y1={61}
        x2={438}
        y2={61}
        markerId="identity-arrow"
        label="max 10"
      />
      <FlowArrow
        x1={352}
        y1={161}
        x2={438}
        y2={61}
        markerId="identity-arrow"
        label="max 10"
      />
      <FlowArrow
        x1={504}
        y1={80}
        x2={504}
        y2={142}
        markerId="identity-arrow"
        label="resolve"
      />
      <FlowArrow
        x1={570}
        y1={161}
        x2={634}
        y2={161}
        markerId="identity-arrow"
        label="evidence search"
      />
      <text x={24} y={226} fontSize={12} fill="#595959">
        Matching commits are deduped by SHA. GitHub login comes from visible
        author/committer user data,
      </text>
      <text x={24} y={244} fontSize={12} fill="#595959">
        after the author-email or committer-email match succeeds.
      </text>
    </svg>
  );
}

export default function GithubGlobalAnalysis() {
  const { model, pluginId, locale } = useAppSettings();
  const [emailsText, setEmailsText] = useState(DEFAULT_EMAILS_TEXT);
  const [commitLimit, setCommitLimit] = useState<number | null>(
    DEFAULT_COMMIT_LIMIT,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const apiBase = getApiBaseUrl();

  const validation = useMemo(() => splitEmails(emailsText), [emailsText]);
  const canSubmit =
    !loading && emailsText.trim().length > 0 && !validation.error;

  const evaluate = async () => {
    const parsed = splitEmails(emailsText);
    if (parsed.error) {
      setError(parsed.error);
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const maxGithubCommitsPerRole = commitLimit ?? DEFAULT_COMMIT_LIMIT;
      const response = await fetch(`${apiBase}/api/github/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          emails: parsed.emails.join(","),
          max_github_commits_per_role: maxGithubCommitsPerRole,
          model,
          plugin: pluginId,
          language: locale,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.detail || data.message || "评估失败");
      }
      setResult(data as AnalysisResult);
      message.success("评估完成");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const commitColumns: ColumnsType<AnalysisCommit> = [
    {
      title: "平台",
      dataIndex: "platform",
      width: 110,
      render: (platform: string) => platformTag(platform),
    },
    {
      title: "仓库",
      dataIndex: "repo_full_name",
      width: 220,
      render: (repo: string, record) => (
        <a href={record.repo_url} target="_blank" rel="noreferrer">
          {repo}
        </a>
      ),
    },
    {
      title: "邮箱",
      dataIndex: "matched_email",
      width: 220,
      render: (email: string) => <Tag icon={<MailOutlined />}>{email}</Tag>,
    },
    {
      title: "角色",
      dataIndex: "matched_roles",
      width: 180,
      render: (roles: AnalysisCommit["matched_roles"]) => (
        <Space size={4} wrap>
          {(roles || []).map((role) => (
            <Tag
              key={`${role.role}:${role.email}`}
              color={role.role === "author" ? "blue" : "purple"}
            >
              {role.role}
              {role.github_login ? ` @${role.github_login}` : ""}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: "Commit",
      dataIndex: "title",
      render: (title: string, record) => (
        <Space direction="vertical" size={2}>
          <a href={record.url} target="_blank" rel="noreferrer">
            <BranchesOutlined /> {record.short_sha || record.sha.slice(0, 8)}
          </a>
          <Text>{title || "(no message)"}</Text>
          <Text type="secondary">{record.author || "-"}</Text>
        </Space>
      ),
    },
    {
      title: "变更",
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
      title: "时间",
      dataIndex: "date",
      width: 190,
      render: formatDate,
    },
  ];

  const evidenceColumns: ColumnsType<CollaborationEvidence> = [
    {
      title: "来源",
      dataIndex: "source",
      width: 190,
      render: (source: string) => <Tag>{sourceLabel(source)}</Tag>,
    },
    {
      title: "平台",
      dataIndex: "platform",
      width: 110,
      render: (platform: string) => platformTag(platform),
    },
    {
      title: "仓库",
      dataIndex: "repo_full_name",
      width: 220,
      render: (repo: string, record) => (
        <a href={record.repo_url} target="_blank" rel="noreferrer">
          {repo}
        </a>
      ),
    },
    {
      title: "证据",
      dataIndex: "label",
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
          {record.github_login && (
            <Text type="secondary">GitHub: @{record.github_login}</Text>
          )}
        </Space>
      ),
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      width: 190,
      render: formatDate,
    },
  ];

  return (
    <main style={{ maxWidth: 1400, margin: "0 auto", padding: "32px 24px" }}>
      <Space direction="vertical" size={24} style={{ width: "100%" }}>
        <div>
          <Title level={2} style={{ marginBottom: 8 }}>
            GitHub 全局邮箱评估
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            输入一个或多个邮箱，系统会全局搜索 GitHub commit author/committer
            邮箱，汇总相关
            PR、Review、Issue、审批和维护者决策证据，并用当前插件完成跨仓库评估。
          </Paragraph>
        </div>

        <Card>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Space.Compact style={{ width: "100%" }}>
              <Input
                size="large"
                value={emailsText}
                prefix={<MailOutlined />}
                placeholder="alice@example.com,bob@example.com"
                status={emailsText && validation.error ? "error" : undefined}
                onChange={(event) => {
                  setEmailsText(event.target.value);
                  setError("");
                }}
                onPressEnter={evaluate}
              />
              <Button
                size="large"
                type="primary"
                icon={<SearchOutlined />}
                loading={loading}
                disabled={!canSubmit}
                onClick={evaluate}
              >
                GitHub 全局评估
              </Button>
            </Space.Compact>
            <Space align="center" wrap>
              <Space size={6} align="center">
                <Text strong>Commit 数量</Text>
                <Tooltip
                  title={
                    <span>
                      默认 10。该值按每个邮箱、每种提交角色分别限制 GitHub
                      commit 搜索数量： author-email 最多 10 条，committer-email
                      最多 10 条，之后按 SHA 去重。 PR/Issue
                      协作证据使用单独的默认上限：每个 GitHub
                      login、每类搜索最多 100 条， 包括创建/讨论的 PR、reviewed
                      PR、merged PR、创建/评论的 issue。 与命中 commit 关联的 PR
                      会额外检查 reviews/approvals；如果 10 个 commit
                      都关联同一个 PR， 当前会按 commit 关联记录展示该 PR
                      的决策/approval 证据。
                    </span>
                  }
                >
                  <InfoCircleOutlined
                    aria-label="Commit 数量说明"
                    style={{ color: "#8c8c8c" }}
                  />
                </Tooltip>
              </Space>
              <InputNumber
                size="large"
                min={1}
                max={1000}
                precision={0}
                value={commitLimit}
                onChange={(value) =>
                  setCommitLimit(typeof value === "number" ? value : null)
                }
              />
              <Text type="secondary">每个邮箱、每种角色最多采集数量</Text>
            </Space>
          </Space>
          {emailsText && validation.error && (
            <Text type="danger" style={{ display: "block", marginTop: 8 }}>
              {validation.error}
            </Text>
          )}
        </Card>

        {error && <Alert type="error" showIcon message={error} />}

        {result && (
          <>
            <Space size={16} wrap>
              <Card>
                <Statistic
                  title="GitHub 命中仓库"
                  value={result.summary.matched_repo_count}
                />
              </Card>
              <Card>
                <Statistic
                  title="评估 Commit"
                  value={
                    result.evaluation?.total_commits_analyzed ??
                    result.summary.commit_count
                  }
                />
              </Card>
              <Card>
                <Statistic
                  title="全量命中 Commit"
                  value={result.summary.commit_count}
                />
              </Card>
              <Card>
                <Statistic
                  title="协作证据"
                  value={result.summary.collaboration_evidence_count}
                />
              </Card>
            </Space>

            {result.limitations.length > 0 && (
              <Alert
                type="info"
                showIcon
                message="范围说明"
                description={result.limitations.join(" ")}
              />
            )}

            {result.warnings.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message="采集警告"
                description={result.warnings.slice(0, 8).join("\n")}
              />
            )}

            {result.evaluation && (
              <Card title="GitHub 全局评估结果">
                <PluginViewRenderer
                  pluginId={
                    result.evaluation.plugin || pluginId || "zgc_ai_native_2026"
                  }
                  evaluation={result.evaluation}
                  title="GitHub Global Evaluation"
                  repoUrl="https://github.com"
                />
              </Card>
            )}

            <Card title="Commits">
              <Table
                rowKey={(record) =>
                  `${record.platform}:${record.repo_full_name}:${record.sha}:${record.matched_email}`
                }
                columns={commitColumns}
                dataSource={result.commits}
                pagination={{ pageSize: 20 }}
                scroll={{ x: 1100 }}
              />
            </Card>

            <Card title="PR / Review / Issue / 决策证据">
              <Table
                rowKey={(record, index) =>
                  `${record.platform}:${record.repo_full_name}:${record.source}:${record.url || record.label}:${index}`
                }
                columns={evidenceColumns}
                dataSource={result.collaboration_evidence}
                pagination={{ pageSize: 20 }}
                scroll={{ x: 1000 }}
              />
            </Card>
          </>
        )}
        <Card title="采集关系图">
          <div
            style={{
              display: "flex",
              gap: 16,
              flexWrap: "wrap",
              width: "100%",
            }}
          >
            <RelationshipDiagram title="PR / Issue / Review / Comment">
              <EvidenceRelationshipSvg />
            </RelationshipDiagram>
            <RelationshipDiagram title="Email / Commit / GitHub Login">
              <IdentityRelationshipSvg />
            </RelationshipDiagram>
          </div>
        </Card>
      </Space>
    </main>
  );
}
