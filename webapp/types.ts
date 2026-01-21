export interface Score {
  ai_model_fullstack: number;
  ai_native_architecture: number;
  cloud_native: number;
  open_source_collaboration: number;
  intelligent_development: number;
  engineering_leadership: number;
}

export interface Comparison {
  repo: string;
  owner: string;
  repo_name: string;
  scores: Score;
  total_commits: number;
  plugin?: string;
  plugin_version?: string;
  plugin_scan_path?: string;
}

export interface ContributorComparisonData {
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
    average_scores: Score;
  };
  failed_repos?: Array<{ repo: string; reason: string }>;
}


