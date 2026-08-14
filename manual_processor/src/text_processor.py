"""
Text Processing Module
Handles OCR result combination and text cleaning
"""

import re
from typing import List, Optional
from dataclasses import dataclass

from src.models import Section
from src.ocr_processor import OCRResult


def combine_ocr_results(ocr_results: List[OCRResult]) -> str:
    """
    Combine OCR results from multiple pages into a single text
    Sorted by page_number.
    """
    if not ocr_results:
        return ""
    
    valid_results = [
        result for result in ocr_results 
        if result is not None and getattr(result, 'text', None) and result.text.strip()
    ]
    
    if not valid_results:
        return ""
    
    # Sort by page_number
    valid_results.sort(key=lambda r: getattr(r, 'page_number', 0))
    
    return "\n\n".join(result.text for result in valid_results)


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted text by removing common OCR noise, normalizing whitespace, etc.
    """
    if not text:
        return ""
    
    cleaned = text
    
    # Full-width space to half-width space
    cleaned = cleaned.replace('\u3000', ' ')
    
    # Full-width digits to half-width
    cleaned = re.sub(r'[\uff10-\uff19]', lambda m: chr(ord(m.group()) - 0xfee0), cleaned)
    
    # Remove control characters except meaningful ones (\t, \n, \r, \f)
    cleaned = ''.join(
        char for char in cleaned
        if ord(char) >= 0x20 or char in ('\t', '\n', '\r', '\f')
    )

    # Normalize multiple spaces per line
    lines = cleaned.split('\n')
    cleaned_lines = []
    for line in lines:
        line_stripped = line.strip()
        # Reduce multiple spaces/tabs into single space
        line_norm = re.sub(r'[ \t]+', ' ', line_stripped)
        cleaned_lines.append(line_norm)
    
    cleaned = '\n'.join(cleaned_lines)
    
    # Limit 4 or more consecutive newlines to 3
    cleaned = re.sub(r'\n{4,}', '\n\n\n', cleaned)
    
    return cleaned.strip()


def normalize_japanese_text(text: str) -> str:
    """Normalize Japanese text, fullwidth alphanumeric to halfwidth, etc."""
    if not text:
        return ""
    # Convert full-width英数字 (U+FF01~U+FF5E) to half-width (U+0021~U+007E)
    res = []
    for char in text:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            res.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            res.append(' ')
        else:
            res.append(char)
    return "".join(res)


def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """Extract top keywords from text, excluding stopwords and short words (<2 chars)"""
    if not text:
        return []
    
    stop_words = {'の', 'は', 'を', 'た', 'が', 'で', 'て', 'と', 'し', 'れ', 'さ', 'です', 'ます', 'これ', 'それ', 'あれ'}
    words = re.findall(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\w]+', text)
    
    word_counts = {}
    for word in words:
        if len(word) < 2 or word in stop_words:
            continue
        word_counts[word] = word_counts.get(word, 0) + 1
    
    sorted_words = sorted(word_counts.keys(), key=lambda w: word_counts[w], reverse=True)
    return sorted_words[:max_keywords]


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences by Japanese and English delimiters"""
    if not text:
        return []
    # Split by 。, !, ?, or . followed by space or newline
    raw_sentences = re.split(r'(?<=[。！？])|(?<=\.)\s+', text)
    sentences = [s.strip() for s in raw_sentences if s and s.strip()]
    return sentences


def remove_duplicate_lines(text: str) -> str:
    """Remove duplicate lines while preserving order"""
    if not text:
        return ""
    seen = set()
    lines = text.split('\n')
    result = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            result.append(line)
    return '\n'.join(result)