import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

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

const dimensions = [
  { name: "AI Model Full-Stack", key: "ai_fullstack" },
  { name: "AI Native Architecture", key: "ai_architecture" },
  { name: "Cloud Native Engineering", key: "cloud_native" },
  { name: "Open Source Collaboration", key: "open_source" },
  { name: "Intelligent Development", key: "intelligent_dev" },
  { name: "Engineering Leadership", key: "leadership" }
];

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
  isCached: boolean
) {
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 15;
  let yPos = margin;

  // Header
  pdf.setFillColor(10, 10, 10);
  pdf.rect(0, 0, pageWidth, 40, 'F');

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(20);
  pdf.setTextColor(255, 235, 0);
  pdf.text('Engineer Skill Analysis Report', margin, yPos + 10);

  pdf.setFontSize(12);
  pdf.setTextColor(176, 176, 176);
  pdf.text('LLM-Powered Six-Dimensional Capability Analysis', margin, yPos + 18);

  yPos = 50;

  // Repository and Author Info
  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(255, 235, 0);
  pdf.text('Repository:', margin, yPos);

  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(255, 255, 255);
  pdf.text(repoData.full_name, margin + 30, yPos);

  yPos += 10;

  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(255, 235, 0);
  pdf.text('Author:', margin, yPos);

  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(255, 255, 255);
  pdf.text(author.author, margin + 30, yPos);

  yPos += 7;

  pdf.setFontSize(10);
  pdf.setTextColor(176, 176, 176);
  pdf.text(`Email: ${author.email}`, margin + 30, yPos);

  yPos += 7;
  pdf.text(`Total Commits: ${author.commits}`, margin + 30, yPos);

  yPos += 10;

  // Analysis Badge
  pdf.setFontSize(10);
  if (isCached) {
    pdf.setTextColor(82, 196, 26);
    pdf.text('⚡ Cached Result', margin, yPos);
  } else {
    pdf.setTextColor(147, 51, 234);
    pdf.text('🤖 AI-Powered Analysis', margin, yPos);
  }

  yPos += 15;

  // Capture and add radar chart
  const chartImage = await captureChart('radar-chart-export');
  if (chartImage) {
    const imgWidth = 120;
    const imgHeight = 120;
    const imgX = (pageWidth - imgWidth) / 2;

    pdf.addImage(chartImage, 'PNG', imgX, yPos, imgWidth, imgHeight);
    yPos += imgHeight + 10;
  }

  // Check if we need a new page
  if (yPos > pageHeight - 80) {
    pdf.addPage();
    yPos = margin;
  }

  // Dimension Scores
  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(255, 235, 0);
  pdf.text('Skill Dimensions', margin, yPos);
  yPos += 10;

  pdf.setFontSize(10);
  dimensions.forEach((dim, index) => {
    if (yPos > pageHeight - 20) {
      pdf.addPage();
      yPos = margin;
    }

    const score = evaluation.scores[dim.key] || 0;

    pdf.setFont('helvetica', 'bold');
    pdf.setTextColor(255, 255, 255);
    pdf.text(dim.name, margin, yPos);

    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(255, 235, 0);
    pdf.text(`${score}`, pageWidth - margin - 15, yPos);

    yPos += 5;

    // Progress bar
    const barWidth = pageWidth - 2 * margin;
    const barHeight = 4;

    // Background
    pdf.setFillColor(51, 51, 51);
    pdf.rect(margin, yPos, barWidth, barHeight, 'F');

    // Progress
    pdf.setFillColor(255, 235, 0);
    pdf.rect(margin, yPos, (barWidth * (score as number)) / 100, barHeight, 'F');

    yPos += 10;
  });

  yPos += 5;

  // Commit Summary
  if (yPos > pageHeight - 60) {
    pdf.addPage();
    yPos = margin;
  }

  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(255, 235, 0);
  pdf.text('Contribution Summary', margin, yPos);
  yPos += 10;

  pdf.setFontSize(10);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(255, 255, 255);

  const stats = [
    `Commits Analyzed: ${evaluation.total_commits_analyzed}`,
    `Lines Added: +${evaluation.commits_summary.total_additions}`,
    `Lines Deleted: -${evaluation.commits_summary.total_deletions}`,
    `Files Changed: ${evaluation.commits_summary.files_changed}`
  ];

  stats.forEach(stat => {
    pdf.text(stat, margin, yPos);
    yPos += 7;
  });

  yPos += 5;

  // Languages
  if (evaluation.commits_summary.languages.length > 0) {
    pdf.setFont('helvetica', 'bold');
    pdf.setTextColor(255, 235, 0);
    pdf.text('Languages:', margin, yPos);
    yPos += 7;

    pdf.setFont('helvetica', 'normal');
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

    pdf.setFontSize(14);
    pdf.setFont('helvetica', 'bold');
    pdf.setTextColor(255, 235, 0);
    pdf.text('AI Analysis Summary', margin, yPos);
    yPos += 10;

    pdf.setFontSize(9);
    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(176, 176, 176);

    const reasoning = evaluation.scores.reasoning as string;
    const lines = pdf.splitTextToSize(reasoning, pageWidth - 2 * margin);

    lines.forEach((line: string) => {
      if (yPos > pageHeight - margin) {
        pdf.addPage();
        yPos = margin;
      }
      pdf.text(line, margin, yPos);
      yPos += 5;
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
  comparisonData: any,
  contributorName: string
) {
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 15;
  let yPos = margin;

  // Header
  pdf.setFillColor(10, 10, 10);
  pdf.rect(0, 0, pageWidth, 40, 'F');

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(20);
  pdf.setTextColor(0, 240, 255);
  pdf.text('Multi-Repo Analysis Report', margin, yPos + 10);

  pdf.setFontSize(12);
  pdf.setTextColor(176, 176, 176);
  pdf.text('Cross-Repository Contributor Comparison', margin, yPos + 18);

  yPos = 50;

  // Contributor Info
  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(255, 235, 0);
  pdf.text('Contributor:', margin, yPos);

  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(255, 255, 255);
  pdf.text(contributorName, margin + 35, yPos);

  yPos += 15;

  // Aggregate Statistics
  if (comparisonData.aggregate) {
    pdf.setFontSize(12);
    pdf.setFont('helvetica', 'bold');
    pdf.setTextColor(0, 240, 255);
    pdf.text('Aggregate Statistics', margin, yPos);
    yPos += 8;

    pdf.setFontSize(10);
    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(255, 255, 255);

    const totalRepos = comparisonData.comparisons.length;
    const totalCommits = comparisonData.comparisons.reduce(
      (sum: number, comp: any) => sum + comp.total_commits,
      0
    );

    pdf.text(`Total Repositories: ${totalRepos}`, margin, yPos);
    yPos += 6;
    pdf.text(`Total Commits: ${totalCommits}`, margin, yPos);
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
  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(255, 235, 0);
  pdf.text('Repository Breakdown', margin, yPos);
  yPos += 10;

  comparisonData.comparisons.forEach((comp: any, index: number) => {
    if (yPos > pageHeight - 60) {
      pdf.addPage();
      yPos = margin;
    }

    // Repository name
    pdf.setFontSize(12);
    pdf.setFont('helvetica', 'bold');
    pdf.setTextColor(0, 240, 255);
    pdf.text(`${comp.owner}/${comp.repo_name}`, margin, yPos);
    yPos += 6;

    // Commits and cached status
    pdf.setFontSize(9);
    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(176, 176, 176);
    pdf.text(
      `Commits: ${comp.total_commits} | ${comp.cached ? 'Cached' : 'Fresh Analysis'}`,
      margin,
      yPos
    );
    yPos += 8;

    // Dimension scores
    pdf.setFontSize(9);
    const dimensionKeys = comparisonData.dimension_keys;
    const dimensionNames = comparisonData.dimension_names;

    dimensionKeys.forEach((key: string, dimIndex: number) => {
      if (yPos > pageHeight - margin) {
        pdf.addPage();
        yPos = margin;
      }

      const score = comp.scores[key] || 0;
      const name = dimensionNames[dimIndex];

      pdf.setTextColor(255, 255, 255);
      pdf.text(`${name}:`, margin + 5, yPos);

      pdf.setTextColor(255, 235, 0);
      pdf.text(`${score}`, margin + 80, yPos);

      yPos += 5;
    });

    yPos += 8;
  });

  // Failed repositories
  if (comparisonData.failed_repos && comparisonData.failed_repos.length > 0) {
    if (yPos > pageHeight - 40) {
      pdf.addPage();
      yPos = margin;
    }

    pdf.setFontSize(12);
    pdf.setFont('helvetica', 'bold');
    pdf.setTextColor(255, 0, 107);
    pdf.text('Failed Repositories', margin, yPos);
    yPos += 8;

    pdf.setFontSize(9);
    pdf.setFont('helvetica', 'normal');

    comparisonData.failed_repos.forEach((failed: any) => {
      if (yPos > pageHeight - margin) {
        pdf.addPage();
        yPos = margin;
      }

      pdf.text(`${failed.repo}: ${failed.reason}`, margin, yPos);
      yPos += 6;
    });
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
