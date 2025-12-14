# LeRobot Dataset Workflow Documentation

This document describes the key scripts used for robot teleoperation, data collection, and dataset cleaning workflows.

## Overview

The workflow consists of four main components:
1. **teleop_multi.sh** - Main control script for robot operations
2. **create_clips.py** - Extract video clips from dataset episodes
3. **clip_episode_tagger.py** - Interactive web UI for reviewing and tagging episodes
4. **extract_episodes.py** - Create cleaned dataset from tagged episodes

---

## 1. teleop_multi.sh

**Purpose**: Main bash script for controlling dual-arm robot system (leader-follower setup) with camera management and dataset recording.

### Key Features

- **Multi-Arm Control**: Manages leader (teleoperation) and follower (robot) arms via serial ports (`/dev/ttyACM0`, `/dev/ttyACM1`)
- **Camera Management**: 
  - Detects and validates 3 cameras (top, side, front)
  - Caches camera IDs to avoid repeated selection
  - Captures test images for visual verification
- **Dataset Management**:
  - Lists existing datasets in `/home/versag/data`
  - Supports creating new datasets or resuming existing ones
  - Caches metadata (episodes, episode time, reset time, task description)
  - **Allows changing task description when resuming** (recently added feature)
- **Four Main Operations**:
  1. **Calibrate**: Calibrate leader or follower arm
  2. **Teleoperate**: Manual control with live camera feed
  3. **Record**: Record demonstrations with configurable parameters
  4. **Inference**: Run trained models for evaluation

### Camera Configuration

- Resolution: `320x240` (4:3 aspect ratio)
- FPS: 20
- Cameras: `top`, `side`, `front`
- Special handling for `smolvla` models with camera rename mapping:
  - `top` → `camera1`
  - `side` → `camera2`
  - `front` → `camera3`

### Dataset Configuration

- Base data directory: `/home/versag/data`
- Eval datasets directory: `/home/versag/evals`
- Supports HuggingFace dataset repos (format: `versag/dataset_name`)
- Metadata caching for faster workflow

### Usage Example

```bash
./teleop_multi.sh
# Select: 3) Record
# Choose existing dataset or create new
# When resuming: can change task description
```

---

## 2. create_clips.py

**Purpose**: Extract individual video clips from a LeRobot dataset based on episode boundaries defined in the dataset's parquet files.

### Key Features

- **Reads Episode Metadata**: Loads episode boundaries from `meta/episodes/chunk-*/file-*.parquet`
- **Video Timestamp Mapping**: Uses video timestamps (`from_timestamp`, `to_timestamp`) from episode metadata for accurate extraction
- **Multi-Camera Support**: Creates clips for specified camera (`top`, `side`, or `front`)
- **Robust Video Extraction**: Uses `ffmpeg` with codec copy (fast) and fallback to re-encoding if needed
- **Episode-Based Naming**: Output clips named as `episode_XXX.mp4` where XXX is the episode index

### Workflow

1. Loads all episode metadata from dataset parquet files
2. For each episode, extracts video segment using timestamps
3. Groups episodes by source video file for efficient processing
4. Creates clips in output directory (default: `dataset/clips/camera_name/`)

### Usage

```bash
python create_clips.py <dataset_path> <camera> [-o output_dir]

# Example:
python create_clips.py ../data/santabot_gift_packaging_v2 side -o ./clips/side
```

### Output

- Individual MP4 files for each episode
- Named: `episode_000.mp4`, `episode_001.mp4`, etc.
- Preserves original video codec when possible

---

## 3. clip_episode_tagger.py

**Purpose**: Flask-based web application for reviewing video clips and marking episode boundaries with color class assignments.

### Key Features

- **Interactive Web UI**: Browser-based interface for clip review
- **Time Slider**: Visual timeline with start/end markers and episode ranges
- **Color Class Mapping**: Automatically maps color selections to task descriptions:
  - `red` → "pick red cube and put in red square"
  - `orange` → "pick orange cube and put in orange square"
  - `brown` → "pick brown cube and put in yellow square"
  - `light-blue` → "pick light-blue cube and put in green square"
  - `dark-blue` → "pick dark-blue cube and put in dark-blue square"
- **Episode Marking**: Mark start/end times for multiple episodes within a single clip
- **CSV Export**: Saves episode definitions to CSV file with columns: `clip_name`, `start_time`, `end_time`, `task`

### Workflow

1. Start Flask server pointing to clips directory
2. Navigate through clips in browser
3. For each clip, mark episode boundaries:
   - Play video and navigate to start time
   - Click "Mark Start" button
   - Navigate to end time
   - Click "Mark End" button
   - Select color class (automatically maps to task)
4. Save episodes to CSV (appends to file)

### Usage

```bash
python clip_episode_tagger.py <clips_directory> [--output episodes.csv]

# Example:
python clip_episode_tagger.py ./clips/side --output episodes.csv
```

Then open `http://localhost:5000` in browser.

### Output CSV Format

```csv
clip_name,start_time,end_time,task
episode_000.mp4,0.0,5.234,pick red cube and put in red square
episode_000.mp4,5.5,10.789,pick orange cube and put in orange square
episode_001.mp4,0.0,6.123,pick brown cube and put in yellow square
```

---

## 4. extract_episodes.py

**Purpose**: Create a new, cleaned LeRobot dataset from CSV-defined episodes, maintaining the original dataset structure.

### Key Features

- **CSV-Based Episode Definition**: Reads episodes from CSV with `clip_name`, `start_time`, `end_time`, `task`
- **Timestamp Mapping**: 
  - Maps relative timestamps from clips back to absolute timestamps in original dataset videos
  - Handles episode-relative timestamps in data parquet files
  - Uses actual video segment durations (via `ffprobe`) for precise cumulative timestamp calculation
- **Dataset Structure Preservation**: 
  - Creates single concatenated video per camera (`file-000.mp4`)
  - Maintains original directory structure (`data/`, `videos/`, `meta/`)
  - Resets `timestamp` and `frame_index` to 0 for each new episode in data parquet
- **Metadata Updates**:
  - Updates `info.json` with total episodes, frames, tasks, and splits
  - Creates `episodes.parquet` with proper episode metadata
  - Creates `tasks.parquet` with task definitions
  - Updates `stats.json` with dataset statistics
- **Video Extraction**: Uses `ffmpeg` for robust video segment extraction and concatenation

### Workflow

1. Loads source dataset data and episode metadata
2. For each CSV episode:
   - Maps clip timestamps to original video timestamps
   - Filters data parquet rows by episode and timestamp range
   - Extracts video segments for all cameras
3. Concatenates all video segments per camera into single file
4. Creates new episode metadata with cumulative timestamps
5. Resets timestamps in data parquet to be episode-relative
6. Updates all metadata files (`info.json`, `stats.json`, `tasks.parquet`, `episodes.parquet`)

### Usage

```bash
python extract_episodes.py <source_dataset> <episodes_csv> <output_dataset> [--clips-dir clips_dir]

# Example:
python extract_episodes.py ../data/santabot_gift_packaging_v2 episodes.csv ../data/santabot_gift_packaging_v2_cleaned
```

### Input CSV Format

```csv
clip_name,start_time,end_time,task
episode_000.mp4,0.0,5.234,pick red cube and put in red square
episode_000.mp4,5.5,10.789,pick orange cube and put in orange square
episode_001.mp4,0.0,6.123,pick brown cube and put in yellow square
```

### Output Dataset Structure

```
output_dataset/
├── data/
│   └── chunk-000/
│       └── file-000.parquet          # All episodes concatenated
├── videos/
│   ├── observation.images.top/
│   │   └── chunk-000/
│   │       └── file-000.mp4          # Single concatenated video
│   ├── observation.images.side/
│   │   └── chunk-000/
│   │       └── file-000.mp4
│   └── observation.images.front/
│       └── chunk-000/
│           └── file-000.mp4
└── meta/
    ├── info.json                     # Updated with totals and splits
    ├── stats.json                    # Dataset statistics
    ├── tasks.parquet                 # Task definitions
    └── episodes/
        └── chunk-000/
            └── file-000.parquet      # Episode metadata
```

### Key Technical Details

- **Timestamp Synchronization**: Ensures data timestamps (episode-relative) and video timestamps (cumulative in concatenated video) are correctly synchronized
- **Video Duration Precision**: Uses `ffprobe` to get actual video segment durations, avoiding timestamp mismatches due to frame boundaries
- **Episode Indexing**: Re-indexes episodes starting from 0 in the new dataset
- **Frame Index Reset**: Resets `frame_index` to 0 for each new episode in data parquet

---

## Complete Workflow Example

### Step 1: Record Data
```bash
./teleop_multi.sh
# Select: 3) Record
# Create or resume dataset
# Record demonstrations
```

### Step 2: Create Clips from Episodes
```bash
python create_clips.py ../data/santabot_gift_packaging_v2 side -o ./clips/side
```

### Step 3: Review and Tag Episodes
```bash
python clip_episode_tagger.py ./clips/side --output episodes.csv
# Open http://localhost:5000
# Mark episode boundaries and assign color classes
# Save episodes
```

### Step 4: Create Cleaned Dataset
```bash
python extract_episodes.py ../data/santabot_gift_packaging_v2 episodes.csv ../data/santabot_gift_packaging_v2_cleaned
```

### Step 5: Train Model
```bash
# Use cleaned dataset for training
lerobot-train ...
```

---

## Dependencies

### System Requirements
- `ffmpeg` and `ffprobe` (for video processing)
- Python 3.10+
- LeRobot environment

### Python Packages
- `pandas` (data manipulation)
- `pyarrow` (parquet support)
- `numpy` (numerical operations)
- `flask` (web UI for clip_episode_tagger.py)

### Optional
- `moviepy` (not required, `ffmpeg` is used instead)

---

## Notes

- **Dataset Structure**: All scripts maintain the standard LeRobot dataset structure with `data/`, `videos/`, and `meta/` directories
- **Timestamp Handling**: Careful attention to timestamp synchronization ensures training compatibility
- **Video Codecs**: `ffmpeg` is used for broad codec support (including AV1)
- **Resume Support**: `teleop_multi.sh` allows resuming datasets and changing task descriptions
- **Validation Split**: `extract_episodes.py` supports creating validation splits in `info.json`

