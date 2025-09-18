import React from "react";
import ReactDOM from "react-dom/client";
import { ClerkProvider } from '@clerk/clerk-react';
import App from "./App";

const clerkPubKey = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;

if (!clerkPubKey) {
  console.error('Environment variables:', {
    NODE_ENV: process.env.NODE_ENV,
    REACT_APP_CLERK_PUBLISHABLE_KEY: process.env.REACT_APP_CLERK_PUBLISHABLE_KEY ? 'SET' : 'NOT SET'
  });
  throw new Error("Missing REACT_APP_CLERK_PUBLISHABLE_KEY - check your .env file");
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <ClerkProvider publishableKey={clerkPubKey}>
    <App />
  </ClerkProvider>
);