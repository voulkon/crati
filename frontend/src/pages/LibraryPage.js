import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getBookmarks,
  getFolders,
  createFolder,
  updateFolder,
  deleteFolder,
  createBookmark,
  updateBookmark,
  deleteBookmark
} from '../api/bookmarks';

/**
 * Library Page - Full-featured bookmark and folder management
 * Layout: Folders (left) | Bookmarks (center) | Details (right)
 */
export default function LibraryPage() {
  const navigate = useNavigate();
  
  // State
  const [folders, setFolders] = useState([]);
  const [bookmarks, setBookmarks] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [selectedBookmark, setSelectedBookmark] = useState(null);
  const [viewMode, setViewMode] = useState('all'); // 'all', 'favorites', 'recent'
  const [isLoading, setIsLoading] = useState(true);
  
  // Modal states
  const [showFolderModal, setShowFolderModal] = useState(false);
  const [editingFolder, setEditingFolder] = useState(null);
  const [folderFormData, setFolderFormData] = useState({
    name: '',
    description: '',
    color: '#3b82f6',
    icon: '📁'
  });

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    loadBookmarks();
  }, [selectedFolder, viewMode]);

  async function loadData() {
    setIsLoading(true);
    try {
      const [foldersData, bookmarksData] = await Promise.all([
        getFolders(),
        getBookmarks()
      ]);
      setFolders(foldersData);
      setBookmarks(bookmarksData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadBookmarks() {
    try {
      const params = {};
      if (selectedFolder) {
        params.folder = selectedFolder.id;
      }
      if (viewMode === 'favorites') {
        params.favorites = 'true';
      }
      const data = await getBookmarks(params);
      
      // Sort by recent if in recent mode
      if (viewMode === 'recent') {
        data.sort((a, b) => new Date(b.last_visited || b.updated_at) - new Date(a.last_visited || a.updated_at));
      }
      
      setBookmarks(data);
    } catch (error) {
      console.error('Failed to load bookmarks:', error);
    }
  }

  function handleFolderClick(folder) {
    setSelectedFolder(folder?.id === selectedFolder?.id ? null : folder);
    setSelectedBookmark(null);
  }

  function handleBookmarkClick(bookmark) {
    setSelectedBookmark(bookmark);
  }

  function handleNavigateToBookmark(bookmark) {
    navigate(bookmark.url);
  }

  async function handleToggleFavorite(bookmark) {
    try {
      await updateBookmark(bookmark.id, { is_favorite: !bookmark.is_favorite });
      loadBookmarks();
      if (selectedBookmark?.id === bookmark.id) {
        setSelectedBookmark({ ...bookmark, is_favorite: !bookmark.is_favorite });
      }
    } catch (error) {
      console.error('Failed to toggle favorite:', error);
    }
  }

  async function handleDeleteBookmark(bookmarkId) {
    if (!window.confirm('Delete this bookmark?')) return;
    try {
      await deleteBookmark(bookmarkId);
      loadBookmarks();
      if (selectedBookmark?.id === bookmarkId) {
        setSelectedBookmark(null);
      }
    } catch (error) {
      console.error('Failed to delete bookmark:', error);
    }
  }

  async function handleSaveBookmarkNotes(bookmarkId, notes) {
    try {
      await updateBookmark(bookmarkId, { notes });
      loadBookmarks();
      if (selectedBookmark?.id === bookmarkId) {
        setSelectedBookmark({ ...selectedBookmark, notes });
      }
    } catch (error) {
      console.error('Failed to save notes:', error);
    }
  }

  function openFolderModal(folder = null) {
    setEditingFolder(folder);
    setFolderFormData(folder || {
      name: '',
      description: '',
      color: '#3b82f6',
      icon: '📁'
    });
    setShowFolderModal(true);
  }

  async function handleSaveFolder() {
    try {
      if (editingFolder) {
        await updateFolder(editingFolder.id, folderFormData);
      } else {
        await createFolder(folderFormData);
      }
      setShowFolderModal(false);
      loadData();
    } catch (error) {
      console.error('Failed to save folder:', error);
      alert('Failed to save folder: ' + error.message);
    }
  }

  async function handleDeleteFolder(folderId) {
    if (!window.confirm('Delete this folder? Bookmarks will be moved to root.')) return;
    try {
      await deleteFolder(folderId);
      if (selectedFolder?.id === folderId) {
        setSelectedFolder(null);
      }
      loadData();
    } catch (error) {
      console.error('Failed to delete folder:', error);
    }
  }

  if (isLoading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: 'var(--text-secondary)' }}>
          Loading your library...
        </div>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      height: 'calc(100vh - 60px)',
      backgroundColor: 'var(--bg-color)',
      color: 'var(--text-color)'
    }}>
      {/* LEFT: Folders Sidebar */}
      <div style={{
        width: '280px',
        borderRight: '1px solid var(--border-color, #e5e7eb)',
        padding: '20px',
        overflowY: 'auto'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px'
        }}>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>Folders</h2>
          <button
            onClick={() => openFolderModal()}
            style={{
              padding: '6px 12px',
              backgroundColor: 'var(--accent-color, #3b82f6)',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            + New
          </button>
        </div>

        {/* View Mode Filter */}
        <div style={{ marginBottom: '16px' }}>
          {['all', 'favorites', 'recent'].map(mode => (
            <button
              key={mode}
              onClick={() => {
                setViewMode(mode);
                setSelectedFolder(null);
              }}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 12px',
                marginBottom: '4px',
                backgroundColor: viewMode === mode ? 'var(--accent-color, #3b82f6)' : 'transparent',
                color: viewMode === mode ? 'white' : 'var(--text-color)',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: '14px'
              }}
            >
              {mode === 'all' && '📚 All Bookmarks'}
              {mode === 'favorites' && '⭐ Favorites'}
              {mode === 'recent' && '🕒 Recent'}
            </button>
          ))}
        </div>

        <div style={{
          height: '1px',
          backgroundColor: 'var(--border-color, #e5e7eb)',
          margin: '16px 0'
        }} />

        {/* Folder List */}
        {folders.map(folder => (
          <div
            key={folder.id}
            style={{
              padding: '10px 12px',
              marginBottom: '4px',
              backgroundColor: selectedFolder?.id === folder.id ? 'var(--bg-secondary, #f3f4f6)' : 'transparent',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '8px'
            }}
            onClick={() => handleFolderClick(folder)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: '18px' }}>{folder.icon || '📁'}</span>
              <span style={{
                fontSize: '14px',
                fontWeight: '500',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {folder.name}
              </span>
              <span style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                marginLeft: 'auto'
              }}>
                {folder.bookmark_count}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  openFolderModal(folder);
                }}
                style={{
                  padding: '4px 8px',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
                title="Edit folder"
              >
                ✏️
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteFolder(folder.id);
                }}
                style={{
                  padding: '4px 8px',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
                title="Delete folder"
              >
                🗑️
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* CENTER: Bookmarks List */}
      <div style={{
        flex: 1,
        padding: '20px',
        overflowY: 'auto'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px'
        }}>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>
            {selectedFolder ? `${selectedFolder.name}` : viewMode === 'all' ? 'All Bookmarks' : viewMode === 'favorites' ? 'Favorites' : 'Recent'}
          </h2>
          <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
            {bookmarks.length} bookmark{bookmarks.length !== 1 ? 's' : ''}
          </span>
        </div>

        {bookmarks.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '60px 20px',
            color: 'var(--text-secondary)'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📑</div>
            <div style={{ fontSize: '16px', marginBottom: '8px' }}>No bookmarks yet</div>
            <div style={{ fontSize: '14px' }}>
              Use the ☆ button on any page to create your first bookmark
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: '12px' }}>
            {bookmarks.map(bookmark => (
              <div
                key={bookmark.id}
                onClick={() => handleBookmarkClick(bookmark)}
                style={{
                  padding: '16px',
                  backgroundColor: selectedBookmark?.id === bookmark.id ? 'var(--bg-secondary, #f3f4f6)' : 'var(--bg-card, white)',
                  border: '1px solid var(--border-color, #e5e7eb)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  if (selectedBookmark?.id !== bookmark.id) {
                    e.currentTarget.style.borderColor = 'var(--accent-color, #3b82f6)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedBookmark?.id !== bookmark.id) {
                    e.currentTarget.style.borderColor = 'var(--border-color, #e5e7eb)';
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleToggleFavorite(bookmark);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '20px',
                      cursor: 'pointer',
                      padding: '0'
                    }}
                  >
                    {bookmark.is_favorite ? '⭐' : '☆'}
                  </button>
                  
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: '16px',
                      fontWeight: '600',
                      marginBottom: '4px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {bookmark.title}
                    </div>
                    
                    <div style={{
                      fontSize: '13px',
                      color: 'var(--text-secondary)',
                      marginBottom: '8px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {bookmark.url}
                    </div>
                    
                    {bookmark.notes && (
                      <div style={{
                        fontSize: '14px',
                        color: 'var(--text-secondary)',
                        marginTop: '8px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical'
                      }}>
                        {bookmark.notes}
                      </div>
                    )}
                    
                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      marginTop: '8px',
                      fontSize: '12px',
                      color: 'var(--text-secondary)'
                    }}>
                      {bookmark.folder_name && (
                        <span>📁 {bookmark.folder_name}</span>
                      )}
                      {bookmark.visit_count > 0 && (
                        <span>👁️ {bookmark.visit_count}</span>
                      )}
                      {bookmark.last_visited && (
                        <span>
                          Last: {new Date(bookmark.last_visited).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleNavigateToBookmark(bookmark);
                    }}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: 'var(--accent-color, #3b82f6)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    Open →
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* RIGHT: Bookmark Details Editor */}
      {selectedBookmark && (
        <BookmarkEditor
          bookmark={selectedBookmark}
          folders={folders}
          onSave={async (updates) => {
            await updateBookmark(selectedBookmark.id, updates);
            loadBookmarks();
            setSelectedBookmark({ ...selectedBookmark, ...updates });
          }}
          onDelete={() => handleDeleteBookmark(selectedBookmark.id)}
          onClose={() => setSelectedBookmark(null)}
        />
      )}

      {/* Folder Modal */}
      {showFolderModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card, white)',
            borderRadius: '12px',
            padding: '24px',
            width: '90%',
            maxWidth: '500px',
            maxHeight: '80vh',
            overflow: 'auto'
          }}>
            <h3 style={{ marginTop: 0, marginBottom: '20px' }}>
              {editingFolder ? 'Edit Folder' : 'New Folder'}
            </h3>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
                Name *
              </label>
              <input
                type="text"
                value={folderFormData.name}
                onChange={(e) => setFolderFormData({ ...folderFormData, name: e.target.value })}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color, #e5e7eb)',
                  fontSize: '14px',
                  backgroundColor: 'var(--bg-color)',
                  color: 'var(--text-color)'
                }}
                placeholder="Work Research"
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
                Description
              </label>
              <textarea
                value={folderFormData.description}
                onChange={(e) => setFolderFormData({ ...folderFormData, description: e.target.value })}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color, #e5e7eb)',
                  fontSize: '14px',
                  backgroundColor: 'var(--bg-color)',
                  color: 'var(--text-color)',
                  minHeight: '80px',
                  resize: 'vertical'
                }}
                placeholder="Optional description..."
              />
            </div>

            <div style={{ marginBottom: '16px', display: 'flex', gap: '16px' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
                  Icon
                </label>
                <input
                  type="text"
                  value={folderFormData.icon}
                  onChange={(e) => setFolderFormData({ ...folderFormData, icon: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-color, #e5e7eb)',
                    fontSize: '14px',
                    backgroundColor: 'var(--bg-color)',
                    color: 'var(--text-color)'
                  }}
                  placeholder="📁 or emoji"
                />
              </div>

              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
                  Color
                </label>
                <input
                  type="color"
                  value={folderFormData.color}
                  onChange={(e) => setFolderFormData({ ...folderFormData, color: e.target.value })}
                  style={{
                    width: '100%',
                    height: '42px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-color, #e5e7eb)',
                    cursor: 'pointer'
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '24px' }}>
              <button
                onClick={() => setShowFolderModal(false)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: 'transparent',
                  border: '1px solid var(--border-color, #e5e7eb)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  color: 'var(--text-color)'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveFolder}
                disabled={!folderFormData.name.trim()}
                style={{
                  padding: '10px 20px',
                  backgroundColor: 'var(--accent-color, #3b82f6)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: folderFormData.name.trim() ? 'pointer' : 'not-allowed',
                  fontSize: '14px',
                  opacity: folderFormData.name.trim() ? 1 : 0.5
                }}
              >
                {editingFolder ? 'Save' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Bookmark Editor Panel - Shows on the right when a bookmark is selected
 */
function BookmarkEditor({ bookmark, folders, onSave, onDelete, onClose }) {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    title: bookmark.title,
    notes: bookmark.notes,
    folder_id: bookmark.folder_id,
    is_favorite: bookmark.is_favorite
  });

  async function handleSave() {
    await onSave(formData);
    setIsEditing(false);
  }

  return (
    <div style={{
      width: '400px',
      borderLeft: '1px solid var(--border-color, #e5e7eb)',
      padding: '20px',
      overflowY: 'auto',
      backgroundColor: 'var(--bg-card, white)'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px'
      }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>Details</h3>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '20px',
            cursor: 'pointer',
            padding: '0'
          }}
        >
          ✕
        </button>
      </div>

      {isEditing ? (
        <>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
              Title
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                border: '1px solid var(--border-color, #e5e7eb)',
                fontSize: '14px',
                backgroundColor: 'var(--bg-color)',
                color: 'var(--text-color)'
              }}
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
              Folder
            </label>
            <select
              value={formData.folder_id || ''}
              onChange={(e) => setFormData({ ...formData, folder_id: e.target.value || null })}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                border: '1px solid var(--border-color, #e5e7eb)',
                fontSize: '14px',
                backgroundColor: 'var(--bg-color)',
                color: 'var(--text-color)'
              }}
            >
              <option value="">No folder</option>
              {folders.map(f => (
                <option key={f.id} value={f.id}>{f.icon} {f.name}</option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
              Notes
            </label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                border: '1px solid var(--border-color, #e5e7eb)',
                fontSize: '14px',
                backgroundColor: 'var(--bg-color)',
                color: 'var(--text-color)',
                minHeight: '200px',
                resize: 'vertical'
              }}
              placeholder="Add your research notes here..."
            />
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => setIsEditing(false)}
              style={{
                flex: 1,
                padding: '10px',
                backgroundColor: 'transparent',
                border: '1px solid var(--border-color, #e5e7eb)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              style={{
                flex: 1,
                padding: '10px',
                backgroundColor: 'var(--accent-color, #3b82f6)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Save
            </button>
          </div>
        </>
      ) : (
        <>
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>
              {bookmark.title}
            </h4>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', wordBreak: 'break-all' }}>
              {bookmark.url}
            </div>
          </div>

          {bookmark.folder_name && (
            <div style={{ marginBottom: '16px', fontSize: '14px' }}>
              <span style={{ fontWeight: '500' }}>Folder:</span> {bookmark.folder_name}
            </div>
          )}

          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '14px', fontWeight: '500', marginBottom: '8px' }}>
              Notes
            </div>
            <div style={{
              padding: '12px',
              backgroundColor: 'var(--bg-secondary, #f3f4f6)',
              borderRadius: '6px',
              fontSize: '14px',
              whiteSpace: 'pre-wrap',
              minHeight: '100px'
            }}>
              {bookmark.notes || <span style={{ color: 'var(--text-secondary)' }}>No notes yet</span>}
            </div>
          </div>

          <div style={{
            padding: '12px',
            backgroundColor: 'var(--bg-secondary, #f3f4f6)',
            borderRadius: '6px',
            fontSize: '13px',
            marginBottom: '16px'
          }}>
            <div>Views: {bookmark.visit_count}</div>
            <div>Created: {new Date(bookmark.created_at).toLocaleString()}</div>
            {bookmark.last_visited && (
              <div>Last visited: {new Date(bookmark.last_visited).toLocaleString()}</div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => setIsEditing(true)}
              style={{
                flex: 1,
                padding: '10px',
                backgroundColor: 'var(--accent-color, #3b82f6)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Edit
            </button>
            <button
              onClick={onDelete}
              style={{
                padding: '10px 16px',
                backgroundColor: '#ef4444',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              🗑️
            </button>
          </div>
        </>
      )}
    </div>
  );
}
