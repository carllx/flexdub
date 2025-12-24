#!/usr/bin/env python3
"""
Clean YouTube auto-generated SRT subtitles.

YouTube auto-captions use a "rolling" format where:
1. Each cue shows 2 lines (previous + current)
2. Transition frames have 10ms duration
3. Same text repeats across multiple cues

This script extracts unique text segments and rebuilds clean subtitles.
"""

import re
import sys
from pathlib import Path


def parse_srt(content: str) -> list[dict]:
    """Parse SRT content into list of cues."""
    pattern = re.compile(
        r'(\d+)\s*\n'
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'
        r'(.*?)(?=\n\n|\n*$)',
        re.DOTALL
    )
    
    cues = []
    for match in pattern.finditer(content):
        idx, start, end, text = match.groups()
        cues.append({
            'index': int(idx),
            'start': start,
            'end': end,
            'text': text.strip()
        })
    return cues


def time_to_ms(time_str: str) -> int:
    """Convert SRT timestamp to milliseconds."""
    h, m, rest = time_str.split(':')
    s, ms = rest.split(',')
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def ms_to_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp."""
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def clean_cues(cues: list[dict], min_duration_ms: int = 50, 
               max_duration_ms: int = 15000, max_chars: int = 250) -> list[dict]:
    """
    Clean YouTube auto-generated cues by reconstructing from rolling format.
    
    Strategy: Build a timeline of unique text segments by tracking what's new
    in each cue compared to the previous one.
    
    Args:
        cues: Raw parsed cues
        min_duration_ms: Filter out transition frames shorter than this
        max_duration_ms: Maximum duration per output cue (default 15s)
        max_chars: Maximum characters per output cue (default 250)
    """
    if not cues:
        return []
    
    # Step 1: Filter out very short transition frames
    filtered = []
    for cue in cues:
        duration = time_to_ms(cue['end']) - time_to_ms(cue['start'])
        if duration >= min_duration_ms:
            filtered.append(cue)
    
    if not filtered:
        return []
    
    # Step 2: Extract unique text segments
    # Track all unique lines and their first appearance time
    segments = []
    seen_lines = set()
    
    for cue in filtered:
        lines = [l.strip() for l in cue['text'].split('\n') if l.strip()]
        for line in lines:
            if line and line not in seen_lines:
                seen_lines.add(line)
                segments.append({
                    'start': cue['start'],
                    'end': cue['end'],
                    'text': line
                })
    
    # Step 3: Merge consecutive segments into natural blocks
    # Respect max_duration_ms and max_chars limits
    if not segments:
        return []
    
    merged = [segments[0].copy()]
    
    for seg in segments[1:]:
        prev = merged[-1]
        prev_start_ms = time_to_ms(prev['start'])
        prev_end_ms = time_to_ms(prev['end'])
        curr_start_ms = time_to_ms(seg['start'])
        curr_end_ms = time_to_ms(seg['end'])
        gap_ms = curr_start_ms - prev_end_ms
        
        prev_text = prev['text']
        combined_len = len(prev_text) + len(seg['text']) + 1
        combined_duration = curr_end_ms - prev_start_ms
        
        # Check if merging would exceed limits
        exceeds_duration = combined_duration > max_duration_ms
        exceeds_chars = combined_len > max_chars
        ends_sentence = prev_text.rstrip().endswith(('.', '!', '?', '。', '！', '？'))
        large_gap = gap_ms > 200
        
        # Merge only if within limits and no natural break
        if not exceeds_duration and not exceeds_chars and not ends_sentence and not large_gap:
            prev['text'] = prev_text + ' ' + seg['text']
            prev['end'] = seg['end']
        else:
            merged.append(seg.copy())
    
    return merged


def format_srt(cues: list[dict]) -> str:
    """Format cues back to SRT format."""
    lines = []
    for i, cue in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{cue['start']} --> {cue['end']}")
        lines.append(cue['text'])
        lines.append('')
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python clean_youtube_srt.py <input.srt> [output.srt]")
        print("\nCleans YouTube auto-generated subtitles by removing duplicates")
        print("and merging rolling 2-line format into single lines.")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix('.clean.srt')
    
    content = input_path.read_text(encoding='utf-8')
    cues = parse_srt(content)
    print(f"Parsed {len(cues)} cues from {input_path}")
    
    cleaned = clean_cues(cues)
    print(f"Cleaned to {len(cleaned)} cues")
    
    output = format_srt(cleaned)
    output_path.write_text(output, encoding='utf-8')
    print(f"Saved to {output_path}")


if __name__ == '__main__':
    main()
