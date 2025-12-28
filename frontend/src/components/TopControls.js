import React from 'react';
import Logo from './Logo';
import UserMenu from './UserMenu';
import './TopControls.css';

const TopControls = ({ layout = 'horizontal-right' }) => {
  return (
    <>
      <div className="logo-container">
        <Logo size="medium" />
      </div>
      <div className={`top-controls ${layout}`}>
        <UserMenu />
      </div>
    </>
  );
};

export default TopControls;