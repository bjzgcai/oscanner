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
import ContributorComparison from './ContributorComparison';
import { exportHomePagePDF, exportMultiRepoPDF } from '../utils/pdfExport';
import type { ContributorComparisonData } from '../types';
import { useAppSettings } from './AppSettingsContext';
import { Radar } from 'react-chartjs-2';
import ReactMarkdown from 'react-markdown';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

const { TextArea } = Input;

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

export default function MultiRepoAnalysis() {
  const [repoUrls, setRepoUrls] = useState('');
  const [loading, setLoading] = useState(false);
  const { useCache, model } = useAppSettings();
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

  // Single-repo state (merged UI)
  const [singleRepo, setSingleRepo] = useState<{ platform: 'github' | 'gitee'; owner: string; repo: string; full_name: string } | null>(null);
  const [authorsData, setAuthorsData] = useState<Array<{ author: string; email: string; commits: number; avatar_url: string }>>([]);
  const [selectedAuthorIndex, setSelectedAuthorIndex] = useState<number>(-1);
  const [evaluation, setEvaluation] = useState<null | {
    scores: { [key: string]: number | string };
    total_commits_analyzed: number;
    commits_summary: { total_additions: number; total_deletions: number; files_changed: number; languages: string[] };
  }>(null);
  const [isCached, setIsCached] = useState(false);

  const dimensions = useMemo(
    () => [
      { name: 'AI Model Full-Stack', key: 'ai_fullstack', description: 'AI/ML model development, training, optimization, and deployment capabilities' },
      { name: 'AI Native Architecture', key: 'ai_architecture', description: 'AI-first system design, API architecture, and microservices patterns' },
      { name: 'Cloud Native Engineering', key: 'cloud_native', description: 'Containerization, infrastructure as code, CI/CD, and cloud platform expertise' },
      { name: 'Open Source Collaboration', key: 'open_source', description: 'Contribution quality, code review, issue management, and communication' },
      { name: 'Intelligent Development', key: 'intelligent_dev', description: 'AI-assisted development, automation, testing, and development efficiency' },
      { name: 'Engineering Leadership', key: 'leadership', description: 'Technical decision-making, optimization, security, and best practices' },
    ],
    []
  );

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
      await refreshLlmConfig();
    } catch (e: unknown) {
      appendLog(`LLM settings save failed: ${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  }, [appendLog, llmApiKey, llmBaseUrl, llmChatUrl, llmFallbackModels, llmMode, model, openRouterKey, refreshLlmConfig]);

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
        evaluation,
        isCached
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
      authorsOverride?: Array<{ author: string; email: string; commits: number; avatar_url: string }>
    ) => {
      const author = (authorsOverride && authorsOverride[index]) || authorsData[index];
      if (!author) return;
      setSelectedAuthorIndex(index);
      setLoading(true);
      setLoadingText(`Evaluating ${author.author}...`);
      appendLog(`Evaluate author: ${author.author}`);

      try {
        const response = await fetch(
          `${API_SERVER_URL}/api/evaluate/${owner}/${repo}/${encodeURIComponent(author.author)}?use_cache=${useCache}&model=${encodeURIComponent(model)}`,
          { method: 'POST' }
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
        setIsCached(Boolean(result.metadata?.cached));
        appendLog(`Evaluation complete (${result.metadata?.cached ? 'cached' : 'fresh'}).`);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        appendLog(`Evaluation failed: ${msg}`, 'error');
      } finally {
        setLoading(false);
        setLoadingText('');
      }
    },
    [appendLog, authorsData, model, useCache]
  );

  const compareContributor = useCallback(
    async (contributorName: string, reposToCompare: Array<{ owner: string; repo: string }>) => {
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
            use_cache: useCache,
            model,
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
        if (!data.success) throw new Error('No evaluation data found');

        setComparisonData(data);
        const cachedCount = data.comparisons.filter((c) => c.cached).length;
        appendLog(
          `Comparison complete: ${data.comparisons.length} repos (${cachedCount} cached, ${
            data.comparisons.length - cachedCount
          } fresh).`
        );
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
    [appendLog, useCache, model]
  );

  useEffect(() => {
    if (selectedContributor && results) {
      const reposWithData = results.results.filter((r) => r.data_exists && r.owner && r.repo);
      if (reposWithData.length >= 2) {
        const reposToCompare = reposWithData.map((r) => ({ owner: r.owner!, repo: r.repo! }));

        // If cache is enabled but LLM is not configured, we can only proceed if caches exist.
        const llmOk = llmConfiguredRef.current !== false;
        if (useCache && !llmOk) {
          (async () => {
            try {
              for (const r of reposToCompare) {
                const resp = await fetch(`${API_SERVER_URL}/api/evaluation-cache/status/${r.owner}/${r.repo}`);
                if (!resp.ok) continue;
                const st = await resp.json();
                if (!st.exists) {
                  appendLog(`Cache enabled but evaluation cache missing for ${r.owner}/${r.repo}; LLM is required for comparison.`, 'error');
                  appendLog('Done.');
                  return;
                }
              }
            } catch {
              // ignore; compare will surface details
            }
            compareContributor(selectedContributor, reposToCompare);
          })();
          return;
        }

        compareContributor(selectedContributor, reposToCompare);
      }
    }
  }, [selectedContributor, results, compareContributor, useCache, appendLog]);

  const handleSubmit = async () => {
    setMode(null);
    setSingleRepo(null);
    setAuthorsData([]);
    setSelectedAuthorIndex(-1);
    setEvaluation(null);
    setIsCached(false);
    setResults(null);
    setCommonContributors(null);
    setSelectedContributor('');
    setComparisonData(null);
    setLogs([]);
    setIsExecuting(true);
    appendLog(`Start analysis (use_cache=${useCache ? 'true' : 'false'}).`);

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
            // If cache is disabled, we cannot proceed because evaluation will require LLM.
            if (!useCache) {
              setIsExecuting(false);
              setLoading(false);
              setLoadingText('');
              return;
            }
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
          `${API_SERVER_URL}/api/authors/${owner}/${repo}?platform=${encodeURIComponent(platform)}&use_cache=${useCache}`
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
          // If cache is enabled but LLM is not configured, we can only proceed if cache exists.
          const llmOk = llmConfiguredRef.current !== false;
          if (useCache && !llmOk) {
            try {
              const cacheResp = await fetch(`${API_SERVER_URL}/api/evaluation-cache/status/${owner}/${repo}`);
              if (cacheResp.ok) {
                const cache = await cacheResp.json();
                if (!cache.exists) {
                  appendLog('Cache enabled but evaluation cache does not exist for this repo; LLM is required. Please configure LLM and retry.', 'error');
                  setIsExecuting(false);
                  setLoading(false);
                  setLoadingText('');
                  return;
                }
              }
            } catch {
              // ignore; evaluation call will surface details
            }
          }

          appendLog('Step 2/2: Evaluating first author...');
          await evaluateAuthor(0, owner, repo, authors);
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
            repos: reposWithData.map((r) => ({ owner: r.owner, repo: r.repo })),
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
                : 'This may take a few minutes. Please wait while we fetch commits and files from GitHub.'}
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
                <h2>{authorsData[selectedAuthorIndex]?.author}</h2>
                <div className="stats">
                  {evaluation.total_commits_analyzed} commits analyzed •{evaluation.commits_summary.total_additions} additions •
                  {evaluation.commits_summary.total_deletions} deletions
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                {isCached ? (
                  <Tag color="success" className="eval-badge">
                    Cached Result
                  </Tag>
                ) : (
                  <Tag color="purple" className="eval-badge">
                    AI-Powered Analysis
                  </Tag>
                )}
                <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownloadSinglePDF}>
                  Download PDF
                </Button>
              </div>
            </div>

            <div className="chart-container" id="radar-chart-export">
              <Radar
                data={{
                  labels: dimensions.map((d) => d.name),
                  datasets: [
                    {
                      label: 'Engineering Skills',
                      data: dimensions.map((d) => evaluation.scores[d.key] || 0),
                      fill: true,
                      backgroundColor: 'rgba(255, 235, 0, 0.15)',
                      borderColor: '#FFEB00',
                      pointBackgroundColor: '#00F0FF',
                      pointBorderColor: '#0A0A0A',
                      pointHoverBackgroundColor: '#FF006B',
                      pointHoverBorderColor: '#FFEB00',
                      pointRadius: 8,
                      pointHoverRadius: 12,
                      borderWidth: 3,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { display: false } },
                  scales: {
                    r: {
                      suggestedMin: 0,
                      suggestedMax: 100,
                      ticks: { stepSize: 20, backdropColor: 'transparent', color: '#B0B0B0' },
                      pointLabels: { color: '#FFFFFF' },
                      angleLines: { display: true, color: '#333', lineWidth: 2 },
                      grid: { color: '#333', lineWidth: 2 },
                    },
                  },
                }}
              />
            </div>

            <div className="dimensions-grid">
              {dimensions.map((dim) => {
                const score = evaluation.scores[dim.key] || 0;
                return (
                  <Card key={dim.key} className="dimension-card">
                    <h4>{dim.name}</h4>
                    <div className="score-display">
                      <div className="score-row">
                        <span className="score-label">Score:</span>
                        <span className="score">{score}</span>
                      </div>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${score}%` }} />
                    </div>
                    <div className="description">{dim.description}</div>
                  </Card>
                );
              })}
            </div>

            {evaluation.scores.reasoning && (
              <Card className="reasoning-section">
                <h3>AI Analysis Summary</h3>
                <div className="markdown-content">
                  <ReactMarkdown>{evaluation.scores.reasoning as string}</ReactMarkdown>
                </div>
              </Card>
            )}
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
                    render: (author: string) => (
                      <Space>
                        <Avatar src={`https://ui-avatars.com/api/?name=${encodeURIComponent(author)}&background=FFEB00&color=0A0A0A&size=64&bold=true`} icon={<UserOutlined />} />
                        <span style={{ fontWeight: 700 }}>{author}</span>
                      </Space>
                    ),
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
            <p>{commonContributors.message || 'The analyzed repositories do not have any contributors in common.'}</p>
          </Card>
        )}
      </div>
    </div>
  );
}


