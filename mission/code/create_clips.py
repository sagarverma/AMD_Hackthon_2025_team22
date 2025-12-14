#!/usr/bin/env python3
"""
Create video clips from episode boundaries in LeRobot dataset parquet files.
"""

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd


def load_episodes_from_dataset(dataset_root: Path, camera: str = None) -> list[dict]:
    """
    Load episodes from dataset parquet files.
    Returns list of episode dicts with start_time, end_time, and episode_index.
    """
    episodes_dir = dataset_root / "meta" / "episodes"
    if not episodes_dir.exists():
        raise ValueError(f"Episodes directory not found: {episodes_dir}")
    
    episode_dfs = []
    for chunk_dir in sorted(episodes_dir.glob("chunk-*")):
        for parquet_file in sorted(chunk_dir.glob("file-*.parquet")):
            df = pd.read_parquet(parquet_file)
            episode_dfs.append(df)
    
    if not episode_dfs:
        raise ValueError("No episode parquet files found")
    
    episodes_df = pd.concat(episode_dfs, ignore_index=True)
    
    # Load data to get timestamps
    data_dir = dataset_root / "data"
    data_frames = []
    for chunk_dir in sorted(data_dir.glob("chunk-*")):
        for parquet_file in sorted(chunk_dir.glob("file-*.parquet")):
            df = pd.read_parquet(parquet_file)
            data_frames.append(df)
    
    if not data_frames:
        raise ValueError("No data parquet files found")
    
    data_df = pd.concat(data_frames, ignore_index=True)
    data_df = data_df.sort_values('timestamp')
    
    # Get episode boundaries from timestamps
    episodes = []
    for _, ep_row in episodes_df.iterrows():
        episode_idx = int(ep_row['episode_index'])
        
        # Get frames for this episode
        ep_frames = data_df[data_df['episode_index'] == episode_idx]
        if len(ep_frames) == 0:
            continue
        
        # Get video timestamps from episode metadata (these are the actual video timestamps)
        video_info = {}
        start_time = None
        end_time = None
        
        if camera:
            video_chunk = ep_row.get(f'videos/observation.images.{camera}/chunk_index')
            video_file = ep_row.get(f'videos/observation.images.{camera}/file_index')
            video_from = ep_row.get(f'videos/observation.images.{camera}/from_timestamp')
            video_to = ep_row.get(f'videos/observation.images.{camera}/to_timestamp')
            
            if pd.notna(video_chunk) and pd.notna(video_file):
                video_info = {
                    'chunk_index': int(video_chunk),
                    'file_index': int(video_file),
                }
            
            # Use video timestamps if available (these are the actual timestamps in the video file)
            if pd.notna(video_from) and pd.notna(video_to):
                start_time = float(video_from)
                end_time = float(video_to)
        
        # Fallback to data timestamps if video timestamps not available
        if start_time is None or end_time is None:
            start_time = float(ep_frames['timestamp'].min())
            end_time = float(ep_frames['timestamp'].max())
        
        episodes.append({
            'episode_index': episode_idx,
            'start_time': start_time,
            'end_time': end_time,
            'video_info': video_info,
        })
    
    # Sort by episode index
    episodes.sort(key=lambda x: x['episode_index'])
    
    return episodes


def create_clip(
    input_video: Path,
    output_video: Path,
    start_time: float,
    end_time: float,
) -> bool:
    """Create a video clip from start_time to end_time using ffmpeg."""
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
        print(f"    Warning: Copy failed, trying re-encode...")
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
        except subprocess.CalledProcessError:
            print(f"    Error: Failed to create clip")
            return False
    except FileNotFoundError:
        print(f"    Error: ffmpeg not found. Please install ffmpeg.")
        return False


def find_video_file(dataset_root: Path, camera: str, chunk_idx: int = None, file_idx: int = None) -> Path:
    """Find video file in dataset."""
    video_dir = dataset_root / "videos" / f"observation.images.{camera}"
    if not video_dir.exists():
        raise ValueError(f"Video directory not found: {video_dir}")
    
    # If chunk/file specified, use that
    if chunk_idx is not None and file_idx is not None:
        video_file = video_dir / f"chunk-{chunk_idx:03d}" / f"file-{file_idx:03d}.mp4"
        if video_file.exists():
            return video_file
    
    # Otherwise, find first available video file
    for chunk_dir in sorted(video_dir.glob("chunk-*")):
        for video_file in sorted(chunk_dir.glob("file-*.mp4")):
            return video_file
    
    raise ValueError(f"No video file found for camera {camera}")


def create_clips_from_episodes(
    dataset_root: Path,
    episodes: list[dict],
    output_dir: Path,
    camera: str,
) -> None:
    """Create clips for all episodes."""
    print(f"\nCreating clips for camera: {camera}")
    print(f"Output directory: {output_dir}")
    print(f"Number of episodes: {len(episodes)}\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Group episodes by video file (if they have video_info)
    episodes_by_video = {}
    for ep in episodes:
        if ep['video_info']:
            key = (ep['video_info']['chunk_index'], ep['video_info']['file_index'])
            if key not in episodes_by_video:
                episodes_by_video[key] = []
            episodes_by_video[key].append(ep)
        else:
            # Episodes without video_info go to default
            if 'default' not in episodes_by_video:
                episodes_by_video['default'] = []
            episodes_by_video['default'].append(ep)
    
    # Process each video file
    for video_key, video_episodes in episodes_by_video.items():
        if video_key == 'default':
            # Use first available video file
            video_path = find_video_file(dataset_root, camera)
        else:
            chunk_idx, file_idx = video_key
            video_path = find_video_file(dataset_root, camera, chunk_idx, file_idx)
        
        print(f"Using video: {video_path.name}")
        
        for ep in video_episodes:
            episode_idx = ep['episode_index']
            start_time = ep['start_time']
            end_time = ep['end_time']
            duration = end_time - start_time
            
            output_file = output_dir / f"episode_{episode_idx:03d}.mp4"
            
            print(f"  Episode {episode_idx}: {start_time:.2f}s - {end_time:.2f}s ({duration:.2f}s) -> {output_file.name}")
            
            success = create_clip(video_path, output_file, start_time, end_time)
            if success:
                print(f"    ✓ Created")
            else:
                print(f"    ✗ Failed")
    
    print(f"\n✓ Created clips in {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Create video clips from LeRobot dataset episode boundaries"
    )
    parser.add_argument(
        "dataset",
        type=Path,
        help="Path to dataset directory"
    )
    parser.add_argument(
        "camera",
        type=str,
        choices=['top', 'side', 'front'],
        help="Camera name (top, side, or front)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory for clips (default: dataset/clips/camera_name)"
    )
    
    args = parser.parse_args()
    
    if not args.dataset.exists():
        print(f"Error: Dataset directory not found: {args.dataset}")
        sys.exit(1)
    
    # Determine output directory
    if args.output:
        output_dir = args.output
    else:
        output_dir = args.dataset / "clips" / args.camera
    
    # Load episodes from dataset
    try:
        episodes = load_episodes_from_dataset(args.dataset, camera=args.camera)
    except Exception as e:
        print(f"Error loading episodes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if not episodes:
        print("Error: No episodes found in dataset")
        sys.exit(1)
    
    # Create clips
    create_clips_from_episodes(args.dataset, episodes, output_dir, args.camera)


if __name__ == "__main__":
    main()

