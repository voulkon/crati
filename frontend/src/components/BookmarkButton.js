import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { toggleBookmarkForCurrentPage, isCurrentPageBookmarked } from '../api/bookmarks';
import { useTranslation } from '../contexts/TranslationContext';
import { ChevronUp, ChevronDown } from './Icons';
import './BookmarkButton.css';

/**
 * Split bookmark button for TopControls.
 * Left half: star toggles the bookmark for the current page.
 * Right half: chevron opens/closes the Library sidebar.
 */
export default function BookmarkButton({ onLibraryToggle, isLibraryOpen, bookmarkCount }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  useEffect(() => {
    checkBookmarkStatus();
  }, [location.pathname, location.search]);

  async function checkBookmarkStatus() {
    try {
      const bookmark = await isCurrentPageBookmarked();
      setIsBookmarked(!!bookmark);
    } catch (error) {
      console.error('Failed to check bookmark status:', error);
    }
  }

  async function handleToggleBookmark() {
    setIsLoading(true);
    try {
      const result = await toggleBookmarkForCurrentPage();
      setIsBookmarked(result.action === 'added');
      
      // Show toast notification
      setToastMessage(result.action === 'added' ? t('library.bookmarked') : t('library.bookmarkRemoved'));
      setShowToast(true);
      setTimeout(() => setShowToast(false), 2000);
    } catch (error) {
      console.error('Failed to toggle bookmark:', error);
      setToastMessage(t('library.errorPrefix') + error.message);
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <div className={`bookmark-split-btn ${isLibraryOpen ? 'library-open' : ''}`}>
        {/* Star half — bookmark current page */}
        <button
          className={`bookmark-button ${isBookmarked ? 'bookmarked' : ''} ${isLoading ? 'loading' : ''}`}
          onClick={handleToggleBookmark}
          disabled={isLoading}
          title={isBookmarked ? t('library.removeBookmark') : t('library.bookmarkThisPage')}
        >
          <span className="bookmark-icon">
            {isLoading ? '⋯' : isBookmarked ? '★' : '☆'}
          </span>
        </button>

        {/* Chevron half — open/close Library sidebar */}
        <button
          className={`bookmark-chevron ${isLibraryOpen ? 'active' : ''}`}
          onClick={onLibraryToggle}
          title={isLibraryOpen ? t('library.close') : t('library.myLibrary')}
        >
          <span className="bookmark-chevron-icon">
            {isLibraryOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </span>
        </button>
      </div>

      {/* Toast notification */}
      {showToast && (
        <div className="bookmark-toast">
          {toastMessage}
        </div>
      )}
    </>
  );
}
