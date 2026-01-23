import type { Messages } from './types';

export const enUS: Messages = {
  // Navigation
  'nav.title': 'Engineer Skill Evaluator',
  'nav.analysis': 'Analysis',
  'nav.api': 'API',
  'nav.cache.tooltip':
    'When enabled, evaluations may reuse cached results + latest commits; when disabled, it forces a fresh evaluation (requires LLM key).',
  'nav.cache.on': 'cache',
  'nav.cache.off': 'no cache',
  'nav.plugin': 'Plugin',
  'nav.model': 'Model',
  'nav.language': 'Language',

  // Common
  'common.ready': 'Ready.',
  'common.expand': 'Expand',
  'common.collapse': 'Collapse',
  'common.clear': 'Clear',
  'common.save': 'Save',
  'common.cancel': 'Cancel',
  'common.fetching': 'Fetching...',
  'common.fetch': 'Fetch',
  'common.download_pdf': 'Download PDF',

  // Multi repo / main page
  'multi.repo_urls.label': 'Repository URLs (1-5 URLs, one per line)',
  'multi.repo_urls.placeholder':
    'Single:\nhttps://gitee.com/owner/repo\n\nMulti:\nhttps://github.com/owner/repo1\nhttps://gitee.com/owner/repo2',
  'multi.use_test_repo': 'Use test repos',
  'multi.llm_settings': 'LLM Settings',
  'multi.author_aliases.label': 'Author Aliases (optional, comma-separated names for the same person)',
  'multi.author_aliases.placeholder':
    'e.g., John Doe, John D, johndoe, jdoe\nGroup multiple names that belong to the same contributor',
  'multi.execution': 'Execution',
  'multi.no_logs_yet': 'No logs yet.',
  'multi.loading.common_contributors': 'Finding Common Contributors...',
  'multi.loading.working': 'Working...',
  'multi.loading.desc.common': 'Analyzing contributors across repositories...',
  'multi.loading.desc.default':
    'This may take a few minutes. Please wait while we fetch commits and files from the remote repository.',
  'multi.single.loaded_authors': 'Loaded {count} authors. Select a contributor to evaluate.',
  'multi.extraction_results': 'Extraction Results',
  'multi.common_contributors': 'Common Contributors',
  'multi.columns.status': 'Status',
  'multi.columns.repo': 'Repository',
  'multi.columns.message': 'Message',
  'multi.status.extracted': 'Extracted',
  'multi.status.skipped': 'Skipped',
  'multi.status.failed': 'Failed',
  'multi.table.contributor': 'Contributor',
  'multi.table.repos': 'Repos',
  'multi.table.commits': 'Commits',
  'multi.also_known_as': 'also known as:',
  'multi.single.analyzing_authors': 'Analyzing {count} authors from local commits',
  'multi.single.commits': '{count} commits',
  'multi.single.commits_analyzed': '{count} commits analyzed',
  'multi.select_contributor': 'Select Contributor to Evaluate:',
  'multi.select_contributor.placeholder': 'Select a contributor...',
  'multi.evaluate': 'Evaluate',
  'multi.evaluating': 'Evaluating...',
  'multi.compare_hint':
    'Select a contributor and click Evaluate to compare their six-dimensional capability scores across all repositories.',
  'multi.no_common.title': 'No Common Contributors Found',
  'multi.no_common.desc': 'The analyzed repositories do not have any contributors in common.',

  // LLM modal
  'llm.modal.title': 'LLM Settings',
  'llm.modal.path': 'Config path (saved under user directory; opening not supported):',
  'llm.gitee_token.title': 'GITEE_TOKEN (optional, to reduce Gitee API rate limiting)',
  'llm.github_token.title': 'GITHUB_TOKEN (optional, to reduce GitHub API rate limiting)',
  'llm.current_set': 'Currently set:',
  'llm.not_set': '(not set)',
  'llm.leave_empty_no_change': '(leave empty to keep unchanged)',
  'llm.openrouter': 'OpenRouter',
  'llm.openai_compat': 'OpenAI-compatible (base_url + api_key)',
  'llm.current_model': 'Current global Model:',

  // Single repo page (legacy)
  'single.input.placeholder': 'Enter repository URL (e.g., https://github.com/owner/repo or https://gitee.com/owner/repo)',
  'single.load_authors': 'Load Authors',
  'single.error.title': 'Error',
  'single.no_eval': 'No evaluation available',
  'single.pdf.no_data': 'No evaluation data available to export',
  'single.pdf.generating': 'Generating PDF report...',
  'single.pdf.success': 'PDF report downloaded successfully!',
  'single.pdf.failed': 'Failed to generate PDF report',
};


