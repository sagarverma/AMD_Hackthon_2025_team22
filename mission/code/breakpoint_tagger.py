#!/usr/bin/env python3
"""
Simple breakpoint tagger - just click to mark timestamps.
"""

import argparse
import json
import sys
from pathlib import Path

import cv2


class BreakpointTagger:
    def __init__(self, video_path: Path, output_json: Path):
        self.video_path = video_path
        self.output_json = output_json
        self.cap = None
        self.breakpoints = []  # List of timestamps
        
    def run(self):
        """Main tagging loop."""
        self.cap = cv2.VideoCapture(str(self.video_path))
        
        if not self.cap.isOpened():
            print(f"Error: Could not open video {self.video_path}")
            sys.exit(1)
        
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        print("\n" + "="*60)
        print("Breakpoint Tagger")
        print("="*60)
        print(f"Video: {self.video_path.name}")
        print(f"Duration: {duration:.2f} seconds")
        print("\nControls:")
        print("  SPACE - Pause/Resume")
        print("  'b'   - Mark breakpoint (click to save timestamp)")
        print("  'r'   - Rewind 5 seconds")
        print("  'f'   - Forward 5 seconds")
        print("  'd'   - Delete last breakpoint")
        print("  'q'   - Quit and save")
        print("="*60 + "\n")
        
        window_name = "Breakpoint Tagger - Press 'q' to quit"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        
        frame_delay = int(1000 / fps) if fps > 0 else 33
        paused = False
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                # Loop back to start
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            current_time = current_frame / fps if fps > 0 else 0
            
            # Draw overlay
            # overlay = frame.copy()
            # cv2.rectangle(overlay, (10, 10), (500, 150), (0, 0, 0), -1)
            # cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            
            # Display current time
            # time_str = f"Time: {current_time:.2f}s / {duration:.2f}s"
            # cv2.putText(frame, time_str, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display breakpoint count
            # bp_count = f"Breakpoints: {len(self.breakpoints)}"
            # cv2.putText(frame, bp_count, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # Display status
            # status = "PAUSED" if paused else "Playing"
            # cv2.putText(frame, status, (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            # Show breakpoints on timeline
            if self.breakpoints:
                last_bp = self.breakpoints[-1]
                if abs(current_time - last_bp) < 0.5:  # Highlight if near breakpoint
                    cv2.circle(frame, (640, 50), 20, (0, 255, 0), -1)
            
            cv2.imshow(window_name, frame)
            
            # Handle keyboard input
            key = cv2.waitKey(frame_delay if not paused else 1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord(' '):  # Space - pause/resume
                paused = not paused
            elif key == ord('b'):  # Mark breakpoint
                self.breakpoints.append(current_time)
                self.breakpoints.sort()  # Keep sorted
                print(f"  → Breakpoint {len(self.breakpoints)}: {current_time:.2f}s")
            elif key == ord('r'):  # Rewind 5 seconds
                new_frame = max(0, current_frame - int(5 * fps))
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            elif key == ord('f'):  # Forward 5 seconds
                new_frame = min(total_frames - 1, current_frame + int(5 * fps))
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            elif key == ord('d'):  # Delete last breakpoint
                if self.breakpoints:
                    removed = self.breakpoints.pop()
                    print(f"  → Removed breakpoint: {removed:.2f}s")
                else:
                    print("  No breakpoints to remove")
        
        self.cap.release()
        cv2.destroyAllWindows()
        
        # Save breakpoints
        self.save_breakpoints()
    
    def save_breakpoints(self):
        """Save breakpoints to JSON file."""
        if not self.breakpoints:
            print("\nNo breakpoints marked. JSON not created.")
            return
        
        self.output_json.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'video_path': str(self.video_path),
            'breakpoints': sorted(self.breakpoints)
        }
        
        with open(self.output_json, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✓ Saved {len(self.breakpoints)} breakpoints to {self.output_json}")
        print("\nBreakpoints:")
        for i, bp in enumerate(self.breakpoints, 1):
            print(f"  {i}. {bp:.2f}s")


def main():
    parser = argparse.ArgumentParser(
        description="Mark breakpoints in video (simple click-to-save)"
    )
    parser.add_argument(
        "video",
        type=Path,
        help="Path to video file"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("breakpoints.json"),
        help="Output JSON file (default: breakpoints.json)"
    )
    
    args = parser.parse_args()
    
    if not args.video.exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)
    
    tagger = BreakpointTagger(args.video, args.output)
    tagger.run()


if __name__ == "__main__":
    main()

