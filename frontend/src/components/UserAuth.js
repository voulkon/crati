import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import './UserAuth.css';

// Check if Clerk is available
const isClerkAvailable = () => {
  return !!process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;
};

// Lazy load Clerk components only if available
let SignInButton, SignUpButton, UserButton;
if (isClerkAvailable()) {
  const clerkReact = require('@clerk/clerk-react');
  SignInButton = clerkReact.SignInButton;
  SignUpButton = clerkReact.SignUpButton;
  UserButton = clerkReact.UserButton;
}

const UserAuth = () => {
  const { getCurrentPaletteColor } = useTheme();
  const { user, isLoading, isSignedIn, isClerkAuth } = useAuth();

  // Don't render auth UI if Clerk is not available
  if (!isClerkAuth) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="user-auth">
        <div className="auth-loading">
          <div className="loading-spinner"></div>
        </div>
      </div>
    );
  }

  // Not signed in
  if (!isSignedIn || !user) {
    return (
      <div className="user-auth">
        <SignInButton mode="modal">
          <button 
            className="sign-in-button"
            style={{ borderLeft: `3px solid ${getCurrentPaletteColor()}` }}
          >
            <span className="auth-icon">👤</span>
            <span className="auth-text">Sign In</span>
          </button>
        </SignInButton>
      </div>
    );
  }

  // Signed in - use Clerk's UserButton for a complete user menu
  return (
    <div className="user-auth">
      <UserButton 
        appearance={{
          elements: {
            avatarBox: {
              width: '40px',
              height: '40px',
              borderLeft: `3px solid ${getCurrentPaletteColor()}`
            }
          }
        }}
      />
    </div>
  );
};

export default UserAuth;