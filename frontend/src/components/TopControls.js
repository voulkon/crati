import React from 'react';
import Logo from './Logo';
import UserMenu from './UserMenu';
import BookmarkButton from './BookmarkButton';
import './TopControls.css';

const TopControls = ({ layout = 'horizontal-right', onLibraryToggle, isLibraryOpen, bookmarkCount }) => {
  return (
    <>
      {/* Left side: Logo (shifts right when sidebar is open) */}
      <div className={`left-controls ${isLibraryOpen ? 'shifted' : ''}`}>
        <div className="logo-container">
          <Logo size="medium" />
        </div>
      </div>
      
      {/* Right side: Split bookmark+chevron button, then User Menu */}
      <div className={`top-controls ${layout}`}>
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