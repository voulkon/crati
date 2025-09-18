import React, { createContext, useContext } from 'react';
import { useUser, useAuth as useClerkAuth } from '@clerk/clerk-react';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const { user, isSignedIn, isLoaded } = useUser();
  const { getToken, signOut } = useClerkAuth();

  // Fixed token method
  const getAuthToken = async () => {
    try {
      if (isSignedIn && user) {
        // Use the auth hook's getToken method, not user.getToken
        return await getToken();
      }
      return null;
    } catch (error) {
      console.error('Error getting Clerk token:', error);
      return null;
    }
  };

  const value = {
    user,
    isSignedIn: isSignedIn && isLoaded,
    isLoaded,
    getToken: getAuthToken, // Use our fixed method
    signOut,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};