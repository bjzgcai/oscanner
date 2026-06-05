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

export type EvidenceLink = {
  type?: 'commit' | 'file' | 'dir' | string;
  label?: string;
  text?: string;
  url?: string;
  sha?: string;
  commit_sha?: string;
  path?: string;
  aliases?: string[];
};

// Note:
// - `scores` is intentionally flexible because different scan plugins may add extra keys.
export type SingleRepoEvaluation = {
  scores: Record<string, number | string>;
  total_commits_analyzed?: number;
  commits_summary?: SingleRepoCommitsSummary;
  plugin?: string;
  plugin_version?: string;
  plugin_scan_path?: string;
  evidence_links?: EvidenceLink[] | null;
};

export type PluginSingleRepoViewProps = {
  evaluation: SingleRepoEvaluation | null;
  title?: string;
  loading?: boolean;
  error?: string;
  repoUrl?: string;
  // i18n support (optional): webapp may pass locale + t() for plugin views to localize labels.
  locale?: string;
  t?: (key: string, params?: Record<string, string | number>) => string;
};

// -----------------------------
// Multi repo compare (view/multi_repo_compare.tsx)
// -----------------------------

export type ComparisonScore = Record<string, number>;

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

export type ContributorComparisonBaseProps = PluginMultiRepoCompareViewProps & {
  theme?: 'simple' | 'rubric';
};

// -----------------------------
// Trajectory checkpoint (view/trajectory_checkpoint.tsx)
// -----------------------------

export type TrajectoryCheckpointData = {
  checkpoint_id: number;
  created_at: string;
  commits_range: {
    start_sha: string;
    end_sha: string;
    commit_count: number;
    period_start?: string | null;
    period_end?: string | null;
    accumulated_from_periods?: number;
  };
  evaluation: {
    scores: Record<string, number | string>;
    commits_summary: {
      total_additions: number;
      total_deletions: number;
      files_changed: number;
      languages: string[];
    };
    plugin: string;
    plugin_version: string;
    total_commits_analyzed: number;
    evidence_links?: EvidenceLink[] | null;
  };
  repos_analyzed?: string[] | null;
  aliases_used?: string[] | null;
  previous_checkpoint_id?: number | null;
  growth_comparison?: {
    dimension_changes: Record<string, number>;
    overall_trend: 'increasing' | 'stable' | 'decreasing';
    improved_dimensions: string[];
    regressed_dimensions: string[];
  } | null;
};

export type PluginTrajectoryCheckpointViewProps = {
  checkpoint: TrajectoryCheckpointData;
  previousCheckpoint?: TrajectoryCheckpointData | null;
  // i18n support (optional): webapp may pass locale + t() for plugin views to localize labels.
  locale?: string;
  t?: (key: string, params?: Record<string, string | number>) => string;
};
