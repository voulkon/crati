import React from 'react';
import Logo from './Logo';
import UserMenu from './UserMenu';
import BookmarkButton from './BookmarkButton';
import NotificationButton from './NotificationButton';
import './TopControls.css';

const TopControls = ({ 
  layout = 'horizontal-right', 
  onLibraryToggle, 
  isLibraryOpen, 
  bookmarkCount,
  onNotificationSidebarToggle,
  isNotificationSidebarOpen 
}) => {
  return (
    <>
      {/* Left side: Logo (shifts right when sidebar is open) */}
      <div className={`left-controls ${isLibraryOpen ? 'shifted' : ''}`}>
        <div className="logo-container">
          <Logo size="medium" />
        </div>
      </div>
      
      {/* Right side: Notification button, Bookmark button, then User Menu */}
      <div className={`top-controls ${layout}`}>
        <NotificationButton
          onSidebarToggle={onNotificationSidebarToggle}
          isSidebarOpen={isNotificationSidebarOpen}
        />
        <BookmarkButton
          onLibraryToggle={onLibraryToggle}
          isLibraryOpen={isLibraryOpen}
          bookmarkCount={bookmarkCount}
        />
        <UserMenu />
      </div>
    </>
  );
};

export default TopControls;