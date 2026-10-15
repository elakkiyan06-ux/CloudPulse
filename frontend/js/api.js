/**
 * CloudPulse REST API Client
 * Wraps all backend endpoints with robust error handling and typed responses.
 */

const API_BASE = '/api';

class ApiClient {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (!response.ok) {
        let errData;
        try {
          errData = await response.json();
        } catch (e) {
          errData = { detail: response.statusText };
        }
        throw new Error(errData.detail || `HTTP Error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error);
      throw error;
    }
  }

  // System & Health
  async getSystemStatus() {
    return this.request('/system/status');
  }

  async getDbStatus() {
    return this.request('/database/status');
  }

  async checkDbConnection(connectionUrl = null) {
    return this.request('/database/check', {
      method: 'POST',
      body: JSON.stringify({ connection_url: connectionUrl }),
    });
  }

  // Real-Time Weather Pipeline (Open-Meteo -> AWS RDS)
  async fetchLiveWeather() {
    return this.request('/weather/fetch', { method: 'POST' });
  }

  async getLiveWeather(page = 1, pageSize = 20, locationName = '') {
    const params = new URLSearchParams({
      page,
      page_size: pageSize,
      ...(locationName && locationName !== 'ALL' && { location_name: locationName }),
    });
    return this.request(`/weather/live?${params.toString()}`);
  }

  async getWeatherLocations() {
    return this.request('/weather/locations');
  }

  // Dataset Explorer (Live weather observations)
  async getRecords(page = 1, pageSize = 20, search = '', category = '', region = '') {
    const params = new URLSearchParams({
      page,
      page_size: pageSize,
      ...(search && { search }),
      ...(category && category !== 'ALL' && { category }),
      ...(region && region !== 'ALL' && { region }),
    });
    return this.request(`/database/records?${params.toString()}`);
  }

  async getDbStatistics() {
    return this.request('/database/statistics');
  }

  async seedDataset(count = 100, batchSize = 100) {
    return this.request('/database/seed', {
      method: 'POST',
      body: JSON.stringify({ count, batch_size: batchSize }),
    });
  }

  async verifyRecordCount(expectedCount = null) {
    const params = expectedCount !== null ? `?expected_count=${expectedCount}` : '';
    return this.request(`/database/verify-count${params}`, {
      method: 'POST',
    });
  }

  async resetDataset() {
    return this.request('/database/reset', { method: 'POST' });
  }

  async cleanupResources() {
    return this.request('/database/cleanup', { method: 'POST' });
  }

  // Benchmark Studio
  async createBenchmark(payload) {
    return this.request('/benchmarks', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async listBenchmarks(workloadType = null, status = null, limit = 50) {
    const params = new URLSearchParams({
      limit,
      ...(workloadType && workloadType !== 'ALL' && { workload_type: workloadType }),
      ...(status && status !== 'ALL' && { status }),
    });
    return this.request(`/benchmarks?${params.toString()}`);
  }

  async getBenchmarkStatus(runId) {
    return this.request(`/benchmarks/${runId}/status`);
  }

  async cancelBenchmark(runId) {
    return this.request(`/benchmarks/${runId}/cancel`, { method: 'POST' });
  }

  async compareBenchmarks(baselineId, optimizedId) {
    return this.request(`/benchmarks/compare?baseline_id=${baselineId}&optimized_id=${optimizedId}`);
  }

  // Optimization Lab
  async listOptimizationExperiments() {
    return this.request('/optimization/experiments');
  }

  async runOptimizationExperiment(payload) {
    return this.request('/optimization/experiments', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async applyIndex(indexName) {
    return this.request(`/optimization/apply-index?index_name=${encodeURIComponent(indexName)}`, {
      method: 'POST',
    });
  }

  async rollbackIndex(indexName) {
    return this.request(`/optimization/rollback-index?index_name=${encodeURIComponent(indexName)}`, {
      method: 'POST',
    });
  }

  // Query Plan Explorer
  async explainQuery(queryType = 'CATEGORY_FILTER', filterValue = 'Cloud Services', analyze = true) {
    return this.request('/query-plans/explain', {
      method: 'POST',
      body: JSON.stringify({
        query_type: queryType,
        filter_value: filterValue,
        analyze,
      }),
    });
  }

  // Cloud Monitoring
  async getCloudMetrics() {
    return this.request('/cloud/metrics');
  }

  // Reports
  async generateReport(format = 'markdown', runIds = null, experimentId = null) {
    return this.request('/reports/generate', {
      method: 'POST',
      body: JSON.stringify({ format, run_ids: runIds, experiment_id: experimentId }),
    });
  }

  getReportDownloadUrl(format = 'markdown') {
    return `${API_BASE}/reports/download?format=${format}`;
  }

  // Logs
  async getLogs(severity = null, eventType = null, limit = 100) {
    const params = new URLSearchParams({
      limit,
      ...(severity && severity !== 'ALL' && { severity }),
      ...(eventType && eventType !== 'ALL' && { event_type: eventType }),
    });
    return this.request(`/logs?${params.toString()}`);
  }

  async clearLogs() {
    return this.request('/logs/clear', { method: 'POST' });
  }

  // Settings
  async getSettings() {
    return this.request('/settings');
  }
}

export const api = new ApiClient();
