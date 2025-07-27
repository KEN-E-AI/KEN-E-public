import axios from "axios";

// Create axios instance for public/unauthenticated API calls
const apiPublic = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor for error handling
apiPublic.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("Public API error:", error);
    return Promise.reject(error);
  },
);

export default apiPublic;
