import axios from "axios";

const DEFAULT_API_BASE_URL = "/api";

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  const baseUrl = configured || DEFAULT_API_BASE_URL;
  return baseUrl.replace(/\/+$/, "") || DEFAULT_API_BASE_URL;
}

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return Promise.reject(new Error(detail));
    }
    if (Array.isArray(detail)) {
      const message = detail
        .map((item) => item?.msg)
        .filter(Boolean)
        .join("; ");
      if (message) {
        return Promise.reject(new Error(message));
      }
    }
    return Promise.reject(error instanceof Error ? error : new Error("请求失败"));
  }
);

export default apiClient;
