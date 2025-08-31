import axios from "axios";
import { auth } from "./firebase";

// Create axios instance with base configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  // Don't set default Content-Type - let axios detect it based on data type
  // For FormData, axios will set multipart/form-data with boundary
  // For JSON, axios will set application/json
});

// Helper function for case-insensitive header check
function hasHeader(headers: Record<string, any>, headerName: string): boolean {
  return Object.keys(headers).some(
    key => key.toLowerCase() === headerName.toLowerCase()
  );
}

// Request interceptor to add auth token and set content type
api.interceptors.request.use(
  async (config) => {
    try {
      const user = auth.currentUser;
      if (user) {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
      }
      
      // Set Content-Type based on data type if not already set
      if (!hasHeader(config.headers, 'content-type')) {
        if (config.data instanceof FormData) {
          // Let axios handle multipart/form-data boundary
          // Don't set Content-Type for FormData
        } else if (config.data && typeof config.data === "object") {
          // Set JSON content type for object data
          config.headers["Content-Type"] = "application/json";
        }
      }
    } catch (error) {
      console.error("Error getting auth token:", error);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If the error is 401 and we haven't already tried to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const user = auth.currentUser;
        if (user) {
          // Force token refresh
          await user.getIdToken(true);
          // Retry the original request
          return api(originalRequest);
        }
      } catch (refreshError) {
        console.error("Token refresh failed:", refreshError);
        // Redirect to login if token refresh fails
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  },
);

export default api;
