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
  cached: boolean;
}

export interface ContributorComparisonData {
  success: boolean;
  contributor: string;
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


