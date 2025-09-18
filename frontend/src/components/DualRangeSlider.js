import React, { useState, useRef, useCallback, useEffect } from 'react';
import SliderTooltip from './SliderTooltip';
import ActivityChart from './ActivityChart';
import ActivitySummary from './ActivitySummary';
import { useSliderFormatters } from '../hooks/useSliderFormatters';
import './DualRangeSlider.css';

const DualRangeSlider = ({ 
  min, 
  max, 
  startValue, 
  endValue, 
  onChange, 
  label, 
  formatValue,
  activityData = null
}) => {
  const [isDragging, setIsDragging] = useState(null);
  const [hoverValue, setHoverValue] = useState(null);
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 });
  const [showActivityTooltip, setShowActivityTooltip] = useState(false);
  const [activityHoverData, setActivityHoverData] = useState(null);
  const sliderRef = useRef(null);
  const { formatAmount, formatPeriod } = useSliderFormatters();

  const getValueFromPosition = useCallback((clientX) => {
    if (!sliderRef.current) return min;
    
    const rect = sliderRef.current.getBoundingClientRect();
    const percentage = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return Math.round(min + percentage * (max - min));
  }, [min, max]);

  const handleMouseDown = useCallback((type) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(type);
  }, []);
  const handleMouseMove = useCallback((e) => {
    if (!sliderRef.current) return;
    
    const rect = sliderRef.current.getBoundingClientRect();
    const percentage = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const value = Math.round(min + percentage * (max - min));
    
    // Always update hover value when not dragging
    if (!isDragging) {
      setHoverValue(value);
      setHoverPosition({ x: e.clientX, y: e.clientY });
      
      // Handle activity data hover
      if (activityData && activityData.data) {
        const dataIndex = Math.floor(percentage * activityData.data.length);
        const hoveredDataPoint = activityData.data[Math.min(dataIndex, activityData.data.length - 1)];
        if (hoveredDataPoint) {
          setActivityHoverData(hoveredDataPoint);
          setShowActivityTooltip(true);
        }
      }
    }
  }, [isDragging, min, max, activityData]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(null);
  }, []);

  const handleTrackClick = useCallback((e) => {
    if (isDragging) return; // Don't handle track clicks while dragging
    
    const clickValue = getValueFromPosition(e.clientX);
    const startDistance = Math.abs(clickValue - startValue);
    const endDistance = Math.abs(clickValue - endValue);
    
    if (startDistance < endDistance) {
      onChange(Math.min(clickValue, endValue), endValue);
    } else {
      onChange(startValue, Math.max(clickValue, startValue));
    }
  }, [isDragging, getValueFromPosition, startValue, endValue, onChange]);

  const handleTrackMouseLeave = useCallback(() => {
    if (!isDragging) {
      setHoverValue(null);
      setShowActivityTooltip(false);
      setActivityHoverData(null);
    }
  }, [isDragging]);
  // Global mouse event handlers for dragging
  useEffect(() => {
    if (isDragging) {
      const handleGlobalMouseMove = (e) => {
        if (!sliderRef.current) return;
        
        const rect = sliderRef.current.getBoundingClientRect();
        const percentage = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const value = Math.round(min + percentage * (max - min));
        
        if (isDragging === 'start') {
          const newStartValue = Math.min(value, endValue);
          onChange(newStartValue, endValue);
        } else if (isDragging === 'end') {
          const newEndValue = Math.max(value, startValue);
          onChange(startValue, newEndValue);
        }
      };

      const handleGlobalMouseUp = () => {
        setIsDragging(null);
      };

      document.addEventListener('mousemove', handleGlobalMouseMove, { passive: false });
      document.addEventListener('mouseup', handleGlobalMouseUp);
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'grabbing';
      
      return () => {
        document.removeEventListener('mousemove', handleGlobalMouseMove);
        document.removeEventListener('mouseup', handleGlobalMouseUp);
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
      };
    }
  }, [isDragging, min, max, startValue, endValue, onChange]);

  const startPercentage = ((startValue - min) / (max - min)) * 100;
  const endPercentage = ((endValue - min) / (max - min)) * 100;
  
  const startLabel = formatValue(startValue);
  const endLabel = formatValue(endValue);

  const isOverlapping = startValue === endValue;
  const handleStyle = (percentage) => ({
    left: `${percentage}%`,
    ...(isOverlapping ? { '--handle-position': `${percentage}%` } : {}),
  });

  return (
    <div className="dual-range-slider">
      <div className="slider-header">
        <label className="slider-label">{label}:</label>
        <div className="slider-values">
          <span className="value-badge">{startLabel}</span>
          <span className="value-separator">to</span>
          <span className="value-badge">{endLabel}</span>
        </div>
      </div>
      
      <div className="slider-container">
        <div
          ref={sliderRef}
          className="slider-track"
          onClick={handleTrackClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleTrackMouseLeave}
        >
          <ActivityChart activityData={activityData} />
        </div>
        
        <div
          className="slider-range"
          style={{
            left: `${startPercentage}%`,
            width: `${endPercentage - startPercentage}%`,
          }}
        />
        
        <div
          className={`slider-handle${isDragging === 'start' ? ' dragging' : ''}${isOverlapping ? ' overlap start' : ''}`}
          style={handleStyle(startPercentage)}
          onMouseDown={handleMouseDown('start')}
        />
        <div
          className={`slider-handle${isDragging === 'end' ? ' dragging' : ''}${isOverlapping ? ' overlap end' : ''}`}
          style={handleStyle(endPercentage)}
          onMouseDown={handleMouseDown('end')}
        />
        
        <SliderTooltip
          isVisible={(hoverValue !== null || showActivityTooltip) && !isDragging}
          position={hoverPosition}
          hoverValue={hoverValue}
          activityHoverData={activityHoverData}
          activityGranularity={activityData?.granularity}
          formatValue={formatValue}
          formatAmount={formatAmount}
          formatPeriod={formatPeriod}
        />
      </div>
      
      <ActivitySummary activityData={activityData} formatAmount={formatAmount} />
    </div>
  );
};

export default DualRangeSlider;