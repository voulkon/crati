import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';

/**
 * Hook to check if the authenticated user is in the allowlist
 * 
 * Makes a simple API call to check access. The backend middleware
 * will return 403 if the user is not allowed.
 */
export function useAllowlistCheck() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [isAllowed, setIsAllowed] = useState(null); // null = checking, true = allowed, false = denied
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    async function checkAccess() {
      // Only check if auth is loaded and user is signed in
      if (!isLoaded || !isSignedIn) {
        setIsChecking(false);
        return;
      }

      try {
        const token = await getToken();
        const apiUrl = process.env.REACT_APP_API_URL || '/api';
        
        // Make a lightweight API call to check access
        const response = await fetch(`${apiUrl}/health/`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (response.status === 403) {
          // User is authenticated but not in allowlist
          setIsAllowed(false);
        } else if (response.ok) {
          // User is allowed
          setIsAllowed(true);
        } else if (response.status === 401) {
          // Authentication failed - shouldn't happen but handle it
          setIsAllowed(null);
        } else {
          // Other error - assume allowed to not break the app
          setIsAllowed(true);
        }
      } catch (error) {
        console.error('Error checking allowlist:', error);
        // On error, assume allowed to not break the app
        setIsAllowed(true);
      } finally {
        setIsChecking(false);
      }
    }

    checkAccess();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn, getToken]);

  return { isAllowed, isChecking };
}
