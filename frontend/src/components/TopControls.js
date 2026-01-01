import React from 'react';
import Logo from './Logo';
import UserMenu from './UserMenu';
import BookmarkButton from './BookmarkButton';
import LibrarySidebarToggle from './LibrarySidebarToggle';
import './TopControls.css';

const TopControls = ({ layout = 'horizontal-right', onLibraryToggle, isLibraryOpen, bookmarkCount }) => {
  return (
    <>
      {/* Left side: Logo + Library button */}
      <div className={`left-controls ${isLibraryOpen ? 'shifted' : ''}`}>
        <div className="logo-container">
          <Logo size="medium" />
        </div>
        <LibrarySidebarToggle 
          isOpen={isLibraryOpen}
          onToggle={onLibraryToggle}
          bookmarkCount={bookmarkCount}
        />
      </div>
      
      {/* Right side: Bookmark on left, User Menu on right */}
      <div className={`top-controls ${layout}`}>
        <BookmarkButton />
        <UserMenu />
      </div>
    </>
  );
};

export default TopControls;