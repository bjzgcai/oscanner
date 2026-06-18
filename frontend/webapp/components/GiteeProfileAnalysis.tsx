"use client";

import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  InputNumber,
  Space,
  Steps,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  ApiOutlined,
  BranchesOutlined,
  CodeOutlined,
  FileSearchOutlined,
  GitlabOutlined,
  SearchOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { getApiBaseUrl } from "../utils/apiBase";
import { useAppSettings } from "./AppSettingsContext";
import PluginViewRenderer from "./PluginViewRenderer";

const { Title, Paragraph, Text } = Typography;

const DEFAULT_PROFILE = "https://gitee.com/wu-yanbiao";
const DEFAULT_COMMIT_LIMIT = 10;
const MAX_COMMIT_LIMIT = 100;
const USERNAME_RE = /^[A-Za-z0-9_.-]+$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

interface AnalysisCommit {
  platform: string;
  repo_full_name: string;
  repo_url: string;
  sha: string;
  short_sha: string;
  title: string;
  author: string;
  matched_identity: string;
  matched_email?: string;
  matched_roles?: Array<{
    role: string;
    email: string;
    name?: string;
    date?: string;
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
}

interface AnalysisResult {
  success: boolean;
  username: string;
  scope: string;
  repos_scanned: number;
  matched_repos: Array<{
    platform: string;
    repo_full_name: string;
    repo_url: string;
    commit_count?: number;
    mode?: string;
  }>;
  summary: {
    repo_count: number;
    matched_repo_count: number;
    commit_count: number;
    available_commit_count: number;
    collaboration_evidence_count: number;
    commit_limit: number;
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

interface StreamEvent {
  event: string;
  data: unknown;
}

function splitOptionalEmails(value: string): { emails: string[]; error: string } {
  const trimmed = value.trim();
  if (!trimmed) {
    return { emails: [], error: "" };
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
  return { emails: Array.from(new Set(parts.map((item) => item.toLowerCase()))), error: "" };
}

function parseGiteeProfile(value: string): {
  username: string;
  repoUrl: string;
  mode: "profile" | "repo";
  error: string;
} {
  const trimmed = value.trim();
  if (!trimmed) {
    return { username: "", repoUrl: "", mode: "profile", error: "请输入 Gitee 个人主页 URL、用户名或仓库 URL。" };
  }

  if (!/^https?:\/\//i.test(trimmed) && !trimmed.includes("/")) {
    if (!USERNAME_RE.test(trimmed)) {
      return { username: "", repoUrl: "", mode: "profile", error: "Gitee 用户名只能包含字母、数字、下划线、点和短横线。" };
    }
    return { username: trimmed, repoUrl: "", mode: "profile", error: "" };
  }

  const rawUrl = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return { username: "", repoUrl: "", mode: "profile", error: "请输入有效的 Gitee URL。" };
  }

  const hostname = parsed.hostname.toLowerCase();
  if (hostname !== "gitee.com" && hostname !== "www.gitee.com") {
    return { username: "", repoUrl: "", mode: "profile", error: "当前页面只支持 gitee.com URL。" };
  }

  const parts = parsed.pathname.split("/").filter(Boolean);
  if (parts.length === 1 && USERNAME_RE.test(parts[0])) {
    return { username: parts[0], repoUrl: "", mode: "profile", error: "" };
  }
  if (parts.length >= 2 && USERNAME_RE.test(parts[0]) && USERNAME_RE.test(parts[1])) {
    return {
      username: parts[0],
      repoUrl: `https://gitee.com/${parts[0]}/${parts[1].replace(/\.git$/i, "")}`,
      mode: "repo",
      error: "",
    };
  }
  if (parts.length !== 1 || !USERNAME_RE.test(parts[0])) {
    return {
      username: "",
      repoUrl: "",
      mode: "profile",
      error: "请输入个人主页或仓库 URL，例如 https://gitee.com/owner/repo。",
    };
  }

  return { username: parts[0], repoUrl: "", mode: "profile", error: "" };
}

function parseSseFrame(frame: string): StreamEvent {
  let event = "message";
  const dataLines: string[] = [];

  frame.split(/\r?\n/).forEach((line) => {
    if (!line || line.startsWith(":")) return;
    if (line.startsWith("event:")) {
      event = line.slice(6).trim() || "message";
      return;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  });

  const dataText = dataLines.join("\n");
  let data: unknown = dataText;
  if (dataText) {
    try {
      data = JSON.parse(dataText);
    } catch {
      data = dataText;
    }
  }
  return { event, data };
}

function parseSseBuffer(buffer: string): { events: StreamEvent[]; remaining: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const remaining = parts.pop() ?? "";
  return {
    events: parts.filter((part) => part.trim()).map(parseSseFrame),
    remaining,
  };
}

function streamDataObject(data: unknown): Record<string, unknown> {
  return data && typeof data === "object" ? (data as Record<string, unknown>) : {};
}

async function readResponseError(response: Response): Promise<never> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.toLowerCase().includes("application/json")) {
    const data = await response.json().catch(() => null);
    const detail = data?.detail || data?.message;
    throw new Error(detail ? String(detail) : `请求失败 (${response.status})`);
  }
  const text = await response.text().catch(() => "");
  throw new Error(text || `请求失败 (${response.status})`);
}

function formatDate(value: string) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    commit_diffs: "Commit Diff",
    pr_discussions: "PR 讨论",
    review_comments: "评审评论",
    issue_triage: "Issue 处理",
    approvals: "评审/测试",
    maintainer_decisions: "维护决策",
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
        height={42}
        rx={6}
        fill={fill}
        stroke="#d9d9d9"
      />
      <text
        x={x + width / 2}
        y={y + 26}
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
  label,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
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
        markerEnd="url(#gitee-flow-arrow)"
      />
      {label && (
        <text
          x={midX}
          y={midY - 7}
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

function GiteeCollectionFlowSvg() {
  return (
    <svg
      viewBox="0 0 960 430"
      role="img"
      aria-label="Gitee profile repository and commit collection flow"
      style={{ width: "100%", minWidth: 820, display: "block" }}
    >
      <title>Gitee profile repository and commit collection flow</title>
      <defs>
        <marker
          id="gitee-flow-arrow"
          markerWidth="8"
          markerHeight="8"
          refX="7"
          refY="4"
          orient="auto"
        >
          <path d="M0,0 L8,4 L0,8 Z" fill="#8c8c8c" />
        </marker>
      </defs>

      <FlowNode x={24} y={120} width={132} label="Profile URL" fill="#e6fffb" />
      <FlowNode x={210} y={54} width={146} label="GET /users/{u}" fill="#f6ffed" />
      <FlowNode x={210} y={186} width={174} label="GET /users/{u}/repos" fill="#fff7e6" />
      <FlowNode x={456} y={120} width={168} label="Profile repo inventory" fill="#f0f5ff" />
      <FlowNode x={690} y={18} width={176} label="commits?author={u}" fill="#f9f0ff" />
      <FlowNode x={690} y={86} width={176} label="commit details/diffs" fill="#fffbe6" />
      <FlowNode x={690} y={154} width={176} label="pulls + PR details" fill="#fff1f0" />
      <FlowNode x={690} y={222} width={176} label="PR comments/logs" fill="#f6ffed" />
      <FlowNode x={690} y={290} width={176} label="issues + triage" fill="#e6f4ff" />
      <FlowNode x={456} y={348} width={168} label="Plugin evaluation" fill="#f6ffed" />
      <FlowNode x={690} y={348} width={176} label="Skill report" fill="#e6fffb" />

      <FlowArrow x1={156} y1={132} x2={210} y2={75} label="username" />
      <FlowArrow x1={156} y1={145} x2={210} y2={208} label="username" />
      <FlowArrow x1={356} y1={75} x2={456} y2={133} label="metadata" />
      <FlowArrow x1={384} y1={208} x2={456} y2={149} label="type=all" />
      <FlowArrow x1={624} y1={132} x2={690} y2={39} label="per repo" />
      <FlowArrow x1={624} y1={138} x2={690} y2={107} label="SHA detail" />
      <FlowArrow x1={624} y1={144} x2={690} y2={175} label="author/reviewer" />
      <FlowArrow x1={624} y1={151} x2={690} y2={243} label="comments" />
      <FlowArrow x1={624} y1={157} x2={690} y2={311} label="creator/assignee" />
      <FlowArrow x1={778} y1={128} x2={540} y2={348} label="code evidence" />
      <FlowArrow x1={778} y1={264} x2={540} y2={348} label="collaboration" />
      <FlowArrow x1={624} y1={369} x2={690} y2={369} label="score" />

      <text x={24} y={388} fontSize={12} fill="#595959">
        Profile mode only uses repositories returned by /api/v5/users/USERNAME/repos.
      </text>
      <text x={24} y={408} fontSize={12} fill="#595959">
        Commits, PRs, issues, comments, and operation logs are collected repository by repository.
      </text>
    </svg>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre
      style={{
        margin: 0,
        padding: 16,
        overflowX: "auto",
        background: "#111827",
        color: "#f9fafb",
        borderRadius: 8,
        fontSize: 13,
        lineHeight: 1.6,
      }}
    >
      <code>{children}</code>
    </pre>
  );
}

export default function GiteeProfileAnalysis() {
  const { model, pluginId, locale } = useAppSettings();
  const [profileText, setProfileText] = useState(DEFAULT_PROFILE);
  const [emailsText, setEmailsText] = useState("");
  const [commitLimit, setCommitLimit] = useState<number | null>(DEFAULT_COMMIT_LIMIT);
  const [submittedUsername, setSubmittedUsername] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progressText, setProgressText] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const apiBase = getApiBaseUrl();

  const validation = useMemo(() => parseGiteeProfile(profileText), [profileText]);
  const emailValidation = useMemo(() => splitOptionalEmails(emailsText), [emailsText]);
  const canSubmit = !loading && profileText.trim().length > 0 && !validation.error && !emailValidation.error;
  const username = submittedUsername || validation.username;
  const profileUrl = validation.mode === "repo" ? validation.repoUrl : username ? `https://gitee.com/${username}` : "";
  const reposEndpoint = username
    ? `https://gitee.com/api/v5/users/${username}/repos`
    : "https://gitee.com/api/v5/users/USERNAME/repos";

  const evaluate = async () => {
    const parsed = parseGiteeProfile(profileText);
    if (parsed.error) {
      setError(parsed.error);
      return;
    }
    const parsedEmails = splitOptionalEmails(emailsText);
    if (parsedEmails.error) {
      setError(parsedEmails.error);
      return;
    }

    const normalizedLimit = Math.min(
      MAX_COMMIT_LIMIT,
      Math.max(1, commitLimit ?? DEFAULT_COMMIT_LIMIT),
    );

    setLoading(true);
    setError("");
    setSubmittedUsername(parsed.username);
    setProgressText(parsed.mode === "repo" ? "准备 Gitee 仓库评估..." : "准备 Gitee 个人仓库评估...");
    setResult(null);

    try {
      const response = await fetch(`${apiBase}/api/gitee/profile/evaluate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          username: parsed.username,
          repo_url: parsed.repoUrl || undefined,
          emails: parsed.mode === "repo" ? parsedEmails.emails.join(",") : undefined,
          commit_limit: normalizedLimit,
          model,
          plugin: pluginId,
          language: locale,
        }),
      });
      if (!response.ok) {
        await readResponseError(response);
      }
      if (!response.body) {
        throw new Error("当前浏览器不支持流式响应读取");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult: AnalysisResult | null = null;

      const handleEvent = ({ event, data }: StreamEvent) => {
        const eventData = streamDataObject(data);
        if (event === "section" && eventData.title) {
          const suffix =
            eventData.status === "done"
              ? "完成"
              : eventData.status === "running"
                ? "..."
                : "";
          setProgressText(`${String(eventData.title)}${suffix}`);
          return;
        }
        if (event === "result") {
          finalResult = data as AnalysisResult;
          setResult(finalResult);
          return;
        }
        if (event === "error") {
          throw new Error(String(eventData.message || "评估失败"));
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parsedBuffer = parseSseBuffer(buffer);
        buffer = parsedBuffer.remaining;
        parsedBuffer.events.forEach(handleEvent);
      }

      buffer += decoder.decode();
      if (buffer.trim()) {
        parseSseBuffer(`${buffer}\n\n`).events.forEach(handleEvent);
      }

      if (!finalResult?.success) {
        throw new Error("评估失败");
      }
      message.success("评估完成");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setProgressText("");
    }
  };

  const commitColumns: ColumnsType<AnalysisCommit> = [
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
      title: "匹配邮箱",
      dataIndex: "matched_email",
      width: 220,
      render: (email: string | undefined) => email ? <Tag>{email}</Tag> : <Text type="secondary">-</Text>,
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
          <Text type="secondary">{record.author || record.matched_identity || "-"}</Text>
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
      width: 150,
      render: (source: string) => <Tag>{sourceLabel(source)}</Tag>,
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
              {label || record.url}
            </a>
          ) : (
            <Text>{label || "-"}</Text>
          )}
          {record.detail && <Text type="secondary">{record.detail}</Text>}
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
            Gitee 个人所有仓库分析
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            输入 Gitee 个人主页会分析个人所有仓库；输入 Gitee 仓库 URL 时只采集该仓库，
            并按邮箱匹配 commit author/committer。
          </Paragraph>
        </div>

        <Card>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Space.Compact style={{ width: "100%" }}>
              <Input
                size="large"
                value={profileText}
                prefix={<UserOutlined />}
                placeholder="https://gitee.com/username、username 或 https://gitee.com/owner/repo"
                status={profileText && validation.error ? "error" : undefined}
                onChange={(event) => {
                  setProfileText(event.target.value);
                  setError("");
                }}
                onPressEnter={evaluate}
              />
              <InputNumber
                size="large"
                min={1}
                max={MAX_COMMIT_LIMIT}
                value={commitLimit}
                onChange={setCommitLimit}
                style={{ width: 140 }}
                addonBefore="Commit"
              />
              <Button
                size="large"
                type="primary"
                icon={<SearchOutlined />}
                disabled={!canSubmit}
                loading={loading}
                onClick={evaluate}
              >
                {validation.mode === "repo" ? "Gitee 单仓库分析" : "Gitee 个人所有仓库分析"}
              </Button>
            </Space.Compact>
            {validation.mode === "repo" && (
              <Input
                size="large"
                value={emailsText}
                placeholder="仓库模式按邮箱匹配，多个邮箱用英文逗号分隔；留空则不会匹配 commit"
                status={emailsText && emailValidation.error ? "error" : undefined}
                onChange={(event) => {
                  setEmailsText(event.target.value);
                  setError("");
                }}
                onPressEnter={evaluate}
              />
            )}
            {progressText && <Alert type="info" showIcon message={progressText} />}
            {profileText && validation.error && (
              <Text type="danger">{validation.error}</Text>
            )}
            {emailsText && emailValidation.error && (
              <Text type="danger">{emailValidation.error}</Text>
            )}
            {username && (
              <Space size={8} wrap>
                <Tag color="green" icon={<GitlabOutlined />}>
                  {validation.mode === "repo" ? "仓库模式" : username}
                </Tag>
                <a href={profileUrl} target="_blank" rel="noreferrer">
                  {profileUrl}
                </a>
              </Space>
            )}
          </Space>
        </Card>

        {error && <Alert type="error" showIcon message={error} />}

        {result && (
          <Space direction="vertical" size={24} style={{ width: "100%" }}>
            <Card>
              <Space size={32} wrap>
                <Statistic title="扫描仓库" value={result.summary.repo_count} />
                <Statistic title="命中仓库" value={result.summary.matched_repo_count} />
                <Statistic title="评估 Commit" value={result.summary.commit_count} />
                <Statistic title="可用 Commit" value={result.summary.available_commit_count} />
                <Statistic title="协作证据" value={result.summary.collaboration_evidence_count} />
              </Space>
            </Card>

            {result.limitations.length > 0 && (
              <Alert
                type="info"
                showIcon
                message="分析范围"
                description={result.limitations.join(" ")}
              />
            )}

            {result.warnings.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message="同步警告"
                description={result.warnings.slice(0, 8).join("\n")}
              />
            )}

            {result.evaluation && (
              <Card title="插件评估结果">
                <PluginViewRenderer
                  pluginId={result.evaluation.plugin || pluginId || "zgc_ai_native_2026"}
                  evaluation={result.evaluation}
                />
              </Card>
            )}

            <Card title={`最新 ${result.summary.commit_limit} 个 Commit`}>
              <Table
                rowKey={(record) => `${record.repo_full_name}:${record.sha}`}
                columns={commitColumns}
                dataSource={result.commits}
                pagination={{ pageSize: 10 }}
                scroll={{ x: 900 }}
              />
            </Card>

            <Card title="PR / Issue / 评审证据">
              <Table
                rowKey={(record, index) => `${record.source}:${record.repo_full_name}:${record.url || index}`}
                columns={evidenceColumns}
                dataSource={result.collaboration_evidence}
                pagination={{ pageSize: 10 }}
                scroll={{ x: 900 }}
              />
            </Card>
          </Space>
        )}

        <Card title="Gitee 数据采集图">
          <div style={{ overflowX: "auto" }}>
            <GiteeCollectionFlowSvg />
          </div>
        </Card>

        <Card title="采集步骤">
          <Steps
            direction="vertical"
            items={[
              {
                title: "解析个人主页",
                icon: <UserOutlined />,
                description: "从 https://gitee.com/USERNAME 提取 Gitee username/login。",
              },
              {
                title: "建立个人仓库清单",
                icon: <ApiOutlined />,
                description:
                  "只使用 /api/v5/users/USERNAME/repos?type=all 返回的仓库作为个人模式分析范围。",
              },
              {
                title: "逐仓采集提交证据",
                icon: <BranchesOutlined />,
                description:
                  "先请求 commits?author=USERNAME，再按需读取未过滤提交页并在本地匹配 author/committer 身份。",
              },
              {
                title: "拉取 commit detail 和 diff",
                icon: <FileSearchOutlined />,
                description:
                  "对命中的 SHA 拉取详情，保留文件路径、增删行、patch、message、日期和原始身份字段。",
              },
              {
                title: "采集 PR 归属、评审和合并证据",
                icon: <BranchesOutlined />,
                description:
                  "按 author、assignee、tester 采集 PR，再拉取 PR commits、files、comments、operate logs、labels、linked issues 和 merge 状态。",
              },
              {
                title: "采集 Issue、讨论和排障证据",
                icon: <FileSearchOutlined />,
                description:
                  "按 creator、assignee 采集 issues，并保存 issue comments、linked PRs、operate logs、labels、状态流转和负责人信息。",
              },
              {
                title: "进入插件评估",
                icon: <CodeOutlined />,
                description:
                  "将仓库清单、代码提交、PR/Issue 协作证据交给当前评估插件，区分强 author/PR 证据和较弱 committer/context 证据。",
              },
            ]}
          />
        </Card>

        <Card title="当前 Profile 的 API 请求预览">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert
              type="info"
              showIcon
              message="Gitee 没有 GitHub-style 全局 commit search。"
              description="个人模式必须先列出该用户自己的仓库，再在每个仓库内用 author=username 过滤提交；如果需要 committer 匹配，需要额外抓取未过滤提交页并本地匹配。"
            />
            <CodeBlock>
              {`username="${username || "USERNAME"}"

# 1. Get profile
curl -G "https://gitee.com/api/v5/users/$username" \\
  --data-urlencode "access_token=$GITEE_TOKEN"

# 2. List repositories owned by this profile
curl -G "${reposEndpoint}" \\
  --data-urlencode "access_token=$GITEE_TOKEN" \\
  --data-urlencode "type=all" \\
  --data-urlencode "page=1" \\
  --data-urlencode "per_page=100"

# 3. For each repository, collect author matches
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits" \\
  --data-urlencode "access_token=$GITEE_TOKEN" \\
  --data-urlencode "author=$username" \\
  --data-urlencode "page=1" \\
  --data-urlencode "per_page=100"

# 4. Fetch detail for each matched SHA
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits/COMMIT_SHA" \\
  --data-urlencode "access_token=$GITEE_TOKEN"

# 5. Collect pull requests authored by or assigned to the user
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/pulls" \\
  --data-urlencode "access_token=$GITEE_TOKEN" \\
  --data-urlencode "author=$username" \\
  --data-urlencode "state=all" \\
  --data-urlencode "page=1" \\
  --data-urlencode "per_page=100"

curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/pulls" \\
  --data-urlencode "access_token=$GITEE_TOKEN" \\
  --data-urlencode "assignee=$username" \\
  --data-urlencode "state=all" \\
  --data-urlencode "page=1" \\
  --data-urlencode "per_page=100"

# 6. For each relevant PR, collect collaboration detail
GET /api/v5/repos/{owner}/{repo}/pulls/{number}
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/commits
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/files
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/comments
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/operate_logs
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/issues

# 7. Collect issues created by or assigned to the user
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/issues" \\
  --data-urlencode "access_token=$GITEE_TOKEN" \\
  --data-urlencode "creator=$username" \\
  --data-urlencode "state=all" \\
  --data-urlencode "page=1" \\
  --data-urlencode "per_page=100"

curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/issues" \\
  --data-urlencode "access_token=$GITEE_TOKEN" \\
  --data-urlencode "assignee=$username" \\
  --data-urlencode "state=all" \\
  --data-urlencode "page=1" \\
  --data-urlencode "per_page=100"

# 8. For each relevant issue, collect discussion and workflow detail
GET /api/v5/repos/{owner}/{repo}/issues/{number}
GET /api/v5/repos/{owner}/{repo}/issues/{number}/comments
GET /api/v5/repos/{owner}/issues/{number}/pull_requests?repo={repo}
GET /api/v5/repos/{owner}/issues/{number}/operate_logs?repo={repo}
GET /api/v5/repos/{owner}/{repo}/issues/{number}/labels

# 9. Collect repository-level comments and filter locally by user
GET /api/v5/repos/{owner}/{repo}/issues/comments
GET /api/v5/repos/{owner}/{repo}/comments
GET /api/v5/repos/{owner}/{repo}/commits/{ref}/comments`}
            </CodeBlock>
          </Space>
        </Card>
      </Space>
    </main>
  );
}
