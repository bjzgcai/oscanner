'use client';

import { useState, useEffect } from 'react';
import { Input, Button, Switch, Card, Avatar, Spin, Alert, Tag, message } from 'antd';
import { UserOutlined, ThunderboltOutlined, RobotOutlined, DownloadOutlined } from '@ant-design/icons';
import { Radar } from 'react-chartjs-2';
import { exportHomePagePDF } from '../utils/pdfExport';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import './dashboard.css';

// Register ChartJS components
ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

const API_SERVER_URL = process.env.NEXT_PUBLIC_API_SERVER_URL || 'http://localhost:8000';
const STORAGE_KEY = 'local_repo_history';
const MAX_HISTORY = 20;

const dimensions = [
  {
    name: "AI Model Full-Stack",
    key: "ai_fullstack",
    description: "AI/ML model development, training, optimization, and deployment capabilities"
  },
  {
    name: "AI Native Architecture",
    key: "ai_architecture",
    description: "AI-first system design, API architecture, and microservices patterns"
  },
  {
    name: "Cloud Native Engineering",
    key: "cloud_native",
    description: "Containerization, infrastructure as code, CI/CD, and cloud platform expertise"
  },
  {
    name: "Open Source Collaboration",
    key: "open_source",
    description: "Contribution quality, code review, issue management, and communication"
  },
  {
    name: "Intelligent Development",
    key: "intelligent_dev",
    description: "AI-assisted development, automation, testing, and development efficiency"
  },
  {
    name: "Engineering Leadership",
    key: "leadership",
    description: "Technical decision-making, optimization, security, and best practices"
  }
];

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

export default function Dashboard() {
  const [repoPath, setRepoPath] = useState('');
  const [useCache, setUseCache] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('');
  const [error, setError] = useState('');
  const [repoData, setRepoData] = useState<any>(null);
  const [authorsData, setAuthorsData] = useState<Author[]>([]);
  const [selectedAuthorIndex, setSelectedAuthorIndex] = useState<number>(-1);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [isCached, setIsCached] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    // Load history from localStorage
    const savedHistory = localStorage.getItem(STORAGE_KEY);
    if (savedHistory) {
      setHistory(JSON.parse(savedHistory));
    }
  }, []);

  const saveToHistory = (path: string) => {
    let newHistory = [...history];
    newHistory = newHistory.filter(h => h !== path);
    newHistory.unshift(path);
    newHistory = newHistory.slice(0, MAX_HISTORY);
    setHistory(newHistory);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newHistory));
  };

  const generateAvatarUrl = (author: string) => {
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(author)}&background=FFEB00&color=0A0A0A&size=128&bold=true`;
  };

  const parseGitHubUrl = (input: string): { owner: string; repo: string } | null => {
    const trimmed = input.trim();

    // Try to parse as GitHub URL
    const urlPatterns = [
      /^https?:\/\/(?:www\.)?github\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^github\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^git@github\.com:([^\/]+)\/([^\/\s]+)\.git$/i,
      /^git@github\.com:([^\/]+)\/([^\/\s]+)$/i,
    ];

    for (const pattern of urlPatterns) {
      const match = trimmed.match(pattern);
      if (match) {
        let repo = match[2];
        // Remove .git suffix if present
        repo = repo.replace(/\.git$/, '');
        return { owner: match[1], repo };
      }
    }

    return null;
  };

  const analyzeRepository = async () => {
    if (!repoPath) {
      setError('Please enter a GitHub repository URL');
      return;
    }

    const parsed = parseGitHubUrl(repoPath);
    if (!parsed) {
      setError('Invalid GitHub URL. Please use a valid format like: https://github.com/owner/repo');
      return;
    }

    const { owner, repo } = parsed;

    setLoading(true);
    setLoadingText('Checking for cached data...');
    setError('');
    setRepoData(null);
    setAuthorsData([]);
    setEvaluation(null);

    try {
      // Note: This endpoint may take a while if it needs to fetch GitHub data
      setLoadingText('Loading repository data (this may take a minute for new repos)...');

      const response = await fetch(`${API_SERVER_URL}/api/authors/${owner}/${repo}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to load authors');
      }

      const result = await response.json();

      if (result.data.cached) {
        setLoadingText('Loaded from cache!');
      } else {
        setLoadingText('Processing commit data...');
      }

      const authors = result.data.authors.map((author: any) => ({
        ...author,
        avatar_url: generateAvatarUrl(author.author)
      })).slice(0, 20);

      setAuthorsData(authors);
      setRepoData({
        owner,
        repo,
        full_name: `${owner}/${repo}`,
        path: repoPath
      });

      saveToHistory(repoPath);

      if (authors.length > 0) {
        setLoadingText('Loading first author evaluation...');
        await evaluateAuthor(0, authors, owner, repo);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const evaluateAuthor = async (index: number, authors?: Author[], owner?: string, repo?: string) => {
    const authorsToUse = authors || authorsData;
    const ownerToUse = owner || repoData?.owner;
    const repoToUse = repo || repoData?.repo;

    const author = authorsToUse[index];
    setSelectedAuthorIndex(index);
    setLoading(true);
    setLoadingText(`Analyzing ${author.author}'s commits with AI...`);

    try {
      const response = await fetch(
        `${API_SERVER_URL}/api/evaluate/${ownerToUse}/${repoToUse}/${encodeURIComponent(author.author)}?use_cache=${useCache}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to evaluate author');
      }

      const result = await response.json();
      if (!result.success) {
        throw new Error(result.error || 'Evaluation failed');
      }

      setEvaluation(result.evaluation);
      setIsCached(result.metadata?.cached || false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getChartData = () => {
    if (!evaluation) return null;

    return {
      labels: dimensions.map(d => d.name),
      datasets: [{
        label: 'Engineering Skills',
        data: dimensions.map(d => evaluation.scores[d.key] || 0),
        fill: true,
        backgroundColor: 'rgba(255, 235, 0, 0.15)',
        borderColor: '#FFEB00',
        pointBackgroundColor: '#00F0FF',
        pointBorderColor: '#0A0A0A',
        pointHoverBackgroundColor: '#FF006B',
        pointHoverBorderColor: '#FFEB00',
        pointRadius: 8,
        pointHoverRadius: 12,
        borderWidth: 3
      }]
    };
  };

  const handleDownloadPDF = async () => {
    if (!repoData || !evaluation || selectedAuthorIndex < 0) {
      message.error('No evaluation data available to export');
      return;
    }

    try {
      message.loading('Generating PDF report...', 0);
      await exportHomePagePDF(
        repoData,
        authorsData[selectedAuthorIndex],
        evaluation,
        isCached
      );
      message.destroy();
      message.success('PDF report downloaded successfully!');
    } catch (error) {
      message.destroy();
      message.error('Failed to generate PDF report');
      console.error('PDF generation error:', error);
    }
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        angleLines: {
          display: true,
          color: '#333',
          lineWidth: 2
        },
        grid: {
          color: '#333',
          lineWidth: 2
        },
        suggestedMin: 0,
        suggestedMax: 100,
        ticks: {
          stepSize: 20,
          backdropColor: 'transparent',
          color: '#B0B0B0',
          font: {
            size: 12,
            family: "'Azeret Mono', monospace",
            weight: 'bold' as const
          }
        },
        pointLabels: {
          color: '#FFFFFF',
          font: {
            size: 13,
            weight: 'bold' as const,
            family: "'Syne', sans-serif"
          }
        }
      }
    },
    plugins: {
      legend: {
        display: false
      }
    }
  };

  const filteredHistory = history.filter(h =>
    h.toLowerCase().includes(repoPath.toLowerCase())
  );

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1>Git Engineer Skill Evaluator</h1>
        <p>LLM-Powered Six-Dimensional Engineering Capability Analysis</p>
      </div>

      <Card className="input-section">
        <div className="input-group">
          <div className="autocomplete-container">
            <Input
              size="large"
              placeholder="Enter GitHub repository URL (e.g., https://github.com/owner/repo)"
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
          <Button
            type="primary"
            size="large"
            onClick={analyzeRepository}
            loading={loading}
            className="analyze-btn"
          >
            Load Authors
          </Button>
        </div>

        <div className="cache-control">
          <Switch
            checked={useCache}
            onChange={setUseCache}
            checkedChildren="Cache On"
            unCheckedChildren="Cache Off"
          />
          <span className="cache-description">
            When enabled, uses cached evaluation results. Disable to force fresh AI analysis.
          </span>
        </div>

        <div className="note">
          Paste a GitHub repository URL to analyze authors from local commit data. Supports HTTPS, SSH, and short URL formats. Authors are identified by their git commit author name.
        </div>
      </Card>

      {error && (
        <Alert
          message="Error"
          description={error}
          type="error"
          closable
          onClose={() => setError('')}
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

      {evaluation && (
        <Card className="evaluation-section">
          <Spin spinning={loading} size="large" tip={loadingText}>
          <div className="eval-header">
            <Avatar
              size={80}
              src={authorsData[selectedAuthorIndex]?.avatar_url}
              icon={<UserOutlined />}
            />
            <div className="eval-header-info">
              <h2>{authorsData[selectedAuthorIndex]?.author}</h2>
              <div className="stats">
                {evaluation.total_commits_analyzed} commits analyzed •
                {evaluation.commits_summary.total_additions} additions •
                {evaluation.commits_summary.total_deletions} deletions
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              {isCached ? (
                <Tag icon={<ThunderboltOutlined />} color="success" className="eval-badge">
                  Cached Result
                </Tag>
              ) : (
                <Tag icon={<RobotOutlined />} color="purple" className="eval-badge">
                  AI-Powered Analysis
                </Tag>
              )}
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={handleDownloadPDF}
                style={{
                  background: '#FFEB00',
                  borderColor: '#FFEB00',
                  color: '#0A0A0A',
                  fontWeight: 'bold'
                }}
              >
                Download PDF
              </Button>
            </div>
          </div>

          <div className="chart-container" id="radar-chart-export">
            {getChartData() && <Radar data={getChartData()!} options={chartOptions} />}
          </div>

          <div className="dimensions-grid">
            {dimensions.map(dim => {
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
                    <div
                      className="progress-fill"
                      style={{ width: `${score}%` }}
                    />
                  </div>
                  <div className="description">{dim.description}</div>
                </Card>
              );
            })}
          </div>

          {evaluation.scores.reasoning && (
            <Card className="reasoning-section">
              <h3>AI Analysis Summary</h3>
              <p>{evaluation.scores.reasoning}</p>
            </Card>
          )}

          <Card className="commit-summary">
            <h3>Contribution Summary</h3>
            <div className="summary-stats">
              <div className="summary-stat">
                <div className="summary-stat-value">{evaluation.total_commits_analyzed}</div>
                <div className="summary-stat-label">Commits Analyzed</div>
              </div>
              <div className="summary-stat">
                <div className="summary-stat-value">+{evaluation.commits_summary.total_additions}</div>
                <div className="summary-stat-label">Lines Added</div>
              </div>
              <div className="summary-stat">
                <div className="summary-stat-value">-{evaluation.commits_summary.total_deletions}</div>
                <div className="summary-stat-label">Lines Deleted</div>
              </div>
              <div className="summary-stat">
                <div className="summary-stat-value">{evaluation.commits_summary.files_changed}</div>
                <div className="summary-stat-label">Files Changed</div>
              </div>
            </div>
            <div className="languages-list">
              {evaluation.commits_summary.languages.map((lang, idx) => (
                <Tag key={idx} color="purple">{lang}</Tag>
              ))}
            </div>
          </Card>
          </Spin>
        </Card>
      )}
    </div>
  );
}
