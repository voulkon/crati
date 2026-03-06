import React, { useState } from 'react';
import { Bell, BellOff, ChevronUp, ChevronDown, Loader2 } from 'lucide-react';
import { useNotificationContext } from '../hooks/useNotificationContext';
import { useUnreadCount } from '../hooks/useUnreadCount';
import { useSubscriptionStatus } from '../hooks/useSubscriptionStatus';
import { toggleSubscription } from '../api/notifications';
import './NotificationButton.css';

/**
 * Split notification button for TopControls.
 * Left half: bell icon that:
 *   - On subscribable pages: toggles subscription for current entity
 *   - On passive pages: opens notification sidebar
 *   - On disabled pages: shows disabled state with tooltip
 * Right half: chevron opens/closes the notification sidebar.
 */
export default function NotificationButton({ onSidebarToggle, isSidebarOpen }) {
  const { context, capabilities } = useNotificationContext();
  const { unreadCount, isLoading: countLoading } = useUnreadCount(30000); // Poll every 30s
  const { subscribed, isLoading: subLoading, refetch: refetchSubscription } = useSubscriptionStatus(context);
  
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  const isLoading = countLoading || subLoading || isActionLoading;

  // Build tooltip text based on context
  const getTooltipText = () => {
    if (context.type === 'disabled') {
      return context.reason || 'Subscriptions not available on this page';
    }

    if (context.type === 'passive') {
      return 'Open notifications';
    }

    if (isLoading) {
      return 'Loading...';
    }

    if (subscribed) {
      return `Unsubscribe from ${capabilities.suggestedName || 'notifications'}`;
    }

    return `Subscribe to ${capabilities.suggestedName || 'notifications'}`;
  };

  // Handle bell click (subscribe/unsubscribe or open sidebar)
  const handleBellClick = async () => {
    // Disabled pages - do nothing
    if (context.type === 'disabled') {
      return;
    }

    // Passive pages - open sidebar
    if (context.type === 'passive') {
      handleToggleSidebar();
      return;
    }

    // Subscribable pages - toggle subscription
    if (capabilities.canSubscribe) {
      setIsActionLoading(true);
      try {
        const subscriptionData = buildSubscriptionData(context);
        const result = await toggleSubscription(subscriptionData);
        
        // Refetch subscription status
        await refetchSubscription();
        
        // Show toast
        const action = result.action === 'created' ? 'subscribed' : 'unsubscribed';
        setToastMessage(
          action === 'subscribed' 
            ? `Subscribed to ${capabilities.suggestedName}` 
            : `Unsubscribed from ${capabilities.suggestedName}`
        );
        setShowToast(true);
        setTimeout(() => setShowToast(false), 2000);
      } catch (error) {
        console.error('Failed to toggle subscription:', error);
        setToastMessage(`Error: ${error.message}`);
        setShowToast(true);
        setTimeout(() => setShowToast(false), 3000);
      } finally {
        setIsActionLoading(false);
      }
    }
  };

  // Handle chevron click (toggle sidebar)
  const handleToggleSidebar = () => {
    onSidebarToggle?.(!isSidebarOpen);
  };

  // Build subscription data from context
  const buildSubscriptionData = (ctx) => {
    const data = {
      subscription_type: capabilities.subscriptionType
    };

    switch (ctx.type) {
      case 'organization':
        data.organization_uid = ctx.organizationUid;
        break;
      case 'entity':
        data.entity_afm = ctx.afm;
        break;
      case 'signer':
        data.person_name = ctx.signerName;
        break;
      case 'person':
        data.person_name = ctx.personName;
        break;
      case 'relationship':
        data.organization_uid = ctx.organizationUid;
        data.entity_afm = ctx.afm;
        break;
      default:
        break;
    }

    return data;
  };

  // Format unread count for display
  const formatCount = (count) => {
    if (count === 0) return null;
    if (count > 99) return '99+';
    return count;
  };

  const displayCount = formatCount(unreadCount);
  const isDisabled = context.type === 'disabled';

  return (
    <>
      <div className={`notification-split-btn ${isSidebarOpen ? 'sidebar-open' : ''}`}>
        {/* Bell half — subscribe/unsubscribe or open sidebar */}
        <button
          className={`notification-button ${subscribed ? 'subscribed' : ''} ${isLoading ? 'loading' : ''} ${isDisabled ? 'disabled' : ''}`}
          onClick={handleBellClick}
          disabled={isDisabled || isLoading}
          title={getTooltipText()}
          data-testid="bell-button"
          aria-label={`Notifications${displayCount ? `, ${displayCount} unread` : ''}`}
        >
          <span className="notification-icon" data-testid="bell-icon">
            {isLoading ? <Loader2 className="icon-spin" size={18} /> : subscribed ? <Bell size={18} /> : <BellOff size={18} />}
          </span>
          {displayCount && (
            <span className="unread-badge" data-testid="unread-badge">
              {displayCount}
            </span>
          )}
        </button>

        {/* Chevron half — open/close notification sidebar */}
        <button
          className={`notification-chevron ${isSidebarOpen ? 'active' : ''}`}
          onClick={handleToggleSidebar}
          title={isSidebarOpen ? 'Close notifications' : 'Open notifications'}
          data-testid="chevron-button"
          aria-label="Toggle notification sidebar"
          aria-expanded={isSidebarOpen}
        >
          <span className="notification-chevron-icon" data-testid="chevron-icon">
            {isSidebarOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </span>
        </button>
      </div>

      {/* Toast notification */}
      {showToast && (
        <div className="notification-toast">
          {toastMessage}
        </div>
      )}
    </>
  );
}
