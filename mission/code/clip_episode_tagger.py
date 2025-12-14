#!/usr/bin/env python3
"""
Flask app to tag episodes within video clips.
Allows marking start_time, end_time, and color_class for each episode.
"""

import csv
import sys
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

app = Flask(__name__)

# Global data
CLIPS_DIR: Optional[Path] = None
OUTPUT_CSV: Optional[Path] = None

# Color to task mapping
COLOR_TASKS = {
    'red': 'pick red cube and put in red square',
    'orange': 'pick orange cube and put in orange square',
    'brown': 'pick brown cube and put in yellow square',
    'light-blue': 'pick light-blue cube and put in green square',
    'dark-blue': 'pick dark-blue cube and put in dark-blue square',
}


def get_clips() -> list[dict]:
    """Get list of all clips."""
    if CLIPS_DIR is None or not CLIPS_DIR.exists():
        return []
    
    clips = []
    for clip_file in sorted(CLIPS_DIR.glob("*.mp4")):
        clips.append({
            'name': clip_file.name,
            'path': clip_file.name,
        })
    
    return clips


@app.route('/')
def index():
    """Main page."""
    return render_template('clip_episode_tagger.html')


@app.route('/api/clips')
def get_clips_api():
    """Get all clips."""
    clips = get_clips()
    return jsonify({'clips': clips, 'total': len(clips)})


@app.route('/api/clip/<clip_name>')
def get_clip(clip_name: str):
    """Serve video clip file."""
    if CLIPS_DIR is None:
        return jsonify({'error': 'Clips directory not set'}), 400
    
    clip_path = CLIPS_DIR / clip_name
    if not clip_path.exists():
        return jsonify({'error': 'Clip not found'}), 404
    
    return send_from_directory(str(CLIPS_DIR), clip_name, mimetype='video/mp4')


@app.route('/api/save', methods=['POST'])
def save_episodes():
    """Save episodes to CSV."""
    data = request.json
    episodes = data.get('episodes', [])
    clip_name = data.get('clip_name', '')
    
    if OUTPUT_CSV is None:
        return jsonify({'error': 'Output CSV path not set'}), 400
    
    if not episodes:
        return jsonify({'error': 'No episodes to save'}), 400
    
    # Write CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file exists - if so, append; otherwise create new
    file_exists = OUTPUT_CSV.exists()
    
    with open(OUTPUT_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['clip_name', 'start_time', 'end_time', 'task'])
        
        for ep in episodes:
            color = ep.get('color', '')
            task = COLOR_TASKS.get(color, '')
            writer.writerow([
                clip_name,
                f"{ep['start_time']:.3f}",
                f"{ep['end_time']:.3f}",
                task
            ])
    
    return jsonify({
        'success': True,
        'episodes_saved': len(episodes),
        'output_file': str(OUTPUT_CSV)
    })


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python clip_episode_tagger.py <clips_directory> [--output episodes.csv]")
        sys.exit(1)
    
    CLIPS_DIR = Path(sys.argv[1])
    if not CLIPS_DIR.exists():
        print(f"Error: Clips directory not found: {CLIPS_DIR}")
        sys.exit(1)
    
    # Parse optional output argument
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            OUTPUT_CSV = Path(sys.argv[idx + 1])
    else:
        OUTPUT_CSV = CLIPS_DIR.parent / "episodes.csv"
    
    clips = get_clips()
    if not clips:
        print(f"Warning: No clips found in {CLIPS_DIR}")
    
    print(f"Clips directory: {CLIPS_DIR}")
    print(f"Output CSV: {OUTPUT_CSV}")
    print(f"Found {len(clips)} clips")
    print("\nStarting Flask server...")
    print("Open http://localhost:5000 in your browser")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

