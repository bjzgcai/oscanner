'use client';

import { useEffect, useState } from 'react';
import { Input, Button, Card, Avatar, Spin, Alert, message, Modal, Progress } from 'antd';
import { UserOutlined, DownloadOutlined, LoadingOutlined } from '@ant-design/icons';
import PluginViewRenderer from './PluginViewRenderer';
import { exportHomePagePDF } from '../utils/pdfExport';
import { useAppSettings } from './AppSettingsContext';
import { getApiBaseUrl } from '../utils/apiBase';
import { useI18n } from './I18nContext';

// Default to same-origin so the bundled dashboard works when served by the backend.
// For separate frontend dev server, set NEXT_PUBLIC_API_SERVER_URL=http://localhost:8000
const API_SERVER_URL = getApiBaseUrl();
const STORAGE_KEY = 'local_repo_history';
const MAX_HISTORY = 20;


interface Author {
  author: string;
  email: string;
  commits: number;
  avatar_url: string;
}

interface Evaluation {
  scores: {
    [key: string]: number | string;
  };
  total_commits_analyzed: number;
  commits_summary: {
    total_additions: number;
    total_deletions: number;
    files_changed: number;
    languages: string[];
  };
}

interface RepoData {
  owner: string;
  repo: string;
  platform: 'github' | 'gitee';
  full_name: string;
  path: string;
}

export default function SingleRepoAnalysis() {
  const [repoPath, setRepoPath] = useState('');
  const { model, pluginId, useCache } = useAppSettings();
  const { t, locale, messages } = useI18n();
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('');
  const [progress, setProgress] = useState(0);
  const [repoError, setRepoError] = useState('');
  const [evalError, setEvalError] = useState('');
  const [repoData, setRepoData] = useState<RepoData | null>(null);
  const [authorsData, setAuthorsData] = useState<Author[]>([]);
  const [selectedAuthorIndex, setSelectedAuthorIndex] = useState<number>(-1);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    const savedHistory = localStorage.getItem(STORAGE_KEY);
    if (savedHistory) setHistory(JSON.parse(savedHistory));
  }, []);

  const saveToHistory = (path: string) => {
    let newHistory = [...history];
    newHistory = newHistory.filter((h) => h !== path);
    newHistory.unshift(path);
    newHistory = newHistory.slice(0, MAX_HISTORY);
    setHistory(newHistory);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newHistory));
  };

  const generateAvatarUrl = (author: string) => {
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(author)}&background=FFEB00&color=0A0A0A&size=128&bold=true`;
  };

  const parseRepoUrl = (input: string): { platform: 'github' | 'gitee'; owner: string; repo: string } | null => {
    const trimmed = input.trim();
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

  const analyzeRepository = async () => {
    if (!repoPath) {
      setRepoError(t('single.input.placeholder'));
      return;
    }
    const parsed = parseRepoUrl(repoPath);
    if (!parsed) {
      setRepoError(
        'Invalid repository URL. Please use a valid format like: https://github.com/owner/repo or https://gitee.com/owner/repo'
      );
      return;
    }

    const { platform, owner, repo } = parsed;

    setLoading(true);
    setLoadingText('Loading repository data...');
    setRepoError('');
    setEvalError('');
    setRepoData(null);
    setAuthorsData([]);
    setEvaluation(null);

    try {
      const response = await fetch(`${API_SERVER_URL}/api/authors/${owner}/${repo}?platform=${encodeURIComponent(platform)}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to load authors');
      }

      const result = await response.json();
      const authors = (result.data.authors as Array<{ author: string; email?: string; commits: number }>)
        .map((author) => ({
          author: author.author,
          email: author.email || '',
          commits: author.commits,
          avatar_url: generateAvatarUrl(author.author),
        }))
        .slice(0, 20);

      setAuthorsData(authors);
      setRepoData({ owner, repo, platform, full_name: `${owner}/${repo}`, path: repoPath });
      saveToHistory(repoPath);

      if (authors.length > 0) {
        setLoadingText('Loading first author evaluation...');
        await evaluateAuthor(0, authors, owner, repo, platform);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setRepoError(msg);
    } finally {
      setLoading(false);
    }
  };

  const evaluateAuthor = async (index: number, authors?: Author[], owner?: string, repo?: string, platform?: 'github' | 'gitee') => {
    const authorsToUse = authors || authorsData;
    const ownerToUse = owner || repoData?.owner;
    const repoToUse = repo || repoData?.repo;
    const platformToUse = platform || repoData?.platform || 'github';

    const author = authorsToUse[index];
    setSelectedAuthorIndex(index);
    setLoading(true);
    setLoadingText(`Analyzing ${author.author}'s commits with AI...`);
    setProgress(0);
    setEvalError('');
    setEvaluation(null);

    // Simulate progress for better UX
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) return prev;
        return prev + Math.random() * 10;
      });
    }, 1000);

    try {
      setProgress(10);
      const response = await fetch(
        `${API_SERVER_URL}/api/evaluate/${ownerToUse}/${repoToUse}/${encodeURIComponent(author.author)}?model=${encodeURIComponent(model)}&platform=${encodeURIComponent(platformToUse)}&plugin=${encodeURIComponent(pluginId || '')}&use_cache=${useCache ? 'true' : 'false'}&language=${encodeURIComponent(locale)}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('Failed to evaluate author');
      const result = await response.json();
      if (!result.success) throw new Error(result.error || 'Evaluation failed');

      setProgress(100);
      setEvaluation(result.evaluation);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setEvalError(msg);
    } finally {
      clearInterval(progressInterval);
      setLoading(false);
      setProgress(0);
    }
  };

  // Result visualization is fully handled by plugin views.

  const handleDownloadPDF = async () => {
    if (!repoData || !evaluation || selectedAuthorIndex < 0) {
      message.error(t('single.pdf.no_data'));
      return;
    }
    try {
      message.loading(t('single.pdf.generating'), 0);
      await exportHomePagePDF(repoData, authorsData[selectedAuthorIndex], evaluation, messages);
      message.destroy();
      message.success(t('single.pdf.success'));
    } catch (e) {
      message.destroy();
      message.error(t('single.pdf.failed'));
      console.error('PDF generation error:', e);
    }
  };

  // Result visualization is fully handled by plugin views.

  const filteredHistory = history.filter((h) => h.toLowerCase().includes(repoPath.toLowerCase()));

  return (
    <div className="dashboard-container">
      <Card className="input-section">
        <div className="input-group">
          <div className="autocomplete-container">
            <Input
              size="large"
              placeholder={t('single.input.placeholder')}
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              onFocus={() => setShowHistory(true)}
              onBlur={() => setTimeout(() => setShowHistory(false), 200)}
              onPressEnter={analyzeRepository}
            />
            {showHistory && filteredHistory.length > 0 && (
              <div className="autocomplete-dropdown">
                {filteredHistory.map((item, idx) => (
                  <div
                    key={idx}
                    className="autocomplete-item"
                    onClick={() => {
                      setRepoPath(item);
                      setShowHistory(false);
                    }}
                  >
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>
          <Button type="primary" size="large" onClick={analyzeRepository} loading={loading} className="analyze-btn">
            {t('single.load_authors')}
          </Button>
        </div>

        {/* Model selection is global (Navigation bar). */}
      </Card>

      {repoError && (
        <Alert
          message={t('single.error.title')}
          description={repoError}
          type="error"
          closable
          onClose={() => setRepoError('')}
          style={{ marginBottom: 20 }}
        />
      )}

      {loading && !evaluation && (
        <Card className="loading-card">
          <Spin size="large" />
          <p style={{ marginTop: 20 }}>{loadingText}</p>
        </Card>
      )}

      {repoData && authorsData.length > 0 && (
        <Card className="repo-info">
          <h2>{repoData.full_name}</h2>
          <p>Analyzing {authorsData.length} authors from local commits</p>

          <div className="contributors-grid">
            {authorsData.map((author, index) => (
              <Card
                key={index}
                hoverable
                className={`contributor-card ${selectedAuthorIndex === index ? 'active' : ''}`}
                onClick={() => evaluateAuthor(index)}
              >
                <Avatar size={60} src={author.avatar_url} icon={<UserOutlined />} />
                <div className="contributor-name">{author.author}</div>
                <div className="contributor-commits">{author.commits} commits</div>
              </Card>
            ))}
          </div>
        </Card>
      )}

      {(evaluation || evalError || (loading && selectedAuthorIndex >= 0)) && (
        <Card className="evaluation-section">
          <Spin spinning={loading} size="large" tip={loadingText}>
            <div className="eval-header">
              <Avatar size={80} src={authorsData[selectedAuthorIndex]?.avatar_url} icon={<UserOutlined />} />
              <div className="eval-header-info">
                <h2>{authorsData[selectedAuthorIndex]?.author}</h2>
                <div className="stats">
                  {evaluation
                    ? `${evaluation.total_commits_analyzed} commits analyzed •${evaluation.commits_summary.total_additions} additions •${evaluation.commits_summary.total_deletions} deletions`
                    : t('single.no_eval')}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  onClick={handleDownloadPDF}
                  style={{ background: '#FFEB00', borderColor: '#FFEB00', color: '#0A0A0A', fontWeight: 'bold' }}
                >
                  {t('common.download_pdf')}
                </Button>
              </div>
            </div>

            <PluginViewRenderer
              pluginId={pluginId || 'zgc_simple'}
              evaluation={evaluation}
              title={`Analysis View (${pluginId || 'zgc_simple'})`}
              loading={loading}
              error={evalError}
            />
          </Spin>
        </Card>
      )}

      {/* Progress Modal - blocks user interaction during evaluation */}
      <Modal
        open={loading}
        closable={false}
        footer={null}
        centered
        maskClosable={false}
        keyboard={false}
        width={400}
      >
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <LoadingOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 20 }} spin />
          <h3 style={{ marginBottom: 20 }}>{loadingText}</h3>
          <Progress
            percent={Math.round(progress)}
            status="active"
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
          <p style={{ marginTop: 20, color: '#999', fontSize: 12 }}>
            {t('single.eval.please_wait')}
          </p>
        </div>
      </Modal>
    </div>
  );
}


