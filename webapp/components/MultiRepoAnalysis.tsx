'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Input, Button, Card, Table, Tag, Space, Avatar, Select, Modal, Radio } from 'antd';
import {
  GithubOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
  LoadingOutlined,
  UserOutlined,
  TeamOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { exportHomePagePDF, exportMultiRepoPDF } from '../utils/pdfExport';
import type { ContributorComparisonData } from '../types';
import { useAppSettings } from './AppSettingsContext';
import { getApiBaseUrl } from '../utils/apiBase';
import PluginViewRenderer from './PluginViewRenderer';
import PluginComparisonRenderer from './PluginComparisonRenderer';

const { TextArea } = Input;

const API_SERVER_URL = getApiBaseUrl();

interface RepoResult {
  url: string;
  owner?: string;
  repo?: string;
  platform?: string;
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
  aliases: string[];
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

export default function MultiRepoAnalysis() {
  const [repoUrls, setRepoUrls] = useState('');
  const [loading, setLoading] = useState(false);
  const { model, pluginId, useCache } = useAppSettings();
  const [mode, setMode] = useState<'single' | 'multi' | null>(null);
  const [loadingText, setLoadingText] = useState('');
  const [results, setResults] = useState<BatchResult | null>(null);
  const [commonContributors, setCommonContributors] = useState<CommonContributorsResult | null>(null);
  const [loadingCommon, setLoadingCommon] = useState(false);
  const [selectedContributor, setSelectedContributor] = useState<string>('');
  const [comparisonData, setComparisonData] = useState<ContributorComparisonData | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [llmModalOpen, setLlmModalOpen] = useState(false);
  const [llmConfigPath, setLlmConfigPath] = useState<string>('');
  const [llmMode, setLlmMode] = useState<'openrouter' | 'openai'>('openrouter');
  const [openRouterKey, setOpenRouterKey] = useState('');
  const [llmApiKey, setLlmApiKey] = useState('');
  const [llmBaseUrl, setLlmBaseUrl] = useState('');
  const [llmChatUrl, setLlmChatUrl] = useState('');
  const [llmFallbackModels, setLlmFallbackModels] = useState('');
  const [giteeToken, setGiteeToken] = useState('');
  const [giteeTokenMasked, setGiteeTokenMasked] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [githubTokenMasked, setGithubTokenMasked] = useState('');
  const [authorAliases, setAuthorAliases] = useState('');

  // Single-repo state (merged UI)
  const [singleRepo, setSingleRepo] = useState<{ platform: 'github' | 'gitee'; owner: string; repo: string; full_name: string } | null>(null);
  const [authorsData, setAuthorsData] = useState<Array<{ author: string; email: string; commits: number; avatar_url: string }>>([]);
  const [selectedAuthorIndex, setSelectedAuthorIndex] = useState<number>(-1);
  const [evaluation, setEvaluation] = useState<null | {
    scores: { [key: string]: number | string };
    total_commits_analyzed: number;
    commits_summary: { total_additions: number; total_deletions: number; files_changed: number; languages: string[] };
  }>(null);
  // Result visualization is fully handled by plugin views.

  const generateAvatarUrl = (author: string) => {
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(author)}&background=FFEB00&color=0A0A0A&size=128&bold=true`;
  };

  const parseRepoUrl = (input: string): { platform: 'github' | 'gitee'; owner: string; repo: string } | null => {
    const trimmed = (input || '').trim();
    const githubPatterns = [
      /^https?:\/\/(?:www\.)?github\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^github\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^git@github\.com:([^\/]+)\/([^\/\s]+)\.git$/i,
      /^git@github\.com:([^\/]+)\/([^\/\s]+)$/i,
    ];
    for (const pattern of githubPatterns) {
      const match = trimmed.match(pattern);
      if (match) {
        let repo = match[2];
        repo = repo.replace(/\.git$/, '');
        return { platform: 'github', owner: match[1], repo };
      }
    }
    const giteePatterns = [
      /^https?:\/\/(?:www\.)?gitee\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^gitee\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^git@gitee\.com:([^\/]+)\/([^\/\s]+)\.git$/i,
      /^git@gitee\.com:([^\/]+)\/([^\/\s]+)$/i,
    ];
    for (const pattern of giteePatterns) {
      const match = trimmed.match(pattern);
      if (match) {
        let repo = match[2];
        repo = repo.replace(/\.git$/, '');
        return { platform: 'gitee', owner: match[1], repo };
      }
    }
    return null;
  };

  const logSeqRef = useRef(0);
  const tickerQueueRef = useRef<number[]>([]);
  const tickerTimerRef = useRef<number | null>(null);
  const [logs, setLogs] = useState<Array<{ id: number; text: string; level: 'info' | 'error' }>>([]);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const logsBodyRef = useRef<HTMLDivElement | null>(null);
  const [tickerLogId, setTickerLogId] = useState<number | null>(null);
  const isExecutingRef = useRef(false);
  const llmConfiguredRef = useRef<boolean | null>(null);

  useEffect(() => {
    isExecutingRef.current = isExecuting;
  }, [isExecuting]);

  // Auto-expand Execution logs while executing so users can see step-by-step progress.
  useEffect(() => {
    if (isExecuting) setLogsExpanded(true);
  }, [isExecuting]);

  const stopTicker = useCallback(
    (pinToLatest: boolean) => {
      tickerQueueRef.current = [];
      if (tickerTimerRef.current != null) {
        window.clearInterval(tickerTimerRef.current);
        tickerTimerRef.current = null;
      }
      if (pinToLatest) {
        const latest = logs.length ? logs[logs.length - 1] : null;
        if (latest) setTickerLogId(latest.id);
      }
    },
    [logs]
  );

  const appendLog = useCallback((msg: string, level: 'info' | 'error' = 'info') => {
    const now = new Date();
    const ts = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const id = (logSeqRef.current += 1);
    const text = `[${ts}] ${msg}`;

    // If an error occurs, pin the ticker to the error immediately so collapsed view always shows it.
    // Also stop any playback so it doesn't get overwritten by later info logs like "Done.".
    if (level === 'error') {
      tickerQueueRef.current = [];
      if (tickerTimerRef.current != null) {
        window.clearInterval(tickerTimerRef.current);
        tickerTimerRef.current = null;
      }
      setTickerLogId(id);
    }

    if (isExecutingRef.current) {
      tickerQueueRef.current.push(id);
      if (tickerTimerRef.current == null) {
        tickerTimerRef.current = window.setInterval(() => {
          const nextId = tickerQueueRef.current.shift();
          if (typeof nextId === 'number') {
            setTickerLogId(nextId);
            return;
          }
          if (tickerTimerRef.current != null) {
            window.clearInterval(tickerTimerRef.current);
            tickerTimerRef.current = null;
          }
        }, 1600);
      }
    } else {
      tickerQueueRef.current = [];
      setTickerLogId(id);
    }

    setLogs((prev) => {
      const next = [...prev, { id, text, level }];
      return next.length > 200 ? next.slice(next.length - 200) : next;
    });
  }, []);

  const refreshLlmConfig = useCallback(async () => {
    try {
      const resp = await fetch(`${API_SERVER_URL}/api/config/llm`);
      if (!resp.ok) return;
      const cfg = await resp.json();
      setLlmConfigPath(String(cfg.path || ''));
      const mode = String(cfg.mode || 'openrouter') as 'openrouter' | 'openai';
      setLlmMode(mode);
      // do not hydrate secrets into inputs; keep empty
      setLlmBaseUrl(String(cfg.oscanner_llm_base_url || ''));
      setLlmChatUrl(String(cfg.oscanner_llm_chat_completions_url || ''));
      setLlmFallbackModels(String(cfg.oscanner_llm_fallback_models || ''));
      setGiteeTokenMasked(String(cfg.gitee_token_masked || ''));
      setGithubTokenMasked(String(cfg.github_token_masked || ''));
    } catch {
      // ignore
    }
  }, []);

  const saveLlmConfig = useCallback(async () => {
    try {
      const body: Record<string, unknown> =
        llmMode === 'openrouter'
          ? { mode: 'openrouter', openrouter_key: openRouterKey, model }
          : {
              mode: 'openai',
              api_key: llmApiKey,
              base_url: llmBaseUrl,
              model,
              chat_completions_url: llmChatUrl,
              fallback_models: llmFallbackModels,
            };

      // Optional platform token updates (do not overwrite if empty)
      if (giteeToken.trim()) {
        body.gitee_token = giteeToken.trim();
      }
      if (githubToken.trim()) {
        body.github_token = githubToken.trim();
      }

      const resp = await fetch(`${API_SERVER_URL}/api/config/llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        appendLog(`LLM settings save failed: ${data.detail || 'unknown error'}`, 'error');
        return;
      }
      appendLog(`LLM settings saved. Path: ${data.path}`, 'info');
      llmConfiguredRef.current = true;
      setLlmModalOpen(false);
      // clear sensitive inputs after save
      setOpenRouterKey('');
      setLlmApiKey('');
      setGiteeToken('');
      setGithubToken('');
      await refreshLlmConfig();
    } catch (e: unknown) {
      appendLog(`LLM settings save failed: ${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  }, [appendLog, giteeToken, githubToken, llmApiKey, llmBaseUrl, llmChatUrl, llmFallbackModels, llmMode, model, openRouterKey, refreshLlmConfig]);

  const tickerLine = useMemo(() => {
    if (logs.length === 0) return null;
    if (tickerLogId == null) return logs[logs.length - 1] || null;
    return logs.find((l) => l.id === tickerLogId) || logs[logs.length - 1] || null;
  }, [logs, tickerLogId]);

  const isLlmNotConfigured = (detail: unknown) => {
    const s = typeof detail === 'string' ? detail : String(detail || '');
    return s.includes('LLM not configured') || s.includes('OPEN_ROUTER_KEY not configured');
  };

  useEffect(() => {
    if (!logsExpanded) return;
    const el = logsBodyRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [logs, logsExpanded]);

  useEffect(() => {
    if (!isExecuting) stopTicker(true);
  }, [isExecuting, stopTicker]);

  useEffect(() => {
    return () => stopTicker(false);
  }, [stopTicker]);

  const handleDownloadPDF = async () => {
    if (!comparisonData || !selectedContributor) {
      appendLog('PDF export skipped: no comparison data yet.');
      return;
    }
    try {
      appendLog('Generating PDF report...');
      await exportMultiRepoPDF(comparisonData, selectedContributor);
      appendLog('PDF report downloaded.');
    } catch (e: unknown) {
      console.error('PDF generation error:', e);
      appendLog('PDF export failed.');
    }
  };

  const handleDownloadSinglePDF = async () => {
    if (!singleRepo || !evaluation || selectedAuthorIndex < 0) {
      appendLog('PDF export skipped: no single-repo evaluation yet.');
      return;
    }
    try {
      appendLog('Generating PDF report (single repo)...');
      await exportHomePagePDF(
        { owner: singleRepo.owner, repo: singleRepo.repo, full_name: singleRepo.full_name },
        authorsData[selectedAuthorIndex],
        evaluation
      );
      appendLog('PDF report downloaded.');
    } catch (e: unknown) {
      console.error('PDF generation error:', e);
      appendLog('PDF export failed.');
    }
  };

  const evaluateAuthor = useCallback(
    async (
      index: number,
      owner: string,
      repo: string,
      authorsOverride?: Array<{ author: string; email: string; commits: number; avatar_url: string }>,
      platform?: string
    ) => {
      const author = (authorsOverride && authorsOverride[index]) || authorsData[index];
      if (!author) return;
      setSelectedAuthorIndex(index);
      setLoading(true);
      setLoadingText(`Evaluating ${author.author}...`);
      appendLog(`Evaluate author: ${author.author}`);

      const platformParam = platform || singleRepo?.platform || 'github';

      // Parse author aliases and check if current author matches any
      let requestBody: { aliases?: string[] } | undefined = undefined;
      if (authorAliases.trim()) {
        const aliases = authorAliases.split(',').map(a => a.trim().toLowerCase()).filter(a => a);
        // Check if the current author matches any of the aliases
        if (aliases.includes(author.author.toLowerCase().trim())) {
          requestBody = { aliases };
          appendLog(`Using ${aliases.length} aliases: ${aliases.join(', ')}`);
        }
      }

      try {
        const response = await fetch(
          `${API_SERVER_URL}/api/evaluate/${owner}/${repo}/${encodeURIComponent(author.author)}?model=${encodeURIComponent(model)}&platform=${encodeURIComponent(platformParam)}&plugin=${encodeURIComponent(pluginId || '')}&use_cache=${useCache ? 'true' : 'false'}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: requestBody ? JSON.stringify(requestBody) : undefined
          }
        );
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const detail = (errorData as { detail?: unknown }).detail;
          if (isLlmNotConfigured(detail)) {
            throw new Error('LLM not configured: please set OPEN_ROUTER_KEY (or run oscanner init).');
          }
          throw new Error((detail as string) || 'Failed to evaluate author');
        }
        const result = await response.json();
        if (!result.success) throw new Error(result.error || 'Evaluation failed');
        setEvaluation(result.evaluation);
        appendLog('Evaluation complete.');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        appendLog(`Evaluation failed: ${msg}`, 'error');
      } finally {
        setLoading(false);
        setLoadingText('');
      }
    },
    [appendLog, authorsData, model, authorAliases, singleRepo?.platform, pluginId, useCache]
  );

  const compareContributor = useCallback(
    async (contributorName: string, reposToCompare: Array<{ owner: string; repo: string; platform?: string }>) => {
      setLoadingComparison(true);
      setComparisonData(null);
      setIsExecuting(true);
      appendLog(`Step 3/3: Comparing "${contributorName}" across ${reposToCompare.length} repositories...`);

      try {
        const response = await fetch(`${API_SERVER_URL}/api/batch/compare-contributor`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contributor: contributorName.trim(),
            repos: reposToCompare,
            model,
            plugin: pluginId || undefined,
            use_cache: useCache,
            author_aliases: authorAliases.trim() ? authorAliases : undefined,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const detail = (errorData as { detail?: unknown }).detail;
          if (isLlmNotConfigured(detail)) {
            throw new Error('LLM not configured: please set OPEN_ROUTER_KEY (or run oscanner init).');
          }
          throw new Error((detail as string) || 'Failed to compare contributor');
        }

        const data: ContributorComparisonData = await response.json();
        if (!data.success) {
          // Use the detailed message from backend if available
          const errorMessage = data.message || 'No evaluation data found';
          throw new Error(errorMessage);
        }

        setComparisonData(data);
        appendLog(`Comparison complete: ${data.comparisons.length} repos.`);
        appendLog('Done.');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        appendLog(`Comparison failed: ${msg}`, 'error');
        appendLog('Done.');
      } finally {
        setLoadingComparison(false);
        setIsExecuting(false);
      }
    },
    [appendLog, model, authorAliases, pluginId, useCache]
  );

  useEffect(() => {
    if (selectedContributor && results) {
      const reposWithData = results.results.filter((r) => r.data_exists && r.owner && r.repo);
      if (reposWithData.length >= 2) {
        const reposToCompare = reposWithData.map((r) => ({ owner: r.owner!, repo: r.repo!, platform: r.platform }));
        compareContributor(selectedContributor, reposToCompare);
      }
    }
  }, [selectedContributor, results, compareContributor, appendLog]);

  const handleSubmit = async () => {
    setMode(null);
    setSingleRepo(null);
    setAuthorsData([]);
    setSelectedAuthorIndex(-1);
    setEvaluation(null);
    setResults(null);
    setCommonContributors(null);
    setSelectedContributor('');
    setComparisonData(null);
    setLogs([]);
    setIsExecuting(true);
    appendLog('Start analysis.');

    const urls = repoUrls
      .split('\n')
      .map((url) => url.trim())
      .filter((url) => url.length > 0);

    if (urls.length < 1) {
      appendLog('Validation failed: need at least 1 repository URL.', 'error');
      setIsExecuting(false);
      return;
    }

    if (urls.length > 5) {
      appendLog('Validation failed: maximum 5 repository URLs.', 'error');
      setIsExecuting(false);
      return;
    }

    setLoading(true);

    try {
      // Preflight: check LLM config up-front so single/multi repo behave consistently.
      try {
        const statusResp = await fetch(`${API_SERVER_URL}/api/llm/status`);
        if (statusResp.ok) {
          const status = await statusResp.json();
          llmConfiguredRef.current = Boolean(status.configured);
          if (!status.configured) {
            appendLog('LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init).', 'error');
            // Auto-open settings modal for user convenience.
            setLlmModalOpen(true);
            refreshLlmConfig();
            setIsExecuting(false);
            setLoading(false);
            setLoadingText('');
            return;
          }
        }
      } catch {
        // If preflight fails, continue; downstream endpoints will return details.
      }

      // Single repo mode
      if (urls.length === 1) {
        setMode('single');
        appendLog('Mode: Single Repository');
        const parsed = parseRepoUrl(urls[0]);
        if (!parsed) {
          appendLog('Invalid repository URL. Use https://github.com/owner/repo or https://gitee.com/owner/repo', 'error');
          setIsExecuting(false);
          setLoading(false);
          setLoadingText('');
          return;
        }

        const { platform, owner, repo } = parsed;
        setLoadingText('Loading authors...');
        appendLog(`Step 1/2: Loading authors for ${platform}:${owner}/${repo}...`);

        const response = await fetch(
          `${API_SERVER_URL}/api/authors/${owner}/${repo}?platform=${encodeURIComponent(platform)}`
        );
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const detail = (errorData as { detail?: unknown }).detail;
          appendLog(`Load authors failed: ${detail || 'Failed to load authors'}`, 'error');
          setIsExecuting(false);
          setLoading(false);
          setLoadingText('');
          return;
        }
        const result = await response.json();
        const authors = (result.data.authors as Array<{ author: string; email?: string; commits: number }>)
          .map((a) => ({
            author: a.author,
            email: a.email || '',
            commits: a.commits,
            avatar_url: generateAvatarUrl(a.author),
          }))
          .slice(0, 20);

        setSingleRepo({ platform, owner, repo, full_name: `${owner}/${repo}` });
        setAuthorsData(authors);
        appendLog(`Loaded ${authors.length} authors.`);

        if (authors.length > 0) {
          appendLog('Step 2/2: Evaluating first author...');
          await evaluateAuthor(0, owner, repo, authors, platform);
        }

        appendLog('Done.');
        setIsExecuting(false);
        setLoading(false);
        setLoadingText('');
        return;
      }

      // Multi repo mode
      setMode('multi');
      appendLog('Mode: Multi-Repository Analysis');

      appendLog(`Step 1/3: Extracting data for ${urls.length} repositories...`);
      const response = await fetch(`${API_SERVER_URL}/api/batch/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = (errorData as { detail?: unknown }).detail;
        appendLog(`Extract failed: ${detail || 'Failed to extract repositories'}`, 'error');
        setIsExecuting(false);
        setLoading(false);
        setLoadingText('');
        return;
      }

      const data: BatchResult = await response.json();
      setResults(data);

      appendLog(
        `Extraction results: total=${data.summary.total}, extracted=${data.summary.extracted}, skipped=${data.summary.skipped}, failed=${data.summary.failed}.`
      );
      data.results.forEach((r) => {
        const who = r.owner && r.repo ? `${r.owner}/${r.repo}` : r.url;
        appendLog(`- ${who}: ${r.status}${r.message ? ` (${r.message})` : ''}`);
      });
      if (data.summary.extracted === 0 && data.summary.skipped === 0) {
        appendLog('Extraction failed for all repositories. Stop.');
        appendLog('Done.');
        setIsExecuting(false);
        setLoading(false);
        return;
      }

      const reposWithData = data.results.filter((r) => r.data_exists && r.owner && r.repo);
      if (reposWithData.length >= 2) {
        setLoadingCommon(true);
        appendLog(`Step 2/3: Finding common contributors across ${reposWithData.length} repositories...`);

        const commonResponse = await fetch(`${API_SERVER_URL}/api/batch/common-contributors`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            repos: reposWithData.map((r) => ({ owner: r.owner, repo: r.repo, platform: r.platform })),
            author_aliases: authorAliases.trim() ? authorAliases : undefined,
          }),
        });

        if (commonResponse.ok) {
          const commonData: CommonContributorsResult = await commonResponse.json();
          setCommonContributors(commonData);

          if (commonData.common_contributors.length > 0) {
            appendLog(`Common contributors found: ${commonData.common_contributors.length}.`);
            const firstContributor = commonData.common_contributors[0].author;
            setSelectedContributor(firstContributor);
            appendLog(`Auto-select contributor: ${firstContributor}`);
            appendLog('Waiting for comparison...');
          } else {
            appendLog('No common contributors found.');
            appendLog('Done.');
            setIsExecuting(false);
          }
        } else {
          appendLog('Step 2/3 failed: common contributors request failed.', 'error');
          appendLog('Done.');
          setIsExecuting(false);
        }

        setLoadingCommon(false);
      } else {
        appendLog('Step 2/3 skipped: not enough repositories with extracted data.');
        appendLog('Done.');
        setIsExecuting(false);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`Analysis failed: ${msg}`, 'error');
      appendLog('Done.');
      setIsExecuting(false);
    } finally {
      setLoading(false);
      setLoadingText('');
    }
  };

  const useTestRepo = () => {
    setRepoUrls('https://gitee.com/zgcai/eval_test_1\nhttps://gitee.com/zgcai/eval_test_2');
    appendLog('Filled test repositories. Click Analyze to run.');
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
      dataIndex: 'url',
      key: 'url',
      render: (_: unknown, record: RepoResult) => {
        if (record.owner && record.repo) return `${record.owner}/${record.repo}`;
        return record.url;
      },
    },
    {
      title: 'Message',
      dataIndex: 'message',
      key: 'message',
      render: (msg: string) => <span style={{ color: '#666' }}>{msg || '-'}</span>,
    },
  ];

  return (
    <div className="repos-page">
      <div className="repos-container">
        <Card className="repos-card">
          <div className="repos-form">
            <label className="repos-label">
              <GithubOutlined />
              <span>Repository URLs (1-5 URLs, one per line)</span>
            </label>

            <div className="repos-input-row">
              <TextArea
                value={repoUrls}
                onChange={(e) => setRepoUrls(e.target.value)}
                placeholder={
                  'Single:\nhttps://gitee.com/owner/repo\n\nMulti:\nhttps://github.com/owner/repo1\nhttps://gitee.com/owner/repo2'
                }
                rows={6}
                disabled={loading}
              />
              <div className="repos-actions">
                <Button onClick={useTestRepo} disabled={loading}>
                  use_test_repo
                </Button>

                <Button
                  onClick={() => {
                    setLlmModalOpen(true);
                    refreshLlmConfig();
                  }}
                  disabled={loading}
                >
                  LLM设置
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

            <div style={{ marginTop: 16 }}>
              <label className="repos-label">
                <UserOutlined />
                <span>Author Aliases (optional, comma-separated names for the same person)</span>
              </label>
              <TextArea
                value={authorAliases}
                onChange={(e) => setAuthorAliases(e.target.value)}
                placeholder={'e.g., John Doe, John D, johndoe, jdoe\nGroup multiple names that belong to the same contributor'}
                rows={2}
                disabled={loading}
              />
            </div>
          </div>

          {/* Errors are shown in Execution logs to keep behavior consistent. */}

          <div className="repos-log" style={{ marginTop: 16 }}>
            <div className="repos-log-header">
              <div className="repos-log-title">Execution</div>
              <div className="repos-log-actions">
                <Button size="small" onClick={() => setLogsExpanded((v) => !v)}>
                  {logsExpanded ? 'Collapse' : 'Expand'}
                </Button>
                <Button size="small" onClick={() => setLogs([])} disabled={logs.length === 0}>
                  Clear
                </Button>
              </div>
            </div>

            {!logsExpanded ? (
              <div
                className="repos-log-ticker"
                title={tickerLine ? `#${tickerLine.id}/${logs.length} ${tickerLine.text}` : 'Ready.'}
                style={tickerLine?.level === 'error' ? { borderColor: '#fecaca', color: '#b91c1c', background: '#fef2f2' } : undefined}
              >
                {tickerLine ? (
                  <span>
                    <span style={{ color: 'rgba(0,0,0,0.6)', marginRight: 8 }}>
                      #{tickerLine.id}/{logs.length}
                    </span>
                    {tickerLine.text}
                  </span>
                ) : (
                  <span>Ready.</span>
                )}
              </div>
            ) : (
              <div ref={logsBodyRef} className="repos-log-body">
                {logs.length === 0 ? 'No logs yet.' : logs.map((l) => (
                  <div key={l.id} className={l.level === 'error' ? 'repos-log-line-error' : undefined}>
                    #{l.id} {l.text}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <Modal
          title="LLM 设置"
          open={llmModalOpen}
          onCancel={() => setLlmModalOpen(false)}
          onOk={saveLlmConfig}
          okText="保存"
          cancelText="取消"
        >
          <div style={{ marginBottom: 12, color: 'rgba(0,0,0,0.65)' }}>
            配置文件路径（已保存到用户目录，不支持打开）：<code>{llmConfigPath || '(unknown)'}</code>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>GITEE_TOKEN（可选，用于避免 Gitee API 限流）</div>
            <Input.Password value={giteeToken} onChange={(e) => setGiteeToken(e.target.value)} placeholder="Gitee access token" />
            <div style={{ marginTop: 6, color: 'rgba(0,0,0,0.65)' }}>
              当前已配置：<code>{giteeTokenMasked || '(not set)'}</code>（留空不修改）
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>GITHUB_TOKEN（可选，用于避免 GitHub API 限流）</div>
            <Input.Password value={githubToken} onChange={(e) => setGithubToken(e.target.value)} placeholder="GitHub personal access token" />
            <div style={{ marginTop: 6, color: 'rgba(0,0,0,0.65)' }}>
              当前已配置：<code>{githubTokenMasked || '(not set)'}</code>（留空不修改）
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <Radio.Group value={llmMode} onChange={(e) => setLlmMode(e.target.value)}>
              <Radio value="openrouter">OpenRouter</Radio>
              <Radio value="openai">OpenAI-compatible (base_url + api_key)</Radio>
            </Radio.Group>
          </div>

          {llmMode === 'openrouter' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>OPEN_ROUTER_KEY</div>
                <Input.Password value={openRouterKey} onChange={(e) => setOpenRouterKey(e.target.value)} placeholder="sk-or-..." />
              </div>
              <div style={{ color: 'rgba(0,0,0,0.65)' }}>
                当前全局 Model：<code>{model}</code>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_BASE_URL</div>
                <Input value={llmBaseUrl} onChange={(e) => setLlmBaseUrl(e.target.value)} placeholder="https://api.siliconflow.cn/v1" />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_API_KEY</div>
                <Input.Password value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} placeholder="Bearer token" />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_CHAT_COMPLETIONS_URL（可选）</div>
                <Input value={llmChatUrl} onChange={(e) => setLlmChatUrl(e.target.value)} placeholder="https://.../chat/completions" />
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_FALLBACK_MODELS（可选）</div>
                <Input value={llmFallbackModels} onChange={(e) => setLlmFallbackModels(e.target.value)} placeholder="model1,model2" />
              </div>
              <div style={{ color: 'rgba(0,0,0,0.65)' }}>
                当前全局 Model：<code>{model}</code>
              </div>
            </div>
          )}
        </Modal>

        {loading && (
          <Card className="repos-loading-card">
            <LoadingOutlined className="repos-loading-icon" />
            <h3>{loadingText || (loadingCommon ? 'Finding Common Contributors...' : 'Working...')}</h3>
            <p>
              {loadingCommon
                ? 'Analyzing contributors across repositories...'
                : 'This may take a few minutes. Please wait while we fetch commits and files from the remote repository.'}
            </p>
          </Card>
        )}

        {mode === 'single' && singleRepo && authorsData.length > 0 && (
          <Card className="repo-info">
            <h2>{singleRepo.full_name}</h2>
            <p>Analyzing {authorsData.length} authors from local commits</p>

            <div className="contributors-grid">
              {authorsData.map((author, index) => (
                <Card
                  key={index}
                  hoverable
                  className={`contributor-card ${selectedAuthorIndex === index ? 'active' : ''}`}
                  onClick={() => evaluateAuthor(index, singleRepo.owner, singleRepo.repo)}
                >
                  <Avatar size={60} src={author.avatar_url} icon={<UserOutlined />} />
                  <div className="contributor-name">{author.author}</div>
                  <div className="contributor-commits">{author.commits} commits</div>
                </Card>
              ))}
            </div>
          </Card>
        )}

        {mode === 'single' && evaluation && singleRepo && (
          <Card className="evaluation-section">
            <div className="eval-header">
              <Avatar size={80} src={authorsData[selectedAuthorIndex]?.avatar_url} icon={<UserOutlined />} />
              <div className="eval-header-info">
                <h2>
                  {(() => {
                    const currentAuthor = authorsData[selectedAuthorIndex]?.author;
                    if (authorAliases.trim()) {
                      const aliases = authorAliases.split(',').map(a => a.trim()).filter(a => a);
                      if (aliases.some(a => a.toLowerCase() === currentAuthor?.toLowerCase())) {
                        return aliases.join(', ');
                      }
                    }
                    return currentAuthor;
                  })()}
                </h2>
                <div className="stats">
                  {evaluation.total_commits_analyzed} commits analyzed •{evaluation.commits_summary.total_additions} additions •
                  {evaluation.commits_summary.total_deletions} deletions
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownloadSinglePDF}>
                  Download PDF
                </Button>
              </div>
            </div>

            <PluginViewRenderer
              pluginId={pluginId || 'zgc_simple'}
              evaluation={evaluation}
              title={`Analysis View (${pluginId || 'zgc_simple'})`}
              loading={loading}
            />
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
            <Table columns={columns} dataSource={results.results} rowKey={(r) => r.url} pagination={false} />
          </Card>
        )}

        {commonContributors && commonContributors.common_contributors.length > 0 && (
          <>
            <Card
              title={
                <div className="repos-section-title">
                  <TeamOutlined />
                  <span>Common Contributors</span>
                </div>
              }
              className="repos-card"
            >
              <Table
                dataSource={commonContributors.common_contributors.map((c) => ({
                  key: c.author,
                  author: c.author,
                  aliases: c.aliases || [c.author],
                  email: c.email,
                  repo_count: c.repo_count,
                  total_commits: c.total_commits,
                  repos: c.repos,
                }))}
                pagination={false}
                columns={[
                  {
                    title: 'Contributor',
                    dataIndex: 'author',
                    key: 'author',
                    render: (author: string, record: { author: string; aliases: string[]; email: string; repo_count: number; total_commits: number }) => {
                      const otherAliases = record.aliases.filter((a: string) => a !== author);
                      return (
                        <Space orientation="vertical" size={0}>
                          <Space>
                            <Avatar src={`https://ui-avatars.com/api/?name=${encodeURIComponent(author)}&background=FFEB00&color=0A0A0A&size=64&bold=true`} icon={<UserOutlined />} />
                            <span style={{ fontWeight: 700 }}>{author}</span>
                          </Space>
                          {otherAliases.length > 0 && (
                            <span style={{ fontSize: '0.85em', color: 'rgba(0,0,0,0.45)', marginLeft: 40 }}>
                              also known as: {otherAliases.join(', ')}
                            </span>
                          )}
                        </Space>
                      );
                    },
                  },
                  { title: 'Repos', dataIndex: 'repo_count', key: 'repo_count', width: 90 },
                  { title: 'Commits', dataIndex: 'total_commits', key: 'total_commits', width: 110 },
                ]}
              />
            </Card>

            <Card
              title={
                <div className="repos-compare-title">
                  <div className="repos-compare-left">
                    <span className="repos-compare-label">Select Contributor to Compare:</span>
                    <Select value={selectedContributor} onChange={setSelectedContributor} style={{ width: 320 }} size="large">
                      {commonContributors.common_contributors.map((contributor) => (
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
              <PluginComparisonRenderer
                pluginId={pluginId || 'zgc_simple'}
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
            <p>{commonContributors.message || 'The analyzed repositories do not have any contributors in common.'}</p>
          </Card>
        )}
      </div>
    </div>
  );
}


