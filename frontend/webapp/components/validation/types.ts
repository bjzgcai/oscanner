/**
 * TypeScript interfaces for validation system
 */

export type SkillLevel = 'novice' | 'intermediate' | 'senior' | 'architect' | 'expert';

export interface TestRepository {
  entry_id?: string | null;
  language?: string | null;
  level?: string | null;
  status?: string | null;
  platform: string;
  owner: string;
  repo: string;
  author: string;
  skill_level: SkillLevel | null;
  expected_score_range: [number, number] | null;
  strong_dimensions: string[];
  weak_dimensions?: string[];
  expected_dimension_scores?: Record<string, [number, number]>;
  category: string;
  description: string;
  public_reputation?: string | null;
  time_period?: string | null;
  temporal_group?: string | null;
  is_ground_truth: boolean;
  is_edge_case: boolean;
  repo_url: string;
  identifier: string;
  is_pinned?: boolean;
}

export type DimensionScore = Record<string, number | undefined>;

export interface BenchmarkEvaluationResult {
  repo: {
    platform: string;
    owner: string;
    repo: string;
    author: string;
    category: string;
    skill_level: SkillLevel | null;
  };
  overall_score: number;
  dimension_scores: DimensionScore;
  evaluation_data: unknown;
  timestamp: string;
  error: string | null;
}

export interface ValidationResult {
  test_name: string;
  passed: boolean;
  score: number; // 0-100
  details: Record<string, unknown>;
  errors: string[];
  warnings: string[];
  timestamp: string;
}

export interface JusticeCheck {
  id: string;
  label: string;
  status: 'PASS' | 'WARN' | 'FAIL';
  score: number | null;
  source_tests: string[];
  failed_cases: string[];
  warnings: string[];
}

export interface JusticeProfile {
  overall_status: string;
  summary: {
    pass: number;
    warn: number;
    fail: number;
  };
  checks: JusticeCheck[];
  aggregate: {
    score: number | null;
    authoritative: boolean;
    label: string;
  };
}

export interface DatasetStats {
  total: number;
  ground_truth: number;
  edge_cases: number;
  categories: number;
  platforms: number;
  novice: number;
  intermediate: number;
  senior: number;
  architect: number;
  expert: number;
}

export interface ValidationRunResult {
  run_id: string;
  timestamp: string;
  dataset_stats: DatasetStats;
  evaluation_count: number;
  validation_results: ValidationResult[];
  overall_passed: boolean;
  overall_score: number; // 0-100
  duration_seconds: number;
  justice_profile?: JusticeProfile;
}

export interface LogEntry {
  message: string;
  type: 'info' | 'error' | 'success' | 'warning';
  timestamp: number;
}

export type ViewMode = 'dataset' | 'run' | 'results';
