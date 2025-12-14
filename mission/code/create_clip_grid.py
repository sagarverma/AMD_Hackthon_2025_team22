#!/usr/bin/env python3
"""
Create a grid view video showing all clips with all three camera views combined.
For each episode, combines front, side, and top views into a single frame.
Then creates a grid layout showing multiple episodes at once.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd


def get_video_info(video_path: Path) -> dict:
    """Get video width, height, duration, and fps using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,r_frame_rate,duration',
        '-of', 'csv=p=0',
        str(video_path)
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        parts = result.stdout.strip().split(',')
        if len(parts) >= 3:
            width = int(parts[0])
            height = int(parts[1])
            fps_str = parts[2]
            # Parse fps (e.g., "30/1" -> 30.0)
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                fps = num / den if den > 0 else 30.0
            else:
                fps = float(fps_str)
            
            duration = float(parts[3]) if len(parts) > 3 and parts[3] else None
            
            return {
                'width': width,
                'height': height,
                'fps': fps,
                'duration': duration
            }
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        print(f"Warning: Could not get video info for {video_path}: {e}")
        return {'width': 320, 'height': 240, 'fps': 20.0, 'duration': None}
    
    return {'width': 320, 'height': 240, 'fps': 20.0, 'duration': None}


def combine_three_views(
    front_video: Path,
    side_video: Path,
    top_video: Path,
    output_video: Path,
    layout: str = 'horizontal'
) -> bool:
    """
    Combine three camera views into a single video.
    
    Args:
        front_video: Path to front camera video
        side_video: Path to side camera video
        top_video: Path to top camera video
        output_video: Path to output combined video
        layout: 'horizontal' (side-by-side) or 'grid' (2x2 with one empty)
    """
    output_video.parent.mkdir(parents=True, exist_ok=True)
    
    # Get video info to determine dimensions
    front_info = get_video_info(front_video)
    side_info = get_video_info(side_video)
    top_info = get_video_info(top_video)
    
    # Use the first available dimensions
    w = front_info.get('width', 320)
    h = front_info.get('height', 240)
    fps = front_info.get('fps', 20.0)
    
    if layout == 'horizontal':
        # Side-by-side: [side | top | front]
        output_width = w * 3
        output_height = h
        
        filter_complex = (
            f"[0:v]scale={w}:{h}[side];"
            f"[1:v]scale={w}:{h}[top];"
            f"[2:v]scale={w}:{h}[front];"
            f"[side][top][front]hstack=inputs=3"
        )
    else:  # grid layout
        # 2x2 grid: top-left=side, top-right=top, bottom-left=front, bottom-right=black
        output_width = w * 2
        output_height = h * 2
        
        filter_complex = (
            f"[0:v]scale={w}:{h}[side];"
            f"[1:v]scale={w}:{h}[top];"
            f"[2:v]scale={w}:{h}[front];"
            f"color=c=black:s={w}x{h}[black];"
            f"[side][top][front][black]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0"
        )
    
    cmd = [
        'ffmpeg',
        '-i', str(side_video),
        '-i', str(top_video),
        '-i', str(front_video),
        '-filter_complex', filter_complex,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-y',
        str(output_video)
    ]
    
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return output_video.exists() and output_video.stat().st_size > 0
    except subprocess.CalledProcessError as e:
        print(f"Error combining views: {e}")
        if e.stderr:
            print(f"ffmpeg error: {e.stderr.decode()}")
        return False


def create_episode_grid(
    combined_videos: list[Path],
    output_video: Path,
    grid_cols: int = 3,
    grid_rows: int = 3
) -> bool:
    """
    Create a grid video showing multiple episodes at once.
    
    Args:
        combined_videos: List of combined video files (one per episode)
        output_video: Path to output grid video
        grid_cols: Number of columns in grid
        grid_rows: Number of rows in grid
    """
    if not combined_videos:
        print("Error: No videos to combine")
        return False
    
    output_video.parent.mkdir(parents=True, exist_ok=True)
    
    # Get dimensions from first video
    first_info = get_video_info(combined_videos[0])
    w = first_info.get('width', 960)
    h = first_info.get('height', 240)
    fps = first_info.get('fps', 20.0)
    
    # Calculate grid dimensions
    grid_width = w * grid_cols
    grid_height = h * grid_rows
    
    # Pad videos list to fill grid (use last video to fill empty slots)
    total_slots = grid_cols * grid_rows
    if len(combined_videos) < total_slots:
        # Repeat last video to fill grid
        last_video = combined_videos[-1]
        combined_videos = list(combined_videos) + [last_video] * (total_slots - len(combined_videos))
    else:
        combined_videos = combined_videos[:total_slots]
    
    # Build filter complex for xstack grid
    inputs = []
    layout_parts = []
    
    for idx, video in enumerate(combined_videos):
        row = idx // grid_cols
        col = idx % grid_cols
        x_pos = col * w
        y_pos = row * h
        
        inputs.append(f"-i {video}")
        layout_parts.append(f"{x_pos}_{y_pos}")
    
    layout_str = "|".join(layout_parts)
    
    # Create black background
    filter_complex = f"color=c=black:s={grid_width}x{grid_height}[bg];"
    
    # Scale all inputs
    for idx in range(len(combined_videos)):
        filter_complex += f"[{idx}:v]scale={w}:{h}[v{idx}];"
    
    # Stack all videos
    filter_complex += f"[bg]"
    for idx in range(len(combined_videos)):
        filter_complex += f"[v{idx}]"
    filter_complex += f"xstack=inputs={len(combined_videos) + 1}:layout={layout_str}"
    
    cmd = [
        'ffmpeg',
        *[arg for video in combined_videos for arg in ['-i', str(video)]],
        '-filter_complex', filter_complex,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-t', '10',  # Limit to 10 seconds per grid view
        '-y',
        str(output_video)
    ]
    
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return output_video.exists() and output_video.stat().st_size > 0
    except subprocess.CalledProcessError as e:
        print(f"Error creating grid: {e}")
        if e.stderr:
            print(f"ffmpeg error: {e.stderr.decode()}")
        return False


def find_episode_clips(clips_dir: Path, episode_idx: int) -> dict:
    """Find clips for a specific episode from all three cameras."""
    cameras = ['front', 'side', 'top']
    clips = {}
    
    for camera in cameras:
        camera_dir = clips_dir / camera
        clip_file = camera_dir / f"episode_{episode_idx:03d}.mp4"
        if clip_file.exists():
            clips[camera] = clip_file
        else:
            clips[camera] = None
    
    return clips


def main():
    parser = argparse.ArgumentParser(
        description="Create grid view video showing all clips with combined camera views"
    )
    parser.add_argument(
        "clips_dir",
        type=Path,
        help="Path to clips directory containing front/, side/, top/ subdirectories"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output video file (default: clips_dir/grid_view.mp4)"
    )
    parser.add_argument(
        "--layout",
        type=str,
        choices=['horizontal', 'grid'],
        default='horizontal',
        help="Layout for combining three views: 'horizontal' (side-by-side) or 'grid' (2x2)"
    )
    parser.add_argument(
        "--grid-cols",
        type=int,
        default=3,
        help="Number of columns in final grid (default: 3)"
    )
    parser.add_argument(
        "--grid-rows",
        type=int,
        default=3,
        help="Number of rows in final grid (default: 3)"
    )
    parser.add_argument(
        "--max-episodes",
        type=int,
        default=None,
        help="Maximum number of episodes to include (default: all)"
    )
    
    args = parser.parse_args()
    
    if not args.clips_dir.exists():
        print(f"Error: Clips directory not found: {args.clips_dir}")
        sys.exit(1)
    
    # Find all available episodes
    cameras = ['front', 'side', 'top']
    episode_indices = set()
    
    for camera in cameras:
        camera_dir = args.clips_dir / camera
        if camera_dir.exists():
            for clip_file in camera_dir.glob("episode_*.mp4"):
                # Extract episode index from filename
                try:
                    idx = int(clip_file.stem.split('_')[1])
                    episode_indices.add(idx)
                except (ValueError, IndexError):
                    continue
    
    if not episode_indices:
        print(f"Error: No episode clips found in {args.clips_dir}")
        sys.exit(1)
    
    episode_indices = sorted(episode_indices)
    if args.max_episodes:
        episode_indices = episode_indices[:args.max_episodes]
    
    print(f"Found {len(episode_indices)} episodes")
    print(f"Episodes: {episode_indices[0]} to {episode_indices[-1]}")
    
    # Create temporary directory for combined videos
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        combined_videos = []
        
        print(f"\nCombining three views for each episode...")
        for ep_idx in episode_indices:
            clips = find_episode_clips(args.clips_dir, ep_idx)
            
            # Check if we have all three views
            if not all(clips.values()):
                missing = [cam for cam, path in clips.items() if path is None]
                print(f"  Episode {ep_idx:03d}: Missing views {missing}, skipping")
                continue
            
            combined_video = temp_path / f"combined_episode_{ep_idx:03d}.mp4"
            print(f"  Episode {ep_idx:03d}: Combining {clips['side'].name}, {clips['top'].name}, {clips['front'].name}...")
            
            success = combine_three_views(
                clips['front'],
                clips['side'],
                clips['top'],
                combined_video,
                layout=args.layout
            )
            
            if success:
                combined_videos.append(combined_video)
                print(f"    ✓ Created combined video")
            else:
                print(f"    ✗ Failed to combine views")
        
        if not combined_videos:
            print("Error: No combined videos created")
            sys.exit(1)
        
        print(f"\nCreated {len(combined_videos)} combined videos")
        
        # Create final grid video
        if args.output:
            output_video = args.output
        else:
            output_video = args.clips_dir / "grid_view.mp4"
        
        print(f"\nCreating grid view with {args.grid_cols}x{args.grid_rows} layout...")
        print(f"Output: {output_video}")
        
        success = create_episode_grid(
            combined_videos,
            output_video,
            grid_cols=args.grid_cols,
            grid_rows=args.grid_rows
        )
        
        if success:
            print(f"\n✓ Grid view created successfully: {output_video}")
        else:
            print(f"\n✗ Failed to create grid view")
            sys.exit(1)


if __name__ == "__main__":
    main()

