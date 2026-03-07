/**
 * Notification system configuration
 * Centralized configuration values for the notification system
 */

export const NOTIFICATION_CONFIG = {
  /**
   * Polling interval for unread count updates (in milliseconds)
   * Default: 4 minutes (240000ms)
   */
  UNREAD_COUNT_POLL_INTERVAL: 240000,

  /**
   * Default number of notifications to fetch per page
   */
  DEFAULT_PAGE_SIZE: 20,

  /**
   * Maximum number of notifications to show in the sidebar
   */
  MAX_SIDEBAR_NOTIFICATIONS: 50,
};

export default NOTIFICATION_CONFIG;
