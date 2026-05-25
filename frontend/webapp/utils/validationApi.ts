import { getApiBaseUrl } from './apiBase';
import type {
  DatasetStats,
  TestRepository,
  ValidationResult,
  ValidationRunResult,
} from '../components/validation/types';

const API_BASE = getApiBaseUrl();

export interface DatasetStatsResponse {
  success: boolean;
  dataset_path: string;
  total_repos: number;
  stats?: DatasetStats;
  categories?: string[];
  pinning?: {
    total: number;
    pinned: number;
    unpinned: number;
  };
  repos: TestRepository[];
}

export interface ReposResponse {
  success: boolean;
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  repos: TestRepository[];
}

export interface ValidationRunResponse {
  success: boolean;
  run_id: string;
  message?: string;
  result?: ValidationRunResult;
  overall_passed?: boolean;
  overall_score?: number;
  validation_results?: ValidationResult[];
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
};
