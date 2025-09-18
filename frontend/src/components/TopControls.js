import React from 'react';
import UserMenu from './UserMenu';
import './TopControls.css';

const TopControls = ({ layout = 'horizontal-right' }) => {
  return (
    <div className={`top-controls ${layout}`}>
      <UserMenu />
    </div>
  );
};

export default TopControls;