from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from enum import Enum

class CorruptionDetectionStrategy(Enum):
    COMMON_WORDS = "common_words"
    GREEK_DICTIONARY = "greek_dictionary" 
    GR_NLP_TOOLKIT = "gr_nlp_toolkit"
    HYBRID = "hybrid"
    
class PreprocessingResult(BaseModel):
    """Result of text preprocessing operations."""
    
    processed_text: str = Field(..., description="The text after preprocessing (stopwords removed, etc.)")
    is_corrupted: bool = Field(..., description="True if the text appears to be corrupted or garbled")
    confidence_score: Optional[float] = Field(None, description="Confidence score for corruption detection (0.0-1.0)")
    performance_stats: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics for the preprocessing")
    corruption_indicators: Dict[str, Any] = Field(default_factory=dict, description="Details about what triggered corruption detection")

    class Config:
        json_encoders = {
            float: lambda v: round(v, 4)  # Round floats to 4 decimal places
        }