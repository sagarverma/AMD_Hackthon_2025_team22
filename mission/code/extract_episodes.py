#!/usr/bin/env python3
"""
Extract episodes from a dataset based on CSV file with timestamps.
CSV format: start_time, end_time, task
Creates a new dataset folder with only the specified episodes.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


def load_all_data(dataset_root: Path) -> pd.DataFrame:
    """Load all data from all parquet files."""
    data_dir = dataset_root / "data"
    if not data_dir.exists():
        raise ValueError(f"Data directory not found: {data_dir}")
    
    data_frames = []
    for chunk_dir in sorted(data_dir.glob("chunk-*")):
        for parquet_file in sorted(chunk_dir.glob("file-*.parquet")):
            df = pd.read_parquet(parquet_file)
            data_frames.append(df)
    
    if not data_frames:
        raise ValueError("No data files found")
    
    all_data = pd.concat(data_frames, ignore_index=True)
    all_data = all_data.sort_values('timestamp')
    return all_data


def get_video_duration(video_path: Path) -> float:
    """Get the actual duration of a video file in seconds using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        duration = float(result.stdout.decode().strip())
        return duration
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None


def extract_video_segment(
    input_video: Path,
    output_video: Path,
    start_time: float,
    end_time: float,
) -> bool:
    """Extract a segment from a video file using ffmpeg."""
    output_video.parent.mkdir(parents=True, exist_ok=True)
    
    duration = end_time - start_time
    
    # Use ffmpeg to extract clip (more reliable, supports more codecs)
    cmd = [
        'ffmpeg',
        '-i', str(input_video),
        '-ss', str(start_time),
        '-t', str(duration),
        '-c', 'copy',  # Copy codec (fast, no re-encoding)
        '-avoid_negative_ts', 'make_zero',
        '-y',  # Overwrite output file
        str(output_video)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return output_video.exists() and output_video.stat().st_size > 0
    except subprocess.CalledProcessError as e:
        # If copy fails, try re-encoding
        print(f"    Warning: Copy failed, trying re-encode. Error: {e.stderr.decode().strip()}")
        cmd_reencode = [
            'ffmpeg',
            '-i', str(input_video),
            '-ss', str(start_time),
            '-t', str(duration),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-y',
            str(output_video)
        ]
        try:
            subprocess.run(
                cmd_reencode,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return output_video.exists() and output_video.stat().st_size > 0
        except subprocess.CalledProcessError as e_reencode:
            print(f"    Error: Failed to create clip even with re-encoding. Error: {e_reencode.stderr.decode().strip()}")
            return False
    except FileNotFoundError:
        print(f"    Error: ffmpeg not found. Please install ffmpeg.")
        return False


def find_video_file(dataset_root: Path, camera: str) -> Optional[Path]:
    """Find the main video file for a camera (assumes single main video file containing all episodes)."""
    video_dir = dataset_root / "videos" / f"observation.images.{camera}"
    if not video_dir.exists():
        return None
    
    # Look for video files in chunk directories
    # Returns the first video file found (assuming it's the main file with all episodes)
    for chunk_dir in sorted(video_dir.glob("chunk-*")):
        video_files = sorted(chunk_dir.glob("file-*.mp4"))
        if video_files:
            # If multiple files, use the first one (or could combine them, but assuming single file)
            return video_files[0]
    
    return None


def find_clip_video_file(dataset_root: Path, camera: str, clip_name: str) -> Optional[Path]:
    """Find the original video file that contains the clip."""
    # Extract episode index from clip name (e.g., "episode_000.mp4" -> 0)
    # Or try to find the video file that would contain this clip
    # For now, we'll need to map clip names back to episode indices and find the video
    
    # Try to find video files in the dataset
    video_dir = dataset_root / "videos" / f"observation.images.{camera}"
    if not video_dir.exists():
        return None
    
    # Look for video files - typically there's one main video file per camera
    for chunk_dir in sorted(video_dir.glob("chunk-*")):
        for video_file in sorted(chunk_dir.glob("file-*.mp4")):
            return video_file
    
    return None


def create_new_dataset(
    source_dataset: Path,
    output_dataset: Path,
    episodes_csv: Path,
    clips_dir: Optional[Path] = None,
) -> None:
    """Create a new dataset from CSV-defined episodes."""
    
    print(f"Reading episodes from: {episodes_csv}")
    episodes_df = pd.read_csv(episodes_csv)
    
    # Validate CSV columns
    required_columns = ['start_time', 'end_time', 'task']
    for col in required_columns:
        if col not in episodes_df.columns:
            raise ValueError(f"CSV must have '{col}' column")
    
    # Check if clip_name column exists
    has_clip_names = 'clip_name' in episodes_df.columns
    
    print(f"Found {len(episodes_df)} episodes to extract")
    if has_clip_names:
        unique_clips = episodes_df['clip_name'].nunique()
        print(f"Episodes from {unique_clips} different clips")
    
    # Load all source data
    print("Loading source data...")
    source_data = load_all_data(source_dataset)
    print(f"Source data has {len(source_data)} frames")
    
    # Create output directory structure
    output_dataset.mkdir(parents=True, exist_ok=True)
    (output_dataset / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
    (output_dataset / "meta" / "episodes" / "chunk-000").mkdir(parents=True, exist_ok=True)
    (output_dataset / "meta").mkdir(parents=True, exist_ok=True)
    
    # Load episode metadata to map clip names to original episode timestamps
    episodes_meta = None
    if has_clip_names:
        print("Loading episode metadata to map clips to original timestamps...")
        episodes_meta_dir = source_dataset / "meta" / "episodes"
        if episodes_meta_dir.exists():
            meta_dfs = []
            for chunk_dir in sorted(episodes_meta_dir.glob("chunk-*")):
                for parquet_file in sorted(chunk_dir.glob("file-*.parquet")):
                    df = pd.read_parquet(parquet_file)
                    meta_dfs.append(df)
            if meta_dfs:
                episodes_meta = pd.concat(meta_dfs, ignore_index=True)
                print(f"  Loaded metadata for {len(episodes_meta)} episodes")
    
    # Process each episode
    all_extracted_data = []
    episode_metadata = []
    task_map = {}
    next_task_index = 0
    
    for csv_idx, row in episodes_df.iterrows():
        clip_name = row.get('clip_name', '')
        start_time = float(row['start_time'])
        end_time = float(row['end_time'])
        task = str(row['task']).strip()
        
        # Extract original episode index from clip name
        original_episode_idx = None
        if has_clip_names and clip_name:
            import re
            match = re.search(r'episode_(\d+)', clip_name)
            if match:
                original_episode_idx = int(match.group(1))
        
        # Get absolute video timestamps for metadata (if we have episode metadata)
        absolute_video_start = start_time
        absolute_video_end = end_time
        if original_episode_idx is not None and episodes_meta is not None:
            orig_ep = episodes_meta[episodes_meta['episode_index'] == original_episode_idx]
            if len(orig_ep) > 0:
                orig_ep = orig_ep.iloc[0]
                orig_video_start = orig_ep.get('videos/observation.images.top/from_timestamp')
                if pd.notna(orig_video_start):
                    # CSV timestamps are relative to clip/episode, add original video start
                    absolute_video_start = float(orig_video_start) + start_time
                    absolute_video_end = float(orig_video_start) + end_time
        
        print(f"\nProcessing episode {csv_idx} from clip {clip_name}")
        if original_episode_idx is not None:
            print(f"  Original episode index: {original_episode_idx}")
        print(f"  Episode-relative times: {start_time:.2f}s - {end_time:.2f}s")
        if original_episode_idx is not None:
            print(f"  Absolute video times: {absolute_video_start:.2f}s - {absolute_video_end:.2f}s")
        print(f"  Task: {task}")
        
        # Filter data: timestamps in data are relative to each episode (start at 0 for each episode)
        # So we filter by episode_index AND timestamp within that episode
        if original_episode_idx is not None:
            episode_data = source_data[
                (source_data['episode_index'] == original_episode_idx) &
                (source_data['timestamp'] >= start_time) & 
                (source_data['timestamp'] < end_time)
            ].copy()
        else:
            # Fallback: try to find by timestamp only (less reliable)
            episode_data = source_data[
                (source_data['timestamp'] >= start_time) & 
                (source_data['timestamp'] < end_time)
            ].copy()
        
        if len(episode_data) == 0:
            print(f"  Warning: No data found for this time range, skipping")
            continue
        
        # Get or create task index
        if task not in task_map:
            task_map[task] = next_task_index
            next_task_index += 1
        task_index = task_map[task]
        
        # Reset indices for new episode
        episode_data['episode_index'] = csv_idx  # Use CSV row index as episode index
        episode_data['task_index'] = task_index
        
        # Reset frame_index to start from 0 for this episode
        episode_data['frame_index'] = range(len(episode_data))
        
        # Reset timestamps to start from 0 for this episode (timestamps are relative to episode start)
        episode_start_timestamp = episode_data['timestamp'].min()
        episode_data['timestamp'] = episode_data['timestamp'] - episode_start_timestamp
        
        # Reset index to be sequential
        if len(all_extracted_data) == 0:
            episode_data['index'] = range(len(episode_data))
        else:
            last_index = all_extracted_data[-1]['index'].max() + 1
            episode_data['index'] = range(last_index, last_index + len(episode_data))
        
        all_extracted_data.append(episode_data)
        
        # Create episode metadata
        episode_meta = {
            'episode_index': csv_idx,  # Use CSV row index as episode index
            'tasks': [task],  # Store as array
            'length': len(episode_data),
            'data/chunk_index': 0,
            'data/file_index': 0,
            'dataset_from_index': int(episode_data['index'].min()),
            'dataset_to_index': int(episode_data['index'].max() + 1),
        }
        
        # Add video metadata (will be filled after video extraction)
        for camera in ['top', 'side', 'front']:
            episode_meta[f'videos/observation.images.{camera}/chunk_index'] = 0
            episode_meta[f'videos/observation.images.{camera}/file_index'] = csv_idx
            episode_meta[f'videos/observation.images.{camera}/from_timestamp'] = absolute_video_start
            episode_meta[f'videos/observation.images.{camera}/to_timestamp'] = absolute_video_end
        
        # Add stats (simplified - can compute full stats if needed)
        for key in ['action', 'observation.state']:
            if key in episode_data.columns:
                values = episode_data[key].apply(lambda x: np.array(x) if isinstance(x, (list, np.ndarray)) else x)
                if len(values) > 0 and isinstance(values.iloc[0], np.ndarray):
                    stacked = np.stack(values.values)
                    episode_meta[f'stats/{key}/min'] = stacked.min(axis=0).tolist()
                    episode_meta[f'stats/{key}/max'] = stacked.max(axis=0).tolist()
                    episode_meta[f'stats/{key}/mean'] = stacked.mean(axis=0).tolist()
                    episode_meta[f'stats/{key}/std'] = stacked.std(axis=0).tolist()
        
        episode_metadata.append(episode_meta)
    
    if not all_extracted_data:
        raise ValueError("No episodes were extracted")
    
    # Combine all extracted data
    print("\nCombining extracted data...")
    combined_data = pd.concat(all_extracted_data, ignore_index=True)
    
    # Save data parquet file
    data_file = output_dataset / "data" / "chunk-000" / "file-000.parquet"
    print(f"Saving data to: {data_file}")
    combined_data.to_parquet(data_file, index=False)
    
    # Save tasks
    tasks_data = {task: {'task_index': idx} for task, idx in task_map.items()}
    tasks_df = pd.DataFrame.from_dict(tasks_data, orient='index')
    tasks_file = output_dataset / "meta" / "tasks.parquet"
    print(f"Saving tasks to: {tasks_file}")
    tasks_df.to_parquet(tasks_file)
    
    # Extract and concatenate video segments into a single video per camera
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        FFMPEG_AVAILABLE = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        FFMPEG_AVAILABLE = False
    
    if FFMPEG_AVAILABLE:
        print("\nExtracting and concatenating video segments...")
        cameras = ['top', 'side', 'front']
        
        # Calculate cumulative timestamps once (same for all cameras since they're synchronized)
        cumulative_times = {}
        cumulative_time = 0.0
        for csv_idx, row in episodes_df.iterrows():
            start_time = float(row['start_time'])
            end_time = float(row['end_time'])
            duration = end_time - start_time
            cumulative_times[csv_idx] = cumulative_time
            cumulative_time += duration
        
        for camera in cameras:
            source_video = find_video_file(source_dataset, camera)
            if source_video is None:
                print(f"  Warning: No video found for camera {camera}, skipping")
                continue
            
            print(f"  Processing {camera} camera...")
            video_output_dir = output_dataset / "videos" / f"observation.images.{camera}" / "chunk-000"
            video_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Temporary directory for episode segments
            temp_dir = video_output_dir / "temp_segments"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            segment_files = []
            
            # Extract each episode segment
            for csv_idx, row in episodes_df.iterrows():
                clip_name = row.get('clip_name', '')
                start_time = float(row['start_time'])
                end_time = float(row['end_time'])
                duration = end_time - start_time
                
                # Get absolute video timestamps from original dataset
                absolute_video_start = start_time
                absolute_video_end = end_time
                if has_clip_names and clip_name and episodes_meta is not None:
                    match = re.search(r'episode_(\d+)', clip_name)
                    if match:
                        original_episode_idx = int(match.group(1))
                        orig_ep = episodes_meta[episodes_meta['episode_index'] == original_episode_idx]
                        if len(orig_ep) > 0:
                            orig_ep = orig_ep.iloc[0]
                            orig_video_start = orig_ep.get(f'videos/observation.images.{camera}/from_timestamp')
                            if pd.notna(orig_video_start):
                                absolute_video_start = float(orig_video_start) + start_time
                                absolute_video_end = float(orig_video_start) + end_time
                
                temp_segment = temp_dir / f"segment_{csv_idx:03d}.mp4"
                print(f"    Extracting episode {csv_idx}: {absolute_video_start:.2f}s - {absolute_video_end:.2f}s")
                
                success = extract_video_segment(source_video, temp_segment, absolute_video_start, absolute_video_end)
                if success:
                    segment_files.append(temp_segment)
                    
                    # Get actual duration of extracted segment (may differ slightly due to frame boundaries)
                    actual_duration = get_video_duration(temp_segment)
                    if actual_duration is None:
                        print(f"    Warning: Could not get video duration, using CSV duration")
                        actual_duration = duration
                    
                    # Update episode metadata with cumulative timestamps in concatenated video
                    # Video timestamps must be cumulative (where episode starts in concatenated video)
                    # Data timestamps are relative to episode start (0 for each episode)
                    # LeRobot adds data timestamp to video from_timestamp to get absolute position
                    episode_start_time = cumulative_times[csv_idx]
                    episode_metadata[csv_idx][f'videos/observation.images.{camera}/from_timestamp'] = episode_start_time
                    episode_metadata[csv_idx][f'videos/observation.images.{camera}/to_timestamp'] = episode_start_time + actual_duration
                    episode_metadata[csv_idx][f'videos/observation.images.{camera}/file_index'] = 0  # All in file-000
                    
                    # Update cumulative time for next episode using actual duration
                    if csv_idx + 1 < len(episodes_df):
                        cumulative_times[csv_idx + 1] = episode_start_time + actual_duration
                else:
                    print(f"    Warning: Failed to extract segment for episode {csv_idx}")
            
            # Concatenate all segments into a single video file
            if segment_files:
                output_video = video_output_dir / "file-000.mp4"
                print(f"    Concatenating {len(segment_files)} segments into {output_video.name}...")
                
                # Create concat file list for ffmpeg
                concat_file = temp_dir / "concat_list.txt"
                with open(concat_file, 'w') as f:
                    for seg_file in segment_files:
                        f.write(f"file '{seg_file.absolute()}'\n")
                
                # Concatenate using ffmpeg
                cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_file),
                    '-c', 'copy',  # Copy codec (fast, no re-encoding)
                    '-y',
                    str(output_video)
                ]
                
                try:
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    print(f"    ✓ Created concatenated video: {output_video.name}")
                except subprocess.CalledProcessError as e:
                    # If copy fails, try re-encoding
                    print(f"    Warning: Copy failed, trying re-encode...")
                    cmd_reencode = [
                        'ffmpeg',
                        '-f', 'concat',
                        '-safe', '0',
                        '-i', str(concat_file),
                        '-c:v', 'libx264',
                        '-c:a', 'aac',
                        '-preset', 'fast',
                        '-y',
                        str(output_video)
                    ]
                    subprocess.run(cmd_reencode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    print(f"    ✓ Created concatenated video (re-encoded): {output_video.name}")
                
                # Clean up temporary segments
                for seg_file in segment_files:
                    seg_file.unlink()
                concat_file.unlink()
                temp_dir.rmdir()
            else:
                print(f"    Warning: No segments extracted for {camera} camera")
                temp_dir.rmdir()
        
        # Save episode metadata with updated video timestamps (after all cameras processed)
        episodes_df_meta = pd.DataFrame(episode_metadata)
        episodes_file = output_dataset / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
        episodes_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nSaving episode metadata with concatenated video timestamps...")
        episodes_df_meta.to_parquet(episodes_file, index=False)
    else:
        print("\nSkipping video extraction (ffmpeg not available)")
        print("  Video directories will be created but videos will not be extracted")
        # Create video directory structure anyway
        for camera in ['top', 'side', 'front']:
            video_output_dir = output_dataset / "videos" / f"observation.images.{camera}" / "chunk-000"
            video_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Update info.json with new dataset information
    source_info = source_dataset / "meta" / "info.json"
    if source_info.exists():
        with open(source_info) as f:
            info = json.load(f)
        
        # Update with new dataset statistics
        info['total_episodes'] = len(episode_metadata)
        info['total_frames'] = len(combined_data)
        info['total_tasks'] = len(task_map)
        
        # Set up splits - default to all train, but can be customized
        # Format: "start:end" where end is exclusive
        # Example with validation: {"train": "0:115", "val": "115:144"}
        info['splits'] = {"train": f"0:{len(episode_metadata)}"}
        
        # Keep other fields like fps, features, robot_type, etc. from original
        
        dest_info = output_dataset / "meta" / "info.json"
        dest_info.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_info, 'w') as f:
            json.dump(info, f, indent=2)
        print(f"\n✓ Updated info.json:")
        print(f"  Total episodes: {info['total_episodes']}")
        print(f"  Total frames: {info['total_frames']}")
        print(f"  Total tasks: {info['total_tasks']}")
    else:
        print("\nWarning: Source info.json not found, skipping info.json update")
    
    # Update stats.json with new dataset info
    source_stats = source_dataset / "meta" / "stats.json"
    if source_stats.exists():
        with open(source_stats) as f:
            stats = json.load(f)
        # Update episode count if it exists
        if 'num_episodes' in stats:
            stats['num_episodes'] = len(episode_metadata)
        dest_stats = output_dataset / "meta" / "stats.json"
        dest_stats.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_stats, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"✓ Updated stats.json")
    else:
        print("Warning: Source stats.json not found, skipping stats.json update")
    
    print(f"\n✓ Dataset extraction complete!")
    print(f"  Output dataset: {output_dataset}")
    print(f"  Episodes: {len(episode_metadata)}")
    print(f"  Total frames: {len(combined_data)}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract episodes from a dataset based on CSV timestamps"
    )
    parser.add_argument(
        "source_dataset",
        type=Path,
        help="Path to source dataset directory"
    )
    parser.add_argument(
        "episodes_csv",
        type=Path,
        help="Path to CSV file with columns: start_time, end_time, task"
    )
    parser.add_argument(
        "output_dataset",
        type=Path,
        help="Path to output dataset directory (will be created)"
    )
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=None,
        help="Path to clips directory (optional, for reference)"
    )
    
    args = parser.parse_args()
    
    if not args.source_dataset.exists():
        print(f"Error: Source dataset not found: {args.source_dataset}")
        sys.exit(1)
    
    if not args.episodes_csv.exists():
        print(f"Error: Episodes CSV not found: {args.episodes_csv}")
        sys.exit(1)
    
    # Check for ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("ffmpeg found - video extraction will be available")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Warning: ffmpeg not available. Video extraction will be skipped.")
        print("Install with: sudo apt-get install ffmpeg (or conda install -c conda-forge ffmpeg)")
        print("Continuing without video extraction...")
    
    try:
        create_new_dataset(args.source_dataset, args.output_dataset, args.episodes_csv, args.clips_dir)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

