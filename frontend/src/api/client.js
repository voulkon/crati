import axios from 'axios';

// Create a global token getter that will be set by the app
let getClerkToken = null;

export const setTokenGetter = (getter) => {
  getClerkToken = getter;
};

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add interceptors for auth, etc.
apiClient.interceptors.request.use(async config => {
  // Get Clerk token if available
  if (getClerkToken) {
    try {
      const token = await getClerkToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('Error getting Clerk token:', error);
    }
  }
  return config;
},
  (error) => Promise.reject(error)
);

// Add response interceptor to handle rate limiting
apiClient.interceptors.response.use(
  (response) => {
    // Store rate limit info for display
    if (response.headers['x-ratelimit-limit']) {
      const rateLimitInfo = {
        limit: parseInt(response.headers['x-ratelimit-limit']),
        remaining: parseInt(response.headers['x-ratelimit-remaining']),
        reset: parseInt(response.headers['x-ratelimit-reset'])
      };
      
      // Store in localStorage or context for UI display
      localStorage.setItem('rateLimitInfo', JSON.stringify(rateLimitInfo));
      
      // Dispatch event for components to listen to
      window.dispatchEvent(new CustomEvent('rateLimitUpdate', { detail: rateLimitInfo }));
    }
    
    return response;
  },
  (error) => {
    if (error.response?.status === 429) {
      // Rate limit exceeded
      const resetTime = error.response.headers['x-ratelimit-reset'];
      const resetDate = new Date(resetTime * 1000);
      
      // Create enhanced error with rate limit info
      const rateLimitError = new Error('Rate limit exceeded');
      rateLimitError.isRateLimit = true;
      rateLimitError.resetTime = resetDate;
      rateLimitError.message = error.response.data.error || error.response.data || 'Rate limit exceeded';
      
      // Dispatch event for global handling
      window.dispatchEvent(new CustomEvent('rateLimitExceeded', { 
        detail: { 
          resetTime: resetDate,
          message: rateLimitError.message
        }
      }));
      
      return Promise.reject(rateLimitError);
    }
    
    if (error.response?.status === 401) {
      // Unauthorized - user needs to sign in
      // Dispatch event for global handling
      window.dispatchEvent(new CustomEvent('authRequired', { 
        detail: { 
          message: 'Please sign in to access this feature'
        }
      }));
      
      return Promise.reject(error);
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;