import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
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

interface PDFTexts {
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
 * Create localized PDF texts from translations
 */
function getPDFTexts(translations: Messages): PDFTexts {
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
 * Renders text as HTML and converts to image for Chinese support
 * This is a workaround for jsPDF's lack of built-in Chinese font support
 */
async function renderTextAsImage(
  text: string,
  options: {
    fontSize?: number;
    fontWeight?: string;
    color?: string;
    maxWidth?: number;
  } = {}
): Promise<string> {
  const { fontSize = 16, fontWeight = 'normal', color = '#ffffff', maxWidth = 500 } = options;

  const div = document.createElement('div');
  div.style.position = 'absolute';
  div.style.left = '-9999px';
  div.style.top = '-9999px';
  div.style.padding = '10px';
  div.style.fontSize = `${fontSize}px`;
  div.style.fontWeight = fontWeight;
  div.style.color = color;
  div.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
  div.style.maxWidth = `${maxWidth}px`;
  div.style.backgroundColor = '#1A1A1A';
  div.textContent = text;

  document.body.appendChild(div);

  try {
    const canvas = await html2canvas(div, {
      backgroundColor: '#1A1A1A',
      scale: 2,
      logging: false,
    });
    return canvas.toDataURL('image/png');
  } finally {
    document.body.removeChild(div);
  }
}

/**
 * Check if text contains Chinese characters
 */
function hasChinese(text: string): boolean {
  return /[\u4e00-\u9fa5]/.test(text);
}

/**
 * Add text to PDF with Chinese support
 * If text contains Chinese, render as image; otherwise use native text
 */
async function addTextWithChineseSupport(
  pdf: jsPDF,
  text: string,
  x: number,
  y: number,
  options: {
    fontSize?: number;
    fontWeight?: 'normal' | 'bold';
    color?: [number, number, number];
    maxWidth?: number;
  } = {}
): Promise<{ height: number }> {
  const { fontSize = 12, fontWeight = 'normal', color = [255, 255, 255], maxWidth } = options;

  if (hasChinese(text)) {
    // Render Chinese text as image
    const imageData = await renderTextAsImage(text, {
      fontSize,
      fontWeight,
      color: `rgb(${color[0]}, ${color[1]}, ${color[2]})`,
      maxWidth: maxWidth || 180,
    });

    // Calculate dimensions
    const img = new Image();
    img.src = imageData;
    await new Promise((resolve) => { img.onload = resolve; });

    const imgWidth = Math.min(img.width / 10, maxWidth || 180);
    const imgHeight = (img.height / img.width) * imgWidth;

    pdf.addImage(imageData, 'PNG', x, y - imgHeight / 2, imgWidth, imgHeight);
    return { height: imgHeight };
  } else {
    // Use native text rendering for ASCII
    pdf.setFontSize(fontSize);
    pdf.setFont('helvetica', fontWeight);
    pdf.setTextColor(color[0], color[1], color[2]);

    if (maxWidth) {
      const lines = pdf.splitTextToSize(text, maxWidth);
      pdf.text(lines, x, y);
      return { height: lines.length * fontSize * 0.35 };
    } else {
      pdf.text(text, x, y);
      return { height: fontSize * 0.35 };
    }
  }
}

/**
 * Captures a canvas element (chart) as an image
 */
async function captureChart(elementId: string): Promise<string | null> {
  const element = document.getElementById(elementId);
  if (!element) return null;

  try {
    const canvas = await html2canvas(element, {
      backgroundColor: '#1A1A1A',
      scale: 2,
      logging: false
    });
    return canvas.toDataURL('image/png');
  } catch (error) {
    console.error('Error capturing chart:', error);
    return null;
  }
}

/**
 * Export home page analysis report as PDF
 */
export async function exportHomePagePDF(
  repoData: RepoData,
  author: Author,
  evaluation: Evaluation,
  translations: Messages
) {
  const texts = getPDFTexts(translations);
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 15;
  let yPos = margin;

  // Header background
  pdf.setFillColor(10, 10, 10);
  pdf.rect(0, 0, pageWidth, 45, 'F');

  // Title - ensure it doesn't wrap by using larger maxWidth
  await addTextWithChineseSupport(pdf, texts.titleSingle, margin, yPos + 12, {
    fontSize: 22,
    fontWeight: 'bold',
    color: [0, 163, 255],
    maxWidth: pageWidth - 2 * margin,
  });

  // Subtitle
  await addTextWithChineseSupport(pdf, texts.subtitleSingle, margin, yPos + 22, {
    fontSize: 11,
    color: [176, 176, 176],
  });

  yPos = 55;

  // Repository Info section with better styling
  pdf.setDrawColor(0, 163, 255);
  pdf.setLineWidth(0.3);
  pdf.line(margin, yPos - 2, pageWidth - margin, yPos - 2);

  await addTextWithChineseSupport(pdf, texts.repository, margin, yPos + 5, {
    fontSize: 13,
    fontWeight: 'bold',
    color: [0, 163, 255],
  });

  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(13);
  pdf.setTextColor(255, 255, 255);
  pdf.text(repoData.full_name, margin + 30, yPos + 5);

  yPos += 12;

  // Author Info section
  await addTextWithChineseSupport(pdf, texts.author, margin, yPos, {
    fontSize: 13,
    fontWeight: 'bold',
    color: [0, 163, 255],
  });

  await addTextWithChineseSupport(pdf, author.author, margin + 25, yPos, {
    fontSize: 13,
    color: [255, 255, 255],
  });

  yPos += 8;

  await addTextWithChineseSupport(pdf, `${texts.email} ${author.email}`, margin + 25, yPos, {
    fontSize: 9,
    color: [176, 176, 176],
  });

  yPos += 6;
  await addTextWithChineseSupport(pdf, `${texts.totalCommits} ${author.commits}`, margin + 25, yPos, {
    fontSize: 9,
    color: [176, 176, 176],
  });

  yPos += 15;

  // Capture and add radar chart with proper aspect ratio
  const chartImage = await captureChart('radar-chart-export');
  if (chartImage) {
    // Create an image to get actual dimensions
    const img = new Image();
    img.src = chartImage;
    await new Promise((resolve) => { img.onload = resolve; });

    // Calculate dimensions preserving aspect ratio
    const maxWidth = 140;
    const aspectRatio = img.height / img.width;
    const imgWidth = maxWidth;
    const imgHeight = maxWidth * aspectRatio;
    const imgX = (pageWidth - imgWidth) / 2;

    pdf.addImage(chartImage, 'PNG', imgX, yPos, imgWidth, imgHeight);
    yPos += imgHeight + 15;
  }

  // Check if we need a new page
  if (yPos > pageHeight - 80) {
    pdf.addPage();
    yPos = margin;
  }

  // Section separator
  pdf.setDrawColor(0, 163, 255);
  pdf.setLineWidth(0.3);
  pdf.line(margin, yPos - 5, pageWidth - margin, yPos - 5);

  // Dimension Scores Title
  await addTextWithChineseSupport(pdf, texts.skillDimensions, margin, yPos + 5, {
    fontSize: 15,
    fontWeight: 'bold',
    color: [0, 163, 255],
  });
  yPos += 12;

  // Dynamically determine dimensions based on evaluation scores
  // zgc_simple has 6 dimensions, zgc_ai_native_2026 has 4 dimensions
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
  const dimensions = allDimensions.filter(dim =>
    dim.name && evaluation.scores[dim.key] !== undefined && evaluation.scores[dim.key] !== null
  );

  for (const dim of dimensions) {
    if (yPos > pageHeight - 20) {
      pdf.addPage();
      yPos = margin;
    }

    // Robust score parsing (consistent with webapp plugin views)
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

    await addTextWithChineseSupport(pdf, dim.name, margin, yPos, {
      fontSize: 10,
      fontWeight: 'bold',
      color: [255, 255, 255],
    });

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);
    pdf.setTextColor(0, 163, 255);
    pdf.text(`${score}`, pageWidth - margin - 15, yPos);

    yPos += 5;

    // Progress bar
    const barWidth = pageWidth - 2 * margin;
    const barHeight = 4;

    pdf.setFillColor(51, 51, 51);
    pdf.rect(margin, yPos, barWidth, barHeight, 'F');

    pdf.setFillColor(0, 163, 255);
    pdf.rect(margin, yPos, (barWidth * score) / 100, barHeight, 'F');

    yPos += 10;
  }

  yPos += 8;

  // Contribution Summary with separator
  if (yPos > pageHeight - 60) {
    pdf.addPage();
    yPos = margin;
  }

  // Section separator
  pdf.setDrawColor(0, 163, 255);
  pdf.setLineWidth(0.3);
  pdf.line(margin, yPos - 5, pageWidth - margin, yPos - 5);

  await addTextWithChineseSupport(pdf, texts.contributionSummary, margin, yPos + 5, {
    fontSize: 15,
    fontWeight: 'bold',
    color: [0, 163, 255],
  });
  yPos += 12;

  const stats = [
    `${texts.commitsAnalyzed} ${evaluation.total_commits_analyzed}`,
    `${texts.linesAdded} +${evaluation.commits_summary.total_additions}`,
    `${texts.linesDeleted} -${evaluation.commits_summary.total_deletions}`,
    `${texts.filesChanged} ${evaluation.commits_summary.files_changed}`
  ];

  for (const stat of stats) {
    await addTextWithChineseSupport(pdf, stat, margin, yPos, {
      fontSize: 10,
      color: [255, 255, 255],
    });
    yPos += 7;
  }

  yPos += 5;

  // Languages
  if (evaluation.commits_summary.languages.length > 0) {
    await addTextWithChineseSupport(pdf, texts.languages, margin, yPos, {
      fontSize: 10,
      fontWeight: 'bold',
      color: [0, 163, 255],
    });
    yPos += 7;

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);
    pdf.setTextColor(176, 176, 176);
    pdf.text(evaluation.commits_summary.languages.join(', '), margin, yPos);
    yPos += 10;
  }

  // AI Analysis Summary
  if (evaluation.scores.reasoning) {
    if (yPos > pageHeight - 40) {
      pdf.addPage();
      yPos = margin;
    }

    // Section separator
    pdf.setDrawColor(0, 163, 255);
    pdf.setLineWidth(0.3);
    pdf.line(margin, yPos - 5, pageWidth - margin, yPos - 5);

    await addTextWithChineseSupport(pdf, texts.aiAnalysis, margin, yPos + 5, {
      fontSize: 15,
      fontWeight: 'bold',
      color: [0, 163, 255],
    });
    yPos += 12;

    const reasoning = evaluation.scores.reasoning as string;
    // Convert mm to pixels (1mm ≈ 3.78 pixels at 96 DPI)
    const maxWidthPixels = Math.floor((pageWidth - 2 * margin) * 3.78);
    await addTextWithChineseSupport(pdf, reasoning, margin, yPos, {
      fontSize: 9,
      color: [200, 200, 200],
      maxWidth: maxWidthPixels,
    });
  }

  // Footer
  const timestamp = new Date().toLocaleString();
  pdf.setFontSize(8);
  pdf.setTextColor(100, 100, 100);
  pdf.text(`Generated on ${timestamp}`, margin, pageHeight - 10);

  // Save PDF
  const filename = `${repoData.owner}-${repoData.repo}-${author.author.replace(/[^a-zA-Z0-9]/g, '_')}-analysis.pdf`;
  pdf.save(filename);
}

/**
 * Export multi-repo comparison report as PDF
 */
export async function exportMultiRepoPDF(
  comparisonData: ContributorComparisonData,
  contributorName: string,
  translations: Messages
) {
  const texts = getPDFTexts(translations);
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 15;
  let yPos = margin;

  // Header
  pdf.setFillColor(10, 10, 10);
  pdf.rect(0, 0, pageWidth, 40, 'F');

  await addTextWithChineseSupport(pdf, texts.titleMulti, margin, yPos + 10, {
    fontSize: 20,
    fontWeight: 'bold',
    color: [0, 240, 255],
  });

  await addTextWithChineseSupport(pdf, texts.subtitleMulti, margin, yPos + 18, {
    fontSize: 12,
    color: [176, 176, 176],
  });

  yPos = 50;

  // Contributor Info
  await addTextWithChineseSupport(pdf, texts.contributor, margin, yPos, {
    fontSize: 14,
    fontWeight: 'bold',
    color: [255, 235, 0],
  });

  await addTextWithChineseSupport(pdf, contributorName, margin + 35, yPos, {
    fontSize: 14,
    color: [255, 255, 255],
  });

  yPos += 15;

  // Aggregate Statistics
  if (comparisonData.aggregate) {
    await addTextWithChineseSupport(pdf, texts.aggregateStats, margin, yPos, {
      fontSize: 12,
      fontWeight: 'bold',
      color: [0, 240, 255],
    });
    yPos += 8;

    const totalRepos = comparisonData.comparisons.length;
    const totalCommits = comparisonData.comparisons.reduce((sum: number, comp: Comparison) => sum + comp.total_commits, 0);

    await addTextWithChineseSupport(pdf, `${texts.totalRepos} ${totalRepos}`, margin, yPos, {
      fontSize: 10,
      color: [255, 255, 255],
    });
    yPos += 6;

    await addTextWithChineseSupport(pdf, `${texts.totalCommits} ${totalCommits}`, margin, yPos, {
      fontSize: 10,
      color: [255, 255, 255],
    });
    yPos += 10;
  }

  // Capture and add comparison chart
  const chartImage = await captureChart('comparison-chart-export');
  if (chartImage) {
    const imgWidth = 160;
    const imgHeight = 100;
    const imgX = (pageWidth - imgWidth) / 2;

    if (yPos + imgHeight > pageHeight - margin) {
      pdf.addPage();
      yPos = margin;
    }

    pdf.addImage(chartImage, 'PNG', imgX, yPos, imgWidth, imgHeight);
    yPos += imgHeight + 15;
  }

  // Repository Comparisons
  await addTextWithChineseSupport(pdf, texts.repositoryBreakdown, margin, yPos, {
    fontSize: 14,
    fontWeight: 'bold',
    color: [255, 235, 0],
  });
  yPos += 12;

  for (const comp of comparisonData.comparisons) {
    // Check if we need a new page
    if (yPos > pageHeight - 80) {
      pdf.addPage();
      yPos = margin;
    }

    // Draw repository container box
    const boxHeight = 65;
    pdf.setDrawColor(0, 240, 255);
    pdf.setLineWidth(0.5);
    pdf.rect(margin, yPos - 5, pageWidth - 2 * margin, boxHeight);
    yPos += 3;

    // Repository name
    pdf.setFontSize(11);
    pdf.setFont('helvetica', 'bold');
    pdf.setTextColor(0, 240, 255);
    pdf.text(`${comp.owner}/${comp.repo_name}`, margin + 5, yPos);
    yPos += 7;

    // Commits
    await addTextWithChineseSupport(pdf, `${texts.commits} ${comp.total_commits}`, margin + 5, yPos, {
      fontSize: 9,
      color: [176, 176, 176],
    });
    yPos += 10;

    // Dimension scores header
    await addTextWithChineseSupport(pdf, texts.skillDimensions + ':', margin + 5, yPos, {
      fontSize: 9,
      fontWeight: 'bold',
      color: [255, 255, 255],
    });
    yPos += 6;

    // Dimension scores in a grid layout (2 columns)
    const dimensionKeys = comparisonData.dimension_keys;
    const dimensionNames = comparisonData.dimension_names;
    const col1X = margin + 10;
    const col2X = margin + 95;
    const colWidth = 80;

    for (let dimIndex = 0; dimIndex < dimensionKeys.length; dimIndex++) {
      const key = dimensionKeys[dimIndex];

      // Robust score parsing (consistent with webapp plugin views)
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
      // Clamp score to 0-100 range
      score = Math.max(0, Math.min(100, score));

      const name = dimensionNames[dimIndex];

      // Determine column position
      const isLeftColumn = dimIndex % 2 === 0;
      const xPos = isLeftColumn ? col1X : col2X;

      // Move to next row after every 2 items
      if (dimIndex % 2 === 0 && dimIndex > 0) {
        yPos += 5;
      }

      // Dimension name
      pdf.setFont('helvetica', 'normal');
      pdf.setFontSize(9);
      pdf.setTextColor(200, 200, 200);
      pdf.text(`${name}:`, xPos, yPos);

      // Score value
      pdf.setFont('helvetica', 'bold');
      pdf.setTextColor(255, 235, 0);
      pdf.text(`${score}`, xPos + colWidth - 10, yPos);
    }

    yPos += 10;
  }

  // Failed repositories
  if (comparisonData.failed_repos && comparisonData.failed_repos.length > 0) {
    if (yPos > pageHeight - 40) {
      pdf.addPage();
      yPos = margin;
    }

    await addTextWithChineseSupport(pdf, texts.failedRepos, margin, yPos, {
      fontSize: 12,
      fontWeight: 'bold',
      color: [255, 0, 107],
    });
    yPos += 8;

    for (const failed of comparisonData.failed_repos) {
      if (yPos > pageHeight - margin) {
        pdf.addPage();
        yPos = margin;
      }

      pdf.setFont('helvetica', 'normal');
      pdf.setFontSize(9);
      pdf.setTextColor(255, 255, 255);
      pdf.text(`${failed.repo}: ${failed.reason}`, margin, yPos);
      yPos += 6;
    }
  }

  // Footer
  const timestamp = new Date().toLocaleString();
  pdf.setFontSize(8);
  pdf.setTextColor(100, 100, 100);
  pdf.text(`Generated on ${timestamp}`, margin, pageHeight - 10);

  // Save PDF
  const filename = `multi-repo-${contributorName.replace(/[^a-zA-Z0-9]/g, '_')}-comparison.pdf`;
  pdf.save(filename);
}
