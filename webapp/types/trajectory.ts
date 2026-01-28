/**
 * TypeScript interfaces matching backend schemas from:
 * - evaluator/schemas/evaluation.py
 * - evaluator/schemas/trajectory.py
 */

// Evaluation Schemas (from evaluator/schemas/evaluation.py)

export interface ScoresSchema {
  // Legacy field names (backward compatibility)
  spec_quality?: number | null;
  cloud_architecture?: number | null;
  ai_engineering?: number | null;
  mastery_professionalism?: number | null;

  // 2026 standardized field names
  ai_fullstack?: number | null;
  ai_architecture?: number | null;
  cloud_native?: number | null;
  open_source?: number | null;
  intelligent_dev?: number | null;
  leadership?: number | null;

  reasoning: string;
}

export interface CommitsSummarySchema {
  total_additions: number;
  total_deletions: number;
  files_changed: number;
  languages: string[];
}

export interface EvaluationSchema {
  // Core fields
  username: string;
  total_commits_analyzed: number;
  files_loaded: number;
  mode: string;

  // Evaluation results
  scores: ScoresSchema;
  commits_summary: CommitsSummarySchema;

  // Chunking metadata
  chunked: boolean;
  chunks_processed: number;
  chunking_strategy?: string | null;

  // Incremental evaluation tracking
  last_commit_sha?: string | null;
  total_commits_evaluated: number;
  new_commits_count: number;
  evaluated_at: string;
  incremental: boolean;

  // Plugin metadata
  plugin: string;
  plugin_version: string;

  // Optional fields
  commit_ids?: string[] | null;
}

export interface EvaluationMetadata {
  cached: boolean;
  timestamp: string;
  source?: string | null;
}

export interface EvaluationResponseSchema {
  success: boolean;
  evaluation: EvaluationSchema;
  metadata: EvaluationMetadata;
}

// Trajectory Schemas (from evaluator/schemas/trajectory.py)

export interface CommitsRange {
  start_sha: string;
  end_sha: string;
  commit_count: number;
}

export interface TrajectoryCheckpoint {
  checkpoint_id: number;
  created_at: string;
  commits_range: CommitsRange;
  evaluation: EvaluationSchema;
  repos_analyzed?: string[] | null;
  aliases_used?: string[] | null;
}

export interface TrajectoryCache {
  username: string;
  repo_urls: string[];
  checkpoints: TrajectoryCheckpoint[];
  last_synced_sha?: string | null;
  last_synced_at?: string | null;
  total_checkpoints: number;
}

export interface TrajectoryResponse {
  success: boolean;
  trajectory?: TrajectoryCache | null;
  new_checkpoint_created: boolean;
  message: string;
  commits_pending?: number | null;
}
