import type { ContributorComparisonData, Comparison } from '../types';
import type { Messages } from '../i18n/types';

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

interface Author {
  author: string;
  email: string;
  commits: number;
  avatar_url?: string;
}

interface RepoData {
  owner: string;
  repo: string;
  full_name: string;
}

interface MDTexts {
  titleSingle: string;
  subtitleSingle: string;
  titleMulti: string;
  subtitleMulti: string;
  repository: string;
  author: string;
  contributor: string;
  email: string;
  totalCommits: string;
  skillDimensions: string;
  contributionSummary: string;
  commitsAnalyzed: string;
  linesAdded: string;
  linesDeleted: string;
  filesChanged: string;
  languages: string;
  aiAnalysis: string;
  aggregateStats: string;
  totalRepos: string;
  repositoryBreakdown: string;
  failedRepos: string;
  commits: string;
  dimensions: {
    ai_fullstack?: string;
    ai_architecture?: string;
    cloud_native?: string;
    open_source?: string;
    intelligent_dev?: string;
    leadership?: string;
    spec_quality?: string;
    cloud_architecture?: string;
    ai_engineering?: string;
    mastery_professionalism?: string;
  };
}

/**
 * Calculate display width of a string (CJK characters count as 2, others as 1)
 */
function getDisplayWidth(str: string): number {
  let width = 0;
  for (const char of str) {
    const code = char.charCodeAt(0);
    // CJK Unified Ideographs and other wide characters
    if (
      (code >= 0x4E00 && code <= 0x9FFF) ||   // CJK Unified Ideographs
      (code >= 0x3400 && code <= 0x4DBF) ||   // CJK Unified Ideographs Extension A
      (code >= 0x20000 && code <= 0x2A6DF) || // CJK Unified Ideographs Extension B
      (code >= 0x2A700 && code <= 0x2B73F) || // CJK Unified Ideographs Extension C
      (code >= 0x2B740 && code <= 0x2B81F) || // CJK Unified Ideographs Extension D
      (code >= 0x2B820 && code <= 0x2CEAF) || // CJK Unified Ideographs Extension E
      (code >= 0x3000 && code <= 0x303F) ||   // CJK Symbols and Punctuation
      (code >= 0xFF00 && code <= 0xFFEF)      // Halfwidth and Fullwidth Forms
    ) {
      width += 2;
    } else {
      width += 1;
    }
  }
  return width;
}

/**
 * Pad string to target display width (accounting for CJK characters)
 */
function padToWidth(str: string, targetWidth: number, align: 'left' | 'right'): string {
  const currentWidth = getDisplayWidth(str);
  const paddingNeeded = Math.max(0, targetWidth - currentWidth);
  const padding = ' '.repeat(paddingNeeded);
  return align === 'left' ? str + padding : padding + str;
}

/**
 * Create localized MD texts from translations
 */
function getMDTexts(translations: Messages): MDTexts {
  return {
    titleSingle: translations['pdf.title.single'],
    subtitleSingle: translations['pdf.subtitle.single'],
    titleMulti: translations['pdf.title.multi'],
    subtitleMulti: translations['pdf.subtitle.multi'],
    repository: translations['pdf.repository'],
    author: translations['pdf.author'],
    contributor: translations['pdf.contributor'],
    email: translations['pdf.email'],
    totalCommits: translations['pdf.total_commits'],
    skillDimensions: translations['pdf.skill_dimensions'],
    contributionSummary: translations['pdf.contribution_summary'],
    commitsAnalyzed: translations['pdf.commits_analyzed'],
    linesAdded: translations['pdf.lines_added'],
    linesDeleted: translations['pdf.lines_deleted'],
    filesChanged: translations['pdf.files_changed'],
    languages: translations['pdf.languages'],
    aiAnalysis: translations['pdf.ai_analysis'],
    aggregateStats: translations['pdf.aggregate_stats'],
    totalRepos: translations['pdf.total_repos'],
    repositoryBreakdown: translations['pdf.repository_breakdown'],
    failedRepos: translations['pdf.failed_repos'],
    commits: translations['pdf.commits'],
    dimensions: {
      // zgc_simple dimensions (6)
      ai_fullstack: translations['pdf.dimension.ai_fullstack'],
      ai_architecture: translations['pdf.dimension.ai_architecture'],
      cloud_native: translations['pdf.dimension.cloud_native'],
      open_source: translations['pdf.dimension.open_source'],
      intelligent_dev: translations['pdf.dimension.intelligent_dev'],
      leadership: translations['pdf.dimension.leadership'],
      // zgc_ai_native_2026 dimensions (4)
      spec_quality: translations['plugin.zgc_ai_native_2026.dim.spec_quality'],
      cloud_architecture: translations['plugin.zgc_ai_native_2026.dim.cloud_architecture'],
      ai_engineering: translations['plugin.zgc_ai_native_2026.dim.ai_engineering'],
      mastery_professionalism: translations['plugin.zgc_ai_native_2026.dim.mastery_professionalism'],
    },
  };
}

/**
 * Create a markdown table for radar chart representation
 */
function createRadarTable(dimensions: Array<{ name: string; score: number }>): string {
  // Calculate maximum dimension name display width
  const maxNameWidth = Math.max(
    getDisplayWidth('Dimension'),
    ...dimensions.map(d => getDisplayWidth(d.name))
  );

  // Calculate maximum score width (scores are 0-100, so max 3 digits)
  const maxScoreWidth = Math.max(getDisplayWidth('Score'), 3);

  // Bar column is fixed at 20 chars (for the bar itself)
  const barWidth = Math.max(getDisplayWidth('Bar'), 20);

  // Create header with padding
  const headerDimension = padToWidth('Dimension', maxNameWidth, 'left');
  const headerScore = padToWidth('Score', maxScoreWidth, 'right');
  const headerBar = padToWidth('Bar', barWidth, 'left');
  let table = `| ${headerDimension} | ${headerScore} | ${headerBar} |\n`;

  // Create separator with proper alignment indicators
  const sepDimension = '-'.repeat(maxNameWidth);
  const sepScore = '-'.repeat(maxScoreWidth) + ':'; // Right-align scores
  const sepBar = '-'.repeat(barWidth);
  table += `| ${sepDimension} | ${sepScore} | ${sepBar} |\n`;

  // Add data rows with proper padding
  for (const dim of dimensions) {
    const barChars = Math.round(dim.score / 5); // 20 chars for 100%
    const bar = '█'.repeat(barChars) + '░'.repeat(20 - barChars);
    const namePadded = padToWidth(dim.name, maxNameWidth, 'left');
    const scorePadded = padToWidth(dim.score.toString(), maxScoreWidth, 'right');
    const barPadded = padToWidth(bar, barWidth, 'left');
    table += `| ${namePadded} | ${scorePadded} | ${barPadded} |\n`;
  }

  return table;
}

/**
 * Create a markdown table for linear chart representation
 */
function createLinearTable(data: Array<{ repo: string; values: Array<{ dimension: string; score: number }> }>): string {
  if (data.length === 0) return '';

  // Get all dimension names from first entry
  const dimensionNames = data[0].values.map(v => v.dimension);

  // Calculate maximum display width for repository column
  const maxRepoWidth = Math.max(
    getDisplayWidth('Repository'),
    ...data.map(d => getDisplayWidth(d.repo))
  );

  // Calculate maximum display widths for each dimension column (scores are 0-100, so max 3 digits)
  const dimensionWidths = dimensionNames.map(name => Math.max(getDisplayWidth(name), 3));

  // Create header with padding
  const headerRepo = padToWidth('Repository', maxRepoWidth, 'left');
  const headerDims = dimensionNames.map((name, idx) => padToWidth(name, dimensionWidths[idx], 'right'));
  let table = `| ${headerRepo} | ${headerDims.join(' | ')} |\n`;

  // Create separator with proper alignment indicators
  const sepRepo = '-'.repeat(maxRepoWidth);
  const sepDims = dimensionWidths.map(width => '-'.repeat(width) + ':'); // Right-align scores
  table += `| ${sepRepo} | ${sepDims.join(' | ')} |\n`;

  // Add data rows with proper padding
  for (const entry of data) {
    const repoPadded = padToWidth(entry.repo, maxRepoWidth, 'left');
    const scoresPadded = entry.values.map((v, idx) =>
      padToWidth(v.score.toString(), dimensionWidths[idx], 'right')
    );
    table += `| ${repoPadded} | ${scoresPadded.join(' | ')} |\n`;
  }

  return table;
}

/**
 * Download markdown content as file
 */
function downloadMarkdown(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Export home page analysis report as Markdown
 */
export async function exportHomePageMD(
  repoData: RepoData,
  author: Author,
  evaluation: Evaluation,
  translations: Messages
) {
  const texts = getMDTexts(translations);
  let md = '';

  // Header
  md += `# ${texts.titleSingle}\n\n`;
  md += `> ${texts.subtitleSingle}\n\n`;
  md += `---\n\n`;

  // Repository Info
  md += `## ${texts.repository}\n\n`;
  md += `**${repoData.full_name}**\n\n`;

  // Author Info
  md += `## ${texts.author}\n\n`;
  md += `- **Name:** ${author.author}\n`;
  md += `- **${texts.email}** ${author.email}\n`;
  md += `- **${texts.totalCommits}** ${author.commits}\n\n`;

  // Skill Dimensions
  md += `## ${texts.skillDimensions}\n\n`;

  // Dynamically determine dimensions based on evaluation scores
  const allDimensions = [
    // zgc_simple dimensions (6)
    { name: texts.dimensions.ai_fullstack, key: "ai_fullstack" },
    { name: texts.dimensions.ai_architecture, key: "ai_architecture" },
    { name: texts.dimensions.cloud_native, key: "cloud_native" },
    { name: texts.dimensions.open_source, key: "open_source" },
    { name: texts.dimensions.intelligent_dev, key: "intelligent_dev" },
    { name: texts.dimensions.leadership, key: "leadership" },
    // zgc_ai_native_2026 dimensions (4)
    { name: texts.dimensions.spec_quality, key: "spec_quality" },
    { name: texts.dimensions.cloud_architecture, key: "cloud_architecture" },
    { name: texts.dimensions.ai_engineering, key: "ai_engineering" },
    { name: texts.dimensions.mastery_professionalism, key: "mastery_professionalism" }
  ];

  // Filter to only include dimensions that exist in the evaluation scores
  const dimensions = allDimensions
    .filter(dim => dim.name && evaluation.scores[dim.key] !== undefined && evaluation.scores[dim.key] !== null)
    .map(dim => {
      const rawScore = evaluation.scores[dim.key];
      let score: number;
      if (typeof rawScore === 'number') {
        score = rawScore;
      } else if (typeof rawScore === 'string') {
        const parsed = Number(rawScore);
        score = Number.isFinite(parsed) ? parsed : 0;
      } else {
        score = 0;
      }
      // Clamp score to 0-100 range
      score = Math.max(0, Math.min(100, score));
      return { name: dim.name, score };
    });

  md += createRadarTable(dimensions);
  md += '\n';

  // Contribution Summary
  md += `## ${texts.contributionSummary}\n\n`;
  md += `- **${texts.commitsAnalyzed}** ${evaluation.total_commits_analyzed}\n`;
  md += `- **${texts.linesAdded}** +${evaluation.commits_summary.total_additions}\n`;
  md += `- **${texts.linesDeleted}** -${evaluation.commits_summary.total_deletions}\n`;
  md += `- **${texts.filesChanged}** ${evaluation.commits_summary.files_changed}\n`;

  if (evaluation.commits_summary.languages.length > 0) {
    md += `- **${texts.languages}** ${evaluation.commits_summary.languages.join(', ')}\n`;
  }
  md += '\n';

  // AI Analysis Summary
  if (evaluation.scores.reasoning) {
    md += `## ${texts.aiAnalysis}\n\n`;
    md += `${evaluation.scores.reasoning}\n\n`;
  }

  // Footer
  const timestamp = new Date().toLocaleString();
  md += `---\n\n`;
  md += `*Generated on ${timestamp}*\n`;

  // Download
  const filename = `${repoData.owner}-${repoData.repo}-${author.author.replace(/[^a-zA-Z0-9]/g, '_')}-analysis.md`;
  downloadMarkdown(md, filename);
}

/**
 * Export multi-repo comparison report as Markdown
 */
export async function exportMultiRepoMD(
  comparisonData: ContributorComparisonData,
  contributorName: string,
  translations: Messages
) {
  const texts = getMDTexts(translations);
  let md = '';

  // Header
  md += `# ${texts.titleMulti}\n\n`;
  md += `> ${texts.subtitleMulti}\n\n`;
  md += `---\n\n`;

  // Contributor Info
  md += `## ${texts.contributor}\n\n`;
  md += `**${contributorName}**\n\n`;

  // Aggregate Statistics
  if (comparisonData.aggregate) {
    md += `## ${texts.aggregateStats}\n\n`;
    const totalRepos = comparisonData.comparisons.length;
    const totalCommits = comparisonData.comparisons.reduce((sum: number, comp: Comparison) => sum + comp.total_commits, 0);
    md += `- **${texts.totalRepos}** ${totalRepos}\n`;
    md += `- **${texts.totalCommits}** ${totalCommits}\n\n`;
  }

  // Comparison Chart (as table)
  md += `## ${texts.skillDimensions}\n\n`;

  const dimensionKeys = comparisonData.dimension_keys;
  const dimensionNames = comparisonData.dimension_names;

  const chartData = comparisonData.comparisons.map(comp => ({
    repo: `${comp.owner}/${comp.repo_name}`,
    values: dimensionKeys.map((key, idx) => {
      const rawScore = (comp.scores as unknown as Record<string, any>)[key];
      let score: number;
      if (typeof rawScore === 'number') {
        score = rawScore;
      } else if (typeof rawScore === 'string') {
        const parsed = Number(rawScore);
        score = Number.isFinite(parsed) ? parsed : 0;
      } else {
        score = 0;
      }
      score = Math.max(0, Math.min(100, score));
      return { dimension: dimensionNames[idx], score };
    })
  }));

  md += createLinearTable(chartData);
  md += '\n';

  // Repository Breakdown
  md += `## ${texts.repositoryBreakdown}\n\n`;

  for (const comp of comparisonData.comparisons) {
    md += `### ${comp.owner}/${comp.repo_name}\n\n`;
    md += `- **${texts.commits}** ${comp.total_commits}\n\n`;

    md += `**${texts.skillDimensions}:**\n\n`;

    const dimensions = dimensionKeys.map((key, idx) => {
      const rawScore = (comp.scores as unknown as Record<string, any>)[key];
      let score: number;
      if (typeof rawScore === 'number') {
        score = rawScore;
      } else if (typeof rawScore === 'string') {
        const parsed = Number(rawScore);
        score = Number.isFinite(parsed) ? parsed : 0;
      } else {
        score = 0;
      }
      score = Math.max(0, Math.min(100, score));
      return { name: dimensionNames[idx], score };
    });

    md += createRadarTable(dimensions);
    md += '\n';
  }

  // Failed repositories
  if (comparisonData.failed_repos && comparisonData.failed_repos.length > 0) {
    md += `## ${texts.failedRepos}\n\n`;
    for (const failed of comparisonData.failed_repos) {
      md += `- **${failed.repo}:** ${failed.reason}\n`;
    }
    md += '\n';
  }

  // Footer
  const timestamp = new Date().toLocaleString();
  md += `---\n\n`;
  md += `*Generated on ${timestamp}*\n`;

  // Download
  const filename = `multi-repo-${contributorName.replace(/[^a-zA-Z0-9]/g, '_')}-comparison.md`;
  downloadMarkdown(md, filename);
}
