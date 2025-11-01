// API Configuration for different environments
export const API_CONFIG = {
  // Automatically detect environment
  getBaseUrl: () => {
    // Priority 1: Use environment variable if set (Vercel production)
    if (import.meta.env.VITE_API_URL) {
      return import.meta.env.VITE_API_URL;
    }

    // Priority 2: Production on Vercel (*.vercel.app)
    if (window.location.hostname.includes('vercel.app')) {
      // Replace with your Railway backend URL after deployment
      return 'https://hrms1-latest-production.up.railway.app'; // Update this with your actual Railway URL
    }

    // Priority 3: Legacy production server
    if (window.location.hostname === "15.207.246.171") {
      return `http://${window.location.hostname}`;
    }

    // Priority 4: Development (localhost)
    if (
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1"
    ) {
      return "http://127.0.0.1:8000";
    }

    // Fallback: Use current domain
    return `${window.location.protocol}//${window.location.hostname}`;
  },

  // Get the full API URL
  getApiUrl: (endpoint: string = "") => {
    const baseUrl = API_CONFIG.getBaseUrl();
    return `${baseUrl}/api${endpoint}`;
  },
};

// Export the base URL for backward compatibility
export const API_BASE_URL = API_CONFIG.getBaseUrl();
export const API_BASE = API_CONFIG.getApiUrl();
