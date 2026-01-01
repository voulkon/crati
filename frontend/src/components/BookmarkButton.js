import React, { useState, useEffect } from 'react';
import { toggleBookmarkForCurrentPage, isCurrentPageBookmarked } from '../api/bookmarks';
import { useTranslation } from '../contexts/TranslationContext';
import './BookmarkButton.css';

/**
 * Compact bookmark button for TopControls
 * Shows bookmark status and allows quick bookmark/unbookmark
 */
export default function BookmarkButton() {
  const { t } = useTranslation();
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  useEffect(() => {
    checkBookmarkStatus();
  }, [window.location.pathname, window.location.search]);

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

      {/* Toast notification */}
      {showToast && (
        <div className="bookmark-toast">
          {toastMessage}
        </div>
      )}
    </>
  );
}
