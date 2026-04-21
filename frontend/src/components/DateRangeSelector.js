import React from 'react';
import { useDateRange } from '../contexts/DateRangeContext';
import { useTranslation } from '../contexts/TranslationContext';
import './DateRangeSelector.css';

const DateRangeSelector = ({ className = '' }) => {
  const { t } = useTranslation();
  const { period, setPeriod, dateRange } = useDateRange();

  const periods = [
    { value: 'today', label: t('dateRange.today') || 'Today' },
    { value: 'week', label: t('dateRange.week') || 'Week' },
    { value: 'month', label: t('dateRange.month') || 'Month' },
    { value: 'year', label: t('dateRange.year') || 'Year' }
  ];

  return (
    <div className={`date-range-selector ${className}`}>
      <div className="period-buttons">
        {periods.map(({ value, label }) => (
          <button
            key={value}
            className={`period-button ${period === value ? 'active' : ''}`}
            onClick={() => setPeriod(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {dateRange && (
        <div className="date-range-display">
          {new Date(dateRange.start_date).toLocaleDateString()} - {new Date(dateRange.end_date).toLocaleDateString()}
        </div>
      )}
    </div>
  );
};

export default DateRangeSelector;
