import { useState, useEffect } from 'react';
import { getUnreadCount } from '../api/notifications';
import { NOTIFICATION_CONFIG } from '../config/notifications';

/**
 * Hook to fetch and maintain unread notification count
 * @param {number} [pollInterval] - Interval in milliseconds to poll for updates (default: from config)
 * @returns {{ unreadCount: number, isLoading: boolean, refetch: Function, error: Error|null }}
 */
export function useUnreadCount(pollInterval = NOTIFICATION_CONFIG.UNREAD_COUNT_POLL_INTERVAL) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchUnreadCount = async () => {
    try {
      const response = await getUnreadCount();
      setUnreadCount(response.unread_count || 0);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch unread count:', err);
      setError(err);
      // Don't show count if there's an error
      setUnreadCount(0);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchUnreadCount();

    // Set up polling if interval is provided
    if (pollInterval > 0) {
      const intervalId = setInterval(fetchUnreadCount, pollInterval);
      return () => clearInterval(intervalId);
    }
  }, [pollInterval]);

  return {
    unreadCount,
    isLoading,
    refetch: fetchUnreadCount,
    error
  };
}

export default useUnreadCount;
