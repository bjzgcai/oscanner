import { getApiBaseUrl } from './apiBase';

const API_BASE = getApiBaseUrl();

export interface DatasetStatsResponse {
  success: boolean;
  dataset_path: string;
  total_repos: number;
  repos: any[];
}

export interface ReposResponse {
  success: boolean;
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  repos: any[];
}

export interface ValidationRunResponse {
  success: boolean;
  run_id: string;
  message?: string;
  result?: any;
  overall_passed?: boolean;
  overall_score?: number;
  validation_results?: any[];
}

export interface ValidationRunsListResponse {
  success: boolean;
  runs: any[];
}

export interface ValidationRunDetailResponse {
  success: boolean;
  run: any;
}

export interface RepoEvaluationResponse {
  success: boolean;
  evaluation: any;
}

/**
 * Validation API utility functions
 */
export const validationApi = {
  /**
   * Get dataset info and statistics
   */
  getDatasetInfo: async (): Promise<DatasetStatsResponse> => {
    const response = await fetch(`${API_BASE}/api/benchmark/dataset`);
    if (!response.ok) {
      throw new Error(`Failed to fetch dataset info: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get paginated list of benchmark repos
   */
  getRepos: async (params: {
    page?: number;
    per_page?: number;
    category?: string;
  }): Promise<ReposResponse> => {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', params.page.toString());
    if (params.per_page) searchParams.set('per_page', params.per_page.toString());
    if (params.category) searchParams.set('category', params.category);

    const url = `${API_BASE}/api/benchmark/repos${
      searchParams.toString() ? `?${searchParams.toString()}` : ''
    }`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch repos: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Run validation tests
   */
  runValidation: async (config: {
    subset?: string;
    quick_mode?: boolean;
    plugin_id?: string;
    model?: string;
  }): Promise<ValidationRunResponse> => {
    const response = await fetch(`${API_BASE}/api/benchmark/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Validation failed: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * List all validation runs
   */
  listRuns: async (): Promise<ValidationRunsListResponse> => {
    const response = await fetch(`${API_BASE}/api/benchmark/validation/runs`);
    if (!response.ok) {
      throw new Error(`Failed to fetch validation runs: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get specific validation run details
   */
  getRun: async (runId: string): Promise<ValidationRunDetailResponse> => {
    const response = await fetch(`${API_BASE}/api/benchmark/validation/runs/${runId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch run details: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get cached evaluation for a specific repo/author
   */
  getRepoEvaluation: async (
    platform: string,
    owner: string,
    repo: string,
    author: string,
    pluginId?: string
  ): Promise<RepoEvaluationResponse> => {
    const searchParams = new URLSearchParams();
    if (pluginId) searchParams.set('plugin_id', pluginId);
    searchParams.set('use_cache', 'true');

    const url = `${API_BASE}/api/benchmark/repo/${platform}/${owner}/${repo}/${encodeURIComponent(
      author
    )}${searchParams.toString() ? `?${searchParams.toString()}` : ''}`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch repo evaluation: ${response.statusText}`);
    }
    return response.json();
  },
};
