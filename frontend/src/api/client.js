import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add interceptors for auth, etc.
apiClient.interceptors.request.use(config => {
  // Add auth token if available
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
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
    
    return Promise.reject(error);
  }
);

export default apiClient;