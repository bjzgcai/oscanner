'use client';

import { useEffect, useState } from 'react';
import { Input, Button, Card, Avatar, Spin, Alert, message } from 'antd';
import { UserOutlined, DownloadOutlined } from '@ant-design/icons';
import PluginViewRenderer from './PluginViewRenderer';
import { exportHomePagePDF } from '../utils/pdfExport';
import { useAppSettings } from './AppSettingsContext';
import { getApiBaseUrl } from '../utils/apiBase';

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
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('');
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
      setRepoError('Please enter a repository URL');
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
    setEvalError('');
    setEvaluation(null);

    try {
      const response = await fetch(
        `${API_SERVER_URL}/api/evaluate/${ownerToUse}/${repoToUse}/${encodeURIComponent(author.author)}?model=${encodeURIComponent(model)}&platform=${encodeURIComponent(platformToUse)}&plugin=${encodeURIComponent(pluginId || '')}&use_cache=${useCache ? 'true' : 'false'}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('Failed to evaluate author');
      const result = await response.json();
      if (!result.success) throw new Error(result.error || 'Evaluation failed');

      setEvaluation(result.evaluation);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setEvalError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Result visualization is fully handled by plugin views.

  const handleDownloadPDF = async () => {
    if (!repoData || !evaluation || selectedAuthorIndex < 0) {
      message.error('No evaluation data available to export');
      return;
    }
    try {
      message.loading('Generating PDF report...', 0);
      await exportHomePagePDF(repoData, authorsData[selectedAuthorIndex], evaluation);
      message.destroy();
      message.success('PDF report downloaded successfully!');
    } catch (e) {
      message.destroy();
      message.error('Failed to generate PDF report');
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
              placeholder="Enter repository URL (e.g., https://github.com/owner/repo or https://gitee.com/owner/repo)"
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
            Load Authors
          </Button>
        </div>

        {/* Model selection is global (Navigation bar). */}
      </Card>

      {repoError && (
        <Alert
          message="Error"
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
                    : 'No evaluation available'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  onClick={handleDownloadPDF}
                  style={{ background: '#FFEB00', borderColor: '#FFEB00', color: '#0A0A0A', fontWeight: 'bold' }}
                >
                  Download PDF
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
    </div>
  );
}


