import React from 'react';
import Logo from './Logo';
import UserMenu from './UserMenu';
import BookmarkButton from './BookmarkButton';
import NotificationButton from './NotificationButton';
import './TopControls.css';

/**
 * TopControls - Main navigation bar with logo and action buttons
 * 
 * @param {string} layout - Layout mode for the controls:
 *   - 'horizontal-right': Horizontal layout, aligned to the right (default)
 *   - 'vertical-right': Vertical layout from top to bottom, aligned to the right
 *   - 'horizontal-left': Horizontal layout, aligned to the left
 *   - 'vertical-left': Vertical layout from top to bottom, aligned to the left
 *   - 'split-corners': Split layout with logo on left, controls on right
 */
const TopControls = ({ 
  layout = 'horizontal-right', 
  onLibraryToggle, 
  isLibraryOpen, 
  bookmarkCount,
  onNotificationSidebarToggle,
  isNotificationSidebarOpen,
  onUserMenuToggle,
  isUserMenuOpen
}) => {
  return (
    <>
      {/* Left side: Logo (shifts right when sidebar is open) */}
      <div className={`left-controls ${isLibraryOpen ? 'shifted' : ''}`}>
        <div className="logo-container">
          <Logo size="medium" />
        </div>
      </div>
      
      {/* Right side: User Menu, Bookmark button, then Notification button */}
      <div className={`top-controls ${layout}`}>
        <UserMenu 
          isOpen={isUserMenuOpen}
          onToggle={onUserMenuToggle}
        />
        <BookmarkButton
          onLibraryToggle={onLibraryToggle}
          isLibraryOpen={isLibraryOpen}
          bookmarkCount={bookmarkCount}
        />
        <NotificationButton
          onSidebarToggle={onNotificationSidebarToggle}
          isSidebarOpen={isNotificationSidebarOpen}
        />
      </div>
    </>
  );
};

export default TopControls;