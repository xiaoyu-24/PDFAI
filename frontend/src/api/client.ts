import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api",
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
