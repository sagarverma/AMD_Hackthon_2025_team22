# Extract Episodes from Dataset

A script to extract specific episodes from a LeRobot dataset based on timestamps defined in a CSV file.

## Usage

```bash
python extract_episodes.py <source_dataset> <episodes_csv> <output_dataset>
```

### Example

```bash
python extract_episodes.py ../data/santabot_gift_packaging_v2 episodes.csv ../data/santabot_gift_packaging_v2_cleaned
```

## CSV Format

The CSV file must have three columns: `start_time`, `end_time`, and `task`.

Example (`episodes.csv`):

```csv
start_time,end_time,task
0.0,5.0,pick up the red block and place it in the box
5.5,10.5,pick up the blue block and place it in the box
11.0,16.0,pick up the green block and place it in the box
```

- **start_time**: Start timestamp in seconds (inclusive)
- **end_time**: End timestamp in seconds (exclusive)
- **task**: Task description for this episode

## What It Does

1. **Reads the CSV** to get episode definitions
2. **Filters data parquet files** to extract frames within each time range
3. **Extracts video segments** for each camera (top, side, front) based on timestamps
4. **Creates a new dataset** with:
   - Properly indexed episodes (starting from 0)
   - Reset frame indices per episode
   - Updated episode metadata
   - Task definitions
   - Video segments

## Requirements

- `pandas`
- `pyarrow` (for parquet support)
- `numpy`
- `moviepy` (for video extraction) - install with: `pip install moviepy`

## Output Structure

The script creates a new dataset with the standard LeRobot structure:

```
output_dataset/
├── data/
│   └── chunk-000/
│       └── file-000.parquet
├── videos/
│   ├── observation.images.top/
│   │   └── chunk-000/
│   │       └── file-000.mp4, file-001.mp4, ...
│   ├── observation.images.side/
│   │   └── chunk-000/
│   │       └── file-000.mp4, file-001.mp4, ...
│   └── observation.images.front/
│       └── chunk-000/
│           └── file-000.mp4, file-001.mp4, ...
└── meta/
    ├── episodes/
    │   └── chunk-000/
    │       └── file-000.parquet
    ├── tasks.parquet
    ├── info.json
    └── stats.json
```

## Notes

- Timestamps should match the timestamps in the source dataset's data parquet files
- The script automatically handles episode re-indexing (episodes start from 0)
- Frame indices are reset per episode
- Video extraction requires `moviepy` - if not available, data will be extracted but videos will be skipped
- Each episode gets its own video file per camera

