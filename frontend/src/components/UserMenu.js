import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import DjangoLoginForm from './DjangoLoginForm';
import UserMenuDropdown from './UserMenuDropdown';
import { UserIcon, ChevronDown } from './Icons';
import './UserMenu.css';

const UserMenu = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [showLoginForm, setShowLoginForm] = useState(false);
  const { palette, palettes, theme } = useTheme();
  const { user, isSignedIn, isClerkAuth } = useAuth();

  const getCurrentPaletteColor = () => {
    const currentPalette = palettes.find(p => p.id === palette);
    if (!currentPalette) return '#4299E1';
    const isDarkTheme = theme === 'dark' || theme === 'solarized-dark';
    return isDarkTheme ? currentPalette.darkColor : currentPalette.color;
  };

  return (
    <div className="user-menu">
      <button 
        className="user-menu-trigger"
        onClick={() => setIsOpen(!isOpen)}
        onBlur={() => setTimeout(() => setIsOpen(false), 150)}
        style={{
          borderLeft: `3px solid ${getCurrentPaletteColor()}`
        }}
      >
        <div className="user-avatar">
          {isSignedIn && user?.imageUrl ? (
            <img src={user.imageUrl} alt={user.firstName} className="avatar-image" />
          ) : (
            <div className="avatar-placeholder">
              {isSignedIn && user?.firstName ? user.firstName.charAt(0).toUpperCase() : <UserIcon size={16} />}
            </div>
          )}
        </div>
        <span className="user-menu-arrow"><ChevronDown size={14} /></span>
      </button>

      {isOpen && (
        <UserMenuDropdown 
          onClose={() => setIsOpen(false)}
          onShowLogin={() => setShowLoginForm(true)} 
        />
      )}
      
      {/* Django Login Form Modal */}
      {showLoginForm && !isClerkAuth && (
        <DjangoLoginForm 
          onSuccess={() => setShowLoginForm(false)}
          onCancel={() => setShowLoginForm(false)}
        />
      )}
    </div>
  );
};

export default UserMenu;