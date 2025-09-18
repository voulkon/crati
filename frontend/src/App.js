import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import HomePage from "./pages/HomePage";
import DevPage from "./pages/OrganizationsPage";
import EntityDetailPage from "./pages/EntityDetailPage";
import DecisionDetailPage from "./pages/DecisionDetailPage";
import AFMEntityDetailPage from "./pages/AFMEntityDetailPage";
import SearchResults from "./pages/SearchResults";
import SuperSearchExample from "./pages/SuperSearchExample";
import Clock from "./components/Clock";
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthProvider } from './contexts/AuthContext';
import { TranslationProvider } from './contexts/TranslationContext';
import TopControls from './components/TopControls';
import './index.css';
import RateLimitIndicator from './components/RateLimitIndicator';
import RateLimitModal from './components/RateLimitModal';

function App() {
  // Easy way to switch layouts - just change this value!
  const controlsLayout = 'vertical-right'; // Options: 'horizontal-right', 'vertical-right', 'split-corners', 'horizontal-left'

  return (
    <TranslationProvider>
      <ThemeProvider>
        <AuthProvider>
          <Router>
            <div className="App" style={{ 
              backgroundColor: 'var(--bg-color)', 
              color: 'var(--text-color)', 
              minHeight: '100vh',
              transition: 'background-color 0.3s ease, color 0.3s ease'
            }}>
              {/* Flexible top controls */}
              <TopControls layout={controlsLayout} />
              
              <RateLimitIndicator />
              <RateLimitModal />
              
              <Routes>
                {/* NEW: Use HomePage as the main landing page */}
                <Route path="/" element={<HomePage />} />
                
                {/* RENAMED: Change from /dev to /organizations */}
                <Route path="/organizations" element={<DevPage />} />
                <Route path="/dev" element={<Navigate to="/organizations" />} />
                
                {/* Search Results Page */}
                <Route path="/search" element={<SearchResults />} />
                
                {/* Super Search Example Page */}
                <Route path="/search-example" element={<SuperSearchExample />} />
                
                <Route path="/entity/:entityType/:entityId" element={<EntityDetailPage />} />
                <Route path="/health" element={<Clock />} />
                <Route path="/entity/afm/:afm" element={<AFMEntityDetailPage />} />
                
                {/* Temporal exploration routes */}
                <Route path="/explore/temporal/:date" element={<EntityDetailPage />} />
                <Route path="/explore/temporal/:startDate/:endDate" element={<EntityDetailPage />} />
                <Route path="/explore/month/:year/:month" element={<EntityDetailPage />} />
                <Route path="/explore/week/:year/:week" element={<EntityDetailPage />} />
                <Route path="/decision/:id" element={<DecisionDetailPage />} />
              </Routes>
            </div>
          </Router>
        </AuthProvider>
      </ThemeProvider>
    </TranslationProvider>
  );
}

export default App;