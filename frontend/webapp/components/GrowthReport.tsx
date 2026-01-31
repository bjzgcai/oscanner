'use client';

import { Card, Button, Space, Divider } from 'antd';
import { DownloadOutlined, TrophyOutlined } from '@ant-design/icons';
import { useI18n } from './I18nContext';
import { TrajectoryCache, TrajectoryCheckpoint } from '@/types/trajectory';

interface GrowthReportProps {
  trajectory: TrajectoryCache;
}

export default function GrowthReport({ trajectory }: GrowthReportProps) {
  const { t } = useI18n();

  if (!trajectory || trajectory.total_checkpoints === 0) {
    return null;
  }

  const checkpoints = trajectory.checkpoints;
  const latestCheckpoint = checkpoints[checkpoints.length - 1];
  const firstCheckpoint = checkpoints[0];

  // Get plugin ID from the first checkpoint
  const pluginId = firstCheckpoint.evaluation.plugin;

  // Extract dimension keys dynamically from scores (excluding 'reasoning')
  const getDimensionKeys = (scores: any): string[] => {
    return Object.keys(scores).filter(
      (key) => key !== 'reasoning' && scores[key] !== null && scores[key] !== undefined
    );
  };

  // Get all dimension keys from first checkpoint
  const dimensionKeys = getDimensionKeys(firstCheckpoint.evaluation.scores);

  // Calculate metrics
  const getDimensionScores = (checkpoint: TrajectoryCheckpoint) => {
    const scores: any = checkpoint.evaluation.scores;
    const result: Record<string, number> = {};
    dimensionKeys.forEach((key) => {
      result[key] = scores[key] ?? 0;
    });
    return result;
  };

  // Get dimension label with plugin-specific translation
  const getDimensionLabel = (dimensionKey: string): string => {
    const pluginSpecificKey = `plugin.${pluginId}.dim.${dimensionKey}`;
    const translated = t(pluginSpecificKey);
    // If translation not found, fall back to generic dimension key
    if (translated === pluginSpecificKey) {
      return t(`dimensions.${dimensionKey}`) || dimensionKey;
    }
    return translated;
  };

  const firstScores = getDimensionScores(firstCheckpoint);
  const latestScores = getDimensionScores(latestCheckpoint);

  // Calculate improvements
  const improvements = Object.keys(firstScores).map((key) => {
    const dimension = key as keyof typeof firstScores;
    const change = latestScores[dimension] - firstScores[dimension];
    const percentChange =
      firstScores[dimension] > 0
        ? (change / firstScores[dimension]) * 100
        : change > 0
        ? 100
        : 0;
    return {
      dimension,
      change,
      percentChange,
      current: latestScores[dimension],
      first: firstScores[dimension],
    };
  });

  // Total commits analyzed
  const totalCommits = checkpoints.reduce(
    (sum, cp) => sum + cp.evaluation.total_commits_analyzed,
    0
  );

  // Time span
  const firstDate = new Date(firstCheckpoint.created_at);
  const latestDate = new Date(latestCheckpoint.created_at);
  const daysBetween = Math.ceil(
    (latestDate.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24)
  );

  // Average score
  const avgScore = (scores: any) => {
    const values = Object.values(scores) as number[];
    return values.reduce((a, b) => a + b, 0) / values.length;
  };

  const avgFirst = avgScore(firstScores);
  const avgLatest = avgScore(latestScores);
  const avgImprovement = avgLatest - avgFirst;

  // Generate markdown report
  const generateMarkdown = () => {
    // Build dimension names dynamically from actual dimensions
    const dimensionNames: { [key: string]: string } = {};
    dimensionKeys.forEach((key) => {
      dimensionNames[key] = getDimensionLabel(key);
    });

    const getTrend = (change: number) => (change > 0 ? '↑' : change < 0 ? '↓' : '→');

    const markdown = `# ${t('trajectory.report.title')} - ${trajectory.username}

## ${t('trajectory.report.summary')}

- **${t('trajectory.report.total_commits')}**: ${totalCommits}
- **${t('trajectory.report.avg_improvement')}**: ${avgImprovement.toFixed(2)} ${t('trajectory.report.points')}

## ${t('trajectory.report.key_achievements')}

${improvements
  .map(
    (imp, idx) =>
      `${idx + 1}. **${dimensionNames[imp.dimension]}**: ${imp.first} → ${imp.current} (+${imp.change.toFixed(
        1
      )} ${t('trajectory.report.points')})`
  )
  .join('\n')}

## ${t('trajectory.report.dimension_analysis')}

${Object.keys(firstScores)
  .map((key) => {
    const dimension = key as keyof typeof firstScores;
    const current = latestScores[dimension];
    const first = firstScores[dimension];
    const change = current - first;
    const trend = getTrend(change);
    const percentChange = first > 0 ? ((change / first) * 100).toFixed(1) : '0';

    return `### ${dimensionNames[key]}

- **${t('trajectory.report.current_score')}**: ${current}/100
- **${t('trajectory.report.trend')}**: ${trend} ${change >= 0 ? '+' : ''}${change.toFixed(1)} (${percentChange}%)
- **${t('trajectory.report.level')}**: ${current >= 80 ? 'L5' : current >= 60 ? 'L4' : current >= 40 ? 'L3' : current >= 20 ? 'L2' : 'L1'}`;
  })
  .join('\n\n')}

## ${t('trajectory.report.recent_activity')}

- **${t('trajectory.report.latest_checkpoint')}**: #${latestCheckpoint.checkpoint_id}
- **${t('trajectory.report.date')}**: ${new Date(latestCheckpoint.created_at).toLocaleString()}
- **${t('trajectory.report.commits_analyzed')}**: ${latestCheckpoint.commits_range.commit_count}
- **${t('trajectory.report.additions')}**: ${latestCheckpoint.evaluation.commits_summary.total_additions}
- **${t('trajectory.report.deletions')}**: ${latestCheckpoint.evaluation.commits_summary.total_deletions}
- **${t('trajectory.report.files_changed')}**: ${latestCheckpoint.evaluation.commits_summary.files_changed}

## ${t('trajectory.report.recommendations')}

${improvements
  .filter((imp) => imp.current < 60)
  .map((imp) => `- **${dimensionNames[imp.dimension]}**: ${t('trajectory.report.needs_improvement')} (${t('trajectory.report.current')}: ${imp.current})`)
  .join('\n') || t('trajectory.report.no_recommendations')}

---

*${t('trajectory.report.generated_at')}: ${new Date().toLocaleString()}*
`;

    return markdown;
  };

  const exportReport = () => {
    const markdown = generateMarkdown();
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${trajectory.username}_growth_report_${new Date()
      .toISOString()
      .split('T')[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <TrophyOutlined />
          {t('trajectory.report.title')}
        </div>
      }
      extra={
        <Button icon={<DownloadOutlined />} onClick={exportReport}>
          {t('trajectory.report.export')}
        </Button>
      }
    >
      <Space orientation="vertical" size="large" style={{ width: '100%' }}>
        {/* Summary Statistics */}
        <div>
          <h4>{t('trajectory.report.summary')}</h4>
          <ul>
            <li>
              <strong>{t('trajectory.report.total_commits')}:</strong> {totalCommits}
            </li>
            <li>
              <strong>{t('trajectory.report.avg_improvement')}:</strong>{' '}
              {avgImprovement >= 0 ? '+' : ''}
              {avgImprovement.toFixed(2)} {t('trajectory.report.points')}
            </li>
          </ul>
        </div>

        <Divider />

        {/* Key Achievements */}
        <div>
          <h4>{t('trajectory.report.key_achievements')}</h4>
          <ul>
            {improvements.map((imp, idx) => (
              <li key={imp.dimension}>
                <strong>{getDimensionLabel(imp.dimension)}:</strong> {imp.first} → {imp.current}{' '}
                (+{imp.change.toFixed(1)} {t('trajectory.report.points')})
              </li>
            ))}
          </ul>
        </div>

        <Divider />

        {/* Recommendations */}
        <div>
          <h4>{t('trajectory.report.recommendations')}</h4>
          {improvements.filter((imp) => imp.current < 60).length > 0 ? (
            <ul>
              {improvements
                .filter((imp) => imp.current < 60)
                .map((imp) => (
                  <li key={imp.dimension}>
                    <strong>{getDimensionLabel(imp.dimension)}:</strong>{' '}
                    {t('trajectory.report.needs_improvement')} ({t('trajectory.report.current')}:{' '}
                    {imp.current})
                  </li>
                ))}
            </ul>
          ) : (
            <p>{t('trajectory.report.no_recommendations')}</p>
          )}
        </div>
      </Space>
    </Card>
  );
}
