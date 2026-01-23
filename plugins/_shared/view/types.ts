// Shared input types for plugin views.
//
// Goal: plugin authors should be able to implement `plugins/<id>/view/*.tsx`
// without guessing what data shape the webapp passes in.

// -----------------------------
// Single repo evaluation (view/single_repo.tsx)
// -----------------------------

export type SingleRepoCommitsSummary = {
  total_additions: number;
  total_deletions: number;
  files_changed: number;
  languages: string[];
};

// Note:
// - `scores` is intentionally flexible because different scan plugins may add extra keys
//   (but the dashboard expects six dimension keys + optional reasoning string).
export type SingleRepoEvaluation = {
  scores: Record<string, number | string>;
  total_commits_analyzed?: number;
  commits_summary?: SingleRepoCommitsSummary;
  plugin?: string;
  plugin_version?: string;
  plugin_scan_path?: string;
};

export type PluginSingleRepoViewProps = {
  evaluation: SingleRepoEvaluation | null;
  title?: string;
  loading?: boolean;
  error?: string;
  // i18n support (optional): webapp may pass locale + t() for plugin views to localize labels.
  locale?: string;
  t?: (key: string, params?: Record<string, string | number>) => string;
};

// -----------------------------
// Multi repo compare (view/multi_repo_compare.tsx)
// -----------------------------

export type ComparisonScore = {
  ai_model_fullstack: number;
  ai_native_architecture: number;
  cloud_native: number;
  open_source_collaboration: number;
  intelligent_development: number;
  engineering_leadership: number;
};

export type Comparison = {
  repo: string;
  owner: string;
  repo_name: string;
  scores: ComparisonScore;
  total_commits: number;
  plugin?: string;
  plugin_version?: string;
  plugin_scan_path?: string;
};

export type ContributorComparisonData = {
  success: boolean;
  message?: string;
  contributor: string;
  plugin_requested?: string | null;
  plugin_used?: string;
  comparisons: Comparison[];
  dimension_keys: string[];
  dimension_names: string[];
  aggregate: {
    total_repos_evaluated: number;
    total_commits: number;
    average_scores: ComparisonScore;
  };
  failed_repos?: Array<{ repo: string; reason: string }>;
};

export type PluginMultiRepoCompareViewProps = {
  data: ContributorComparisonData | null;
  loading?: boolean;
  error?: string;
  // i18n support (optional): webapp may pass locale + t() for plugin views to localize labels.
  locale?: string;
  t?: (key: string, params?: Record<string, string | number>) => string;
};


