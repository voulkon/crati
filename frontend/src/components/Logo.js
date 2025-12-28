import React from 'react';
import { Link } from 'react-router-dom';
import './Logo.css';

const Logo = ({ size = 'medium' }) => {
  return (
    <Link to="/" className={`logo-link logo-${size}`}>
      <img 
        src="/android-chrome-192x192.png" 
        alt="Home" 
        className="logo-image"
      />
    </Link>
  );
};

export default Logo;
