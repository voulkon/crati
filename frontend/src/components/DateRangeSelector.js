import React, { useState, useEffect } from 'react';
import { useDateRange } from '../contexts/DateRangeContext';
import { useTranslation } from '../contexts/TranslationContext';
import './DateRangeSelector.css';

const DateRangeSelector = ({ className = '' }) => {
  const { t } = useTranslation();
  const { period, setPeriod, dateRange, setCustomRange } = useDateRange();
  const [isEditing, setIsEditing] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Format date to DD/M/YYYY
  const formatDateDDM = (dateString) => {
    const date = new Date(dateString);
    const day = date.getDate();
    const month = date.getMonth() + 1;
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  };

  // Convert DD/M/YYYY to YYYY-MM-DD
  const parseUserDate = (userInput) => {
    const parts = userInput.split('/');
    if (parts.length === 3) {
      const day = parts[0].padStart(2, '0');
      const month = parts[1].padStart(2, '0');
      const year = parts[2];
      return `${year}-${month}-${day}`;
    }
    return userInput;
  };

  // Update local state when dateRange changes
  useEffect(() => {
    if (dateRange) {
      setStartDate(dateRange.start_date);
      setEndDate(dateRange.end_date);
    }
  }, [dateRange]);

  const handleDateChange = (type, value) => {
    if (type === 'start') {
      setStartDate(value);
    } else {
      setEndDate(value);
    }
  };

  const applyCustomRange = () => {
    if (startDate && endDate) {
      setCustomRange({
        start_date: startDate,
        end_date: endDate
      });
      setPeriod('custom');
      setIsEditing(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      applyCustomRange();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      if (dateRange) {
        setStartDate(dateRange.start_date);
        setEndDate(dateRange.end_date);
      }
    }
  };

  const periods = [
    { value: 'today', label: t('dateRange.today') || 'Today' },
    { value: 'week', label: t('dateRange.week') || 'Week' },
    { value: 'month', label: t('dateRange.month') || 'Month' },
    { value: 'year', label: t('dateRange.year') || 'Year' },
    { value: 'custom', label: t('dateRange.custom') || 'Custom' }
  ];

  return (
    <div className={`date-range-selector ${className}`}>
      <div className="period-buttons">
        {periods.map(({ value, label }) => (
          <button
            key={value}
            className={`period-button ${period === value ? 'active' : ''}`}
            onClick={() => {
              setPeriod(value);
              if (value === 'custom') {
                setIsEditing(true);
              }
            }}
          >
            {label}
          </button>
        ))}
      </div>
      {dateRange && (
        <div className={`date-range-display ${period === 'custom' ? 'custom-range' : ''}`}>
          {isEditing || period === 'custom' ? (
            <div className="date-inputs">
              <input
                type="text"
                value={formatDateDDM(startDate)}
                onChange={(e) => {
                  const isoDate = parseUserDate(e.target.value);
                  handleDateChange('start', isoDate);
                }}
                onKeyDown={handleKeyPress}
                className="date-input"
                placeholder="DD/M/YYYY"
              />
              <span className="date-separator">-</span>
              <input
                type="text"
                value={formatDateDDM(endDate)}
                onChange={(e) => {
                  const isoDate = parseUserDate(e.target.value);
                  handleDateChange('end', isoDate);
                }}
                onKeyDown={handleKeyPress}
                className="date-input"
                placeholder="DD/M/YYYY"
              />
              <button 
                onClick={applyCustomRange}
                className="apply-button"
                title={t('dateRange.apply') || 'Apply'}
              >
                ✓
              </button>
              {period === 'custom' && (
                <button 
                  onClick={() => setIsEditing(false)}
                  className="cancel-button"
                  title={t('dateRange.cancel') || 'Cancel'}
                >
                  ✕
                </button>
              )}
            </div>
          ) : (
            <div className="date-display" onClick={() => setIsEditing(true)}>
              {formatDateDDM(dateRange.start_date)} - {formatDateDDM(dateRange.end_date)}
              <span className="edit-hint" title={t('dateRange.clickToEdit') || 'Click to edit'}>✎</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DateRangeSelector;
