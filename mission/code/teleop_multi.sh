#!/bin/bash

# Set permissions for USB devices (try without sudo first, fallback to sudo if needed)
set_device_permissions() {
    local device=$1
    if [ -e "$device" ]; then
        # Try without sudo first (works if udev rules are set up)
        chmod 666 "$device" 2>/dev/null || sudo chmod 666 "$device" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "Warning: Could not set permissions for $device"
        fi
    fi
}

set_device_permissions /dev/ttyACM0
set_device_permissions /dev/ttyACM1

# Fixed port assignments
LEADER_PORT="/dev/ttyACM0"
FOLLOWER_PORT="/dev/ttyACM1"

# Fixed arm names
LEADER_NAME="versag_leader_arm"
FOLLOWER_NAME="versag_follower_arm"

# Function to detect and validate cameras
detect_and_validate_cameras() {
    echo ""
    echo "Detecting cameras and capturing test images..."
    echo "=========================================="
    
    # Clean images folder before running camera detection
    local images_dir="$(pwd)/outputs/captured_images"
    if [ -d "$images_dir" ]; then
        echo "Cleaning previous images..."
        rm -rf "$images_dir"/*
        echo "✓ Cleaned images folder"
    else
        mkdir -p "$images_dir"
    fi
    
    # Run camera detection and capture output
    local camera_output=$(lerobot-find-cameras opencv 2>&1)
    echo "$camera_output"
    
    # Count cameras by looking for "Camera #" pattern
    local camera_count=$(echo "$camera_output" | grep -c "Camera #" || echo "0")
    
    if [ "$camera_count" -ne 3 ]; then
        echo ""
        echo "=========================================="
        echo "ERROR: Expected exactly 3 cameras, but found $camera_count"
        echo "=========================================="
        echo ""
        echo "Please check your camera connections:"
        echo "  - Ensure all 3 cameras are properly connected via USB"
        echo "  - Check that cameras are powered on"
        echo "  - Try unplugging and reconnecting the cameras"
        echo "  - Verify cameras are not being used by another application"
        echo ""
        exit 1
    fi
    
    echo ""
    echo "✓ Found exactly 3 cameras"
    echo "Images saved to: $images_dir"
    echo ""
    echo "Opening images for viewing..."
    
    # Wait a moment for images to finish saving
    sleep 2
    
    # Find and open all image files in the directory
    if [ -d "$images_dir" ]; then
        # Find image files (jpg, jpeg, png, etc.)
        local image_files=($(find "$images_dir" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.bmp" \) | sort))
        
        if [ ${#image_files[@]} -gt 0 ]; then
            # Open images with image viewer (eog, xdg-open, or feh)
            for img in "${image_files[@]}"; do
                eog "$img" 2>/dev/null &
                sleep 0.5
            done
            
            # If eog didn't work, try xdg-open
            if ! pgrep -x "eog" > /dev/null; then
                for img in "${image_files[@]}"; do
                    xdg-open "$img" 2>/dev/null &
                    sleep 0.5
                done
            fi
        else
            echo "Warning: No image files found in $images_dir"
        fi
    else
        echo "Warning: Images directory not found at $images_dir"
    fi
    
    echo ""
    echo "Please check the displayed images to identify which camera is 'top', 'side', and 'front'"
    echo ""
}

# Camera cache file
CAMERA_CACHE_FILE=".camera_cache"

# Function to save camera IDs to cache
save_camera_cache() {
    local top=$1
    local side=$2
    local front=$3
    echo "top=$top" > "$CAMERA_CACHE_FILE"
    echo "side=$side" >> "$CAMERA_CACHE_FILE"
    echo "front=$front" >> "$CAMERA_CACHE_FILE"
}

# Function to load camera IDs from cache
load_camera_cache() {
    if [ -f "$CAMERA_CACHE_FILE" ]; then
        source "$CAMERA_CACHE_FILE"
        if [ -n "$top" ] && [ -n "$side" ] && [ -n "$front" ]; then
            TOP_CAM=$top
            SIDE_CAM=$side
            FRONT_CAM=$front
            return 0
        fi
    fi
    return 1
}

# Function to get camera IDs (with caching)
get_camera_ids() {
    # Check if cache exists
    if load_camera_cache; then
        echo ""
        echo "Found cached camera IDs: top=$TOP_CAM, side=$SIDE_CAM, front=$FRONT_CAM"
        echo ""
        read -p "Do you want to reselect cameras? (y/n): " reselect_choice
        
        if [ "$reselect_choice" != "y" ] && [ "$reselect_choice" != "Y" ]; then
            echo "Using cached camera IDs: top=$TOP_CAM, side=$SIDE_CAM, front=$FRONT_CAM"
            return 0
        fi
    fi
    
    # No cache or user wants to reselect - do full detection
    detect_and_validate_cameras
    read -p "Enter camera IDs as 3 digits (top,side,front, e.g., 023): " camera_input
    
    # Parse and validate
    if [ ${#camera_input} -ne 3 ]; then
        echo "Error: Must provide exactly 3 camera IDs as digits (e.g., 023 for top=0, side=2, front=3)"
        exit 1
    fi
    
    TOP_CAM=${camera_input:0:1}
    SIDE_CAM=${camera_input:1:1}
    FRONT_CAM=${camera_input:2:1}
    
    # Save to cache
    save_camera_cache "$TOP_CAM" "$SIDE_CAM" "$FRONT_CAM"
    echo "✓ Camera IDs saved to cache"
    echo ""
}

# Function to parse camera IDs from digit string (e.g., "02" -> top=0, side=2)
parse_camera_ids() {
    local camera_input=$1
    
    if [ ${#camera_input} -ne 2 ]; then
        echo "Error: Must provide exactly 2 camera IDs as digits (e.g., 02 for top=0, side=2)"
        exit 1
    fi
    
    TOP_CAM=${camera_input:0:1}
    SIDE_CAM=${camera_input:1:1}
}

# Dataset metadata cache file
DATASET_CACHE_FILE=".dataset_cache"
DATA_BASE_DIR="/home/versag/data"
EVALS_BASE_DIR="/home/versag/evals"

# Function to list existing datasets
list_datasets() {
    local datasets=()
    if [ -d "$DATA_BASE_DIR" ]; then
        # Find all directories in data folder
        while IFS= read -r -d '' dir; do
            datasets+=("$(basename "$dir")")
        done < <(find "$DATA_BASE_DIR" -maxdepth 1 -type d ! -path "$DATA_BASE_DIR" -print0 2>/dev/null | sort -z)
    fi
    printf '%s\n' "${datasets[@]}"
}

# Function to load metadata from existing dataset
load_dataset_metadata() {
    local dataset_name=$1
    local dataset_path="$DATA_BASE_DIR/$dataset_name"
    
    if [ ! -d "$dataset_path" ]; then
        return 1
    fi
    
    # Try to load from dataset metadata file if it exists
    if [ -f "$dataset_path/.dataset_metadata" ]; then
        source "$dataset_path/.dataset_metadata"
        return 0
    fi
    
    # Try to infer from dataset structure or config
    # Check for info.json or similar files
    if [ -f "$dataset_path/info.json" ]; then
        # Try to extract metadata from info.json (if jq is available)
        if command -v jq &> /dev/null; then
            dataset_repo=$(jq -r '.repo_id // empty' "$dataset_path/info.json" 2>/dev/null || echo "")
            if [ -n "$dataset_repo" ] && [ "$dataset_repo" != "null" ]; then
                export dataset_repo
                return 0
            fi
        fi
    fi
    
    return 1
}

# Function to save metadata cache
save_metadata_cache() {
    local repo=$1
    local episodes=$2
    local episode_time=$3
    local reset_time=$4
    local task=$5
    local root=$6
    
    cat > "$DATASET_CACHE_FILE" << EOF
dataset_repo="$repo"
num_episodes="$episodes"
episode_time="$episode_time"
reset_time="$reset_time"
task_desc="$task"
dataset_root="$root"
EOF
}

# Function to load metadata cache
load_metadata_cache() {
    if [ -f "$DATASET_CACHE_FILE" ]; then
        source "$DATASET_CACHE_FILE"
        return 0
    fi
    return 1
}

# Function to get dataset configuration
get_dataset_config() {
    # Initialize flag for existing dataset
    USE_EXISTING_DATASET=false
    
    echo ""
    echo "=========================================="
    echo "Dataset Configuration"
    echo "=========================================="
    echo ""
    
    # Ensure data base directory exists
    if [ ! -d "$DATA_BASE_DIR" ]; then
        mkdir -p "$DATA_BASE_DIR"
        echo "Created data directory: $DATA_BASE_DIR"
    fi
    
    # List existing datasets
    local existing_datasets=($(list_datasets))
    
    if [ ${#existing_datasets[@]} -gt 0 ]; then
        echo "Existing datasets in $DATA_BASE_DIR:"
        local idx=1
        for dataset in "${existing_datasets[@]}"; do
            echo "  $idx) $dataset"
            ((idx++))
        done
        echo "  $idx) Create new dataset"
        echo ""
        read -p "Select dataset (1-$idx): " dataset_choice
        
        # Validate choice
        if [ "$dataset_choice" -ge 1 ] && [ "$dataset_choice" -le ${#existing_datasets[@]} ]; then
            # Use existing dataset
            local selected_dataset="${existing_datasets[$((dataset_choice-1))]}"
            dataset_root="$DATA_BASE_DIR/$selected_dataset"
            USE_EXISTING_DATASET=true
            
            echo ""
            echo "Using existing dataset: $selected_dataset"
            echo "Dataset path: $dataset_root"
            
            # Set repo_id to match dataset name
            dataset_repo="versag/$selected_dataset"
            
            # Try to load metadata from dataset
            if load_dataset_metadata "$selected_dataset"; then
                echo "✓ Loaded metadata from existing dataset"
                # Override repo_id with dataset name if it was loaded
                dataset_repo="versag/$selected_dataset"
            else
                # Try to load from cache
                if load_metadata_cache; then
                    echo "✓ Using cached metadata"
                    # Override repo_id with dataset name
                    dataset_repo="versag/$selected_dataset"
                else
                    # Use defaults
                    echo "Using default metadata"
                    dataset_repo="versag/$selected_dataset"
                    num_episodes=60
                    episode_time=20
                    reset_time=10
                    task_desc="pickup the pen and place it"
                fi
            fi
            
            # Always prompt for task description when resuming (can be changed)
            echo ""
            echo "Current task: $task_desc"
            read -p "Enter new task description (or press Enter to keep current): " new_task_desc
            if [ -n "$new_task_desc" ]; then
                task_desc="$new_task_desc"
                echo "✓ Task updated to: $task_desc"
            else
                echo "✓ Keeping current task: $task_desc"
            fi
            
            # Save metadata to cache for future use
            save_metadata_cache "$dataset_repo" "$num_episodes" "$episode_time" "$reset_time" "$task_desc" "$dataset_root"
            
            return 0
        fi
    fi
    
    # Create new dataset or no existing datasets
    echo ""
    echo "Creating new dataset..."
    echo ""
    
    # Ask for dataset name/path first
    read -p "Enter dataset name (will be created in $DATA_BASE_DIR/): " dataset_name
    if [ -z "$dataset_name" ]; then
        dataset_name="pick_pen_dataset"
    fi
    
    # Check for cached metadata for other settings (before setting dataset_root/repo)
    if load_metadata_cache; then
        echo ""
        echo "Found cached metadata:"
        echo "  Episodes: $num_episodes"
        echo "  Episode time: $episode_time"
        echo "  Reset time: $reset_time"
        echo "  Task: $task_desc"
        echo ""
        read -p "Use cached metadata? (y/n): " use_cache
        
        if [ "$use_cache" != "y" ] && [ "$use_cache" != "Y" ]; then
            # Ask for new metadata
            read -p "Enter number of episodes (default: 60): " num_episodes
            num_episodes=${num_episodes:-60}
            read -p "Enter episode time in seconds (default: 20): " episode_time
            episode_time=${episode_time:-20}
            read -p "Enter reset time in seconds (default: 10): " reset_time
            reset_time=${reset_time:-10}
            read -p "Enter task description (default: 'pickup the pen and place it'): " task_desc
            task_desc=${task_desc:-"pickup the pen and place it"}
        fi
    else
        # No cache, ask for metadata
        read -p "Enter number of episodes (default: 60): " num_episodes
        num_episodes=${num_episodes:-60}
        read -p "Enter episode time in seconds (default: 20): " episode_time
        episode_time=${episode_time:-20}
        read -p "Enter reset time in seconds (default: 10): " reset_time
        reset_time=${reset_time:-10}
        read -p "Enter task description (default: 'pickup the pen and place it'): " task_desc
        task_desc=${task_desc:-"pickup the pen and place it"}
    fi
    
    # Set dataset_root and repo_id AFTER loading cache to ensure they match the new dataset name
    dataset_root="$DATA_BASE_DIR/$dataset_name"
    dataset_repo="versag/$dataset_name"
    
    # For new datasets, don't create the directory - let lerobot-record create it
    # Only ensure the parent data directory exists
    if [ ! -d "$DATA_BASE_DIR" ]; then
        mkdir -p "$DATA_BASE_DIR"
    fi
    
    # Check if directory already exists (shouldn't for new datasets)
    if [ -d "$dataset_root" ]; then
        echo ""
        echo "Warning: Dataset directory already exists: $dataset_root"
        echo "This might cause an error. Consider selecting it as an existing dataset instead."
        echo ""
    fi
    
    # Save metadata to cache
    save_metadata_cache "$dataset_repo" "$num_episodes" "$episode_time" "$reset_time" "$task_desc" "$dataset_root"
    echo "✓ Metadata saved to cache"
}

# Function to download model from HuggingFace
download_model_from_hf() {
    local repo_id=$1
    local weights_dir="./weights"
    
    # Ensure weights directory exists
    mkdir -p "$weights_dir"
    
    # Extract model name from repo_id (e.g., versag/model_name -> model_name)
    local model_name=$(basename "$repo_id")
    local model_path="$weights_dir/$model_name"
    
    echo ""
    echo "Downloading model from HuggingFace..."
    echo "  Repo ID: $repo_id"
    echo "  Destination: $model_path"
    echo ""
    
    # Check if huggingface-cli is available
    if ! command -v huggingface-cli &> /dev/null; then
        echo "Error: huggingface-cli not found. Please install it with: pip install huggingface_hub"
        exit 1
    fi
    
    # Download using huggingface-cli
    huggingface-cli download "$repo_id" --local-dir "$model_path" --local-dir-use-symlinks False
    
    if [ $? -eq 0 ]; then
        echo "✓ Model downloaded successfully to: $model_path"
        MODEL_PATH="$model_path"
        return 0
    else
        echo "Error: Failed to download model"
        exit 1
    fi
}

# Function to list and select model from weights folder
get_model_path() {
    local weights_dir="./weights"
    
    # Ensure weights directory exists
    mkdir -p "$weights_dir"
    
    # List available models
    local models=($(find "$weights_dir" -maxdepth 1 -type d ! -path "$weights_dir" -exec basename {} \; | sort))
    
    echo ""
    echo "Available models in $weights_dir:"
    local idx=1
    for model in "${models[@]}"; do
        echo "  $idx) $model"
        ((idx++))
    done
    echo "  $idx) Download from HuggingFace"
    echo ""
    read -p "Select model (1-$idx): " model_choice
    
    # Check if user selected download option
    if [ "$model_choice" -eq $idx ]; then
        # Download from HuggingFace
        read -p "Enter HuggingFace repo ID (e.g., versag/model_name): " hf_repo_id
        if [ -z "$hf_repo_id" ]; then
            echo "Error: Repo ID is required"
            exit 1
        fi
        download_model_from_hf "$hf_repo_id"
    elif [ "$model_choice" -ge 1 ] && [ "$model_choice" -le ${#models[@]} ]; then
        # Select existing model
        local selected_model="${models[$((model_choice-1))]}"
        MODEL_PATH="$weights_dir/$selected_model"
        echo "Selected model: $MODEL_PATH"
    else
        echo "Error: Invalid model selection"
        exit 1
    fi
}

# Main menu - Select action
echo "=========================================="
echo "LeRobot Multi-Arm Control"
echo "=========================================="
echo ""
echo "Select an action:"
echo "1) Calibrate"
echo "2) Teleoperate"
echo "3) Record"
echo "4) Inference"
echo ""
read -p "Enter choice (1-4): " action_choice

case $action_choice in
    1)
        # Calibration menu
        echo ""
        echo "What would you like to calibrate?"
        echo "1) Leader"
        echo "2) Follower"
        echo ""
        read -p "Enter choice (1-2): " calibrate_choice
        
        case $calibrate_choice in
            1)
                echo ""
                echo "Calibrating leader..."
lerobot-calibrate \
    --teleop.type=so101_leader \
                    --teleop.port=$LEADER_PORT \
                    --teleop.id=$LEADER_NAME
                ;;
            2)
                echo ""
                echo "Calibrating follower..."
                lerobot-calibrate \
                    --robot.type=so101_follower \
                    --robot.port=$FOLLOWER_PORT \
                    --robot.id=$FOLLOWER_NAME
                ;;
            *)
                echo "Invalid choice"
                exit 1
                ;;
        esac
        ;;
    2)
        # Teleoperate
        get_camera_ids
        
        echo ""
        echo "Starting teleoperation..."
lerobot-teleoperate \
    --robot.type=so101_follower \
            --robot.port=$FOLLOWER_PORT \
            --robot.id=$FOLLOWER_NAME \
            --robot.cameras="{top: {type: opencv, index_or_path: $TOP_CAM, width: 320, height: 240, fps: 20}, side: {type: opencv, index_or_path: $SIDE_CAM, width: 320, height: 240, fps: 20}, front: {type: opencv, index_or_path: $FRONT_CAM, width: 320, height: 240, fps: 20}}" \
    --teleop.type=so101_leader \
            --teleop.port=$LEADER_PORT \
            --teleop.id=$LEADER_NAME \
    --display_data=true
        ;;
    3)
        # Record
        get_camera_ids
        get_dataset_config
        
        echo ""
        echo "Starting recording with configuration:"
        echo "  Dataset repo: $dataset_repo"
        echo "  Episodes: $num_episodes"
        echo "  Episode time: $episode_time"
        echo "  Reset time: $reset_time"
        echo "  Task: $task_desc"
        echo "  Dataset root: $dataset_root"
        echo "  Resume: $USE_EXISTING_DATASET"
        echo ""
        
        # Build base command
        if [ "$USE_EXISTING_DATASET" = true ]; then
            # Existing dataset - use resume
            lerobot-record \
                --robot.type=so101_follower \
                --robot.port=$FOLLOWER_PORT \
                --robot.id=$FOLLOWER_NAME \
                --robot.cameras="{top: {type: opencv, index_or_path: $TOP_CAM, width: 320, height: 240, fps: 20}, side: {type: opencv, index_or_path: $SIDE_CAM, width: 320, height: 240, fps: 20}, front: {type: opencv, index_or_path: $FRONT_CAM, width: 320, height: 240, fps: 20}}" \
                --teleop.type=so101_leader \
                --teleop.port=$LEADER_PORT \
                --teleop.id=$LEADER_NAME \
                --display_data=false \
                --dataset.repo_id=$dataset_repo \
                --dataset.num_episodes=$num_episodes \
                --dataset.episode_time_s=$episode_time \
                --dataset.reset_time_s=$reset_time \
                --dataset.single_task="$task_desc" \
                --dataset.root=$dataset_root \
                --resume=true
        else
            # New dataset - no resume
            lerobot-record \
                --robot.type=so101_follower \
                --robot.port=$FOLLOWER_PORT \
                --robot.id=$FOLLOWER_NAME \
                --robot.cameras="{top: {type: opencv, index_or_path: $TOP_CAM, width: 320, height: 240, fps: 20}, side: {type: opencv, index_or_path: $SIDE_CAM, width: 320, height: 240, fps: 20}, front: {type: opencv, index_or_path: $FRONT_CAM, width: 320, height: 240, fps: 20}}" \
    --teleop.type=so101_leader \
                --teleop.port=$LEADER_PORT \
                --teleop.id=$LEADER_NAME \
                --display_data=false \
                --dataset.repo_id=$dataset_repo \
                --dataset.num_episodes=$num_episodes \
                --dataset.episode_time_s=$episode_time \
                --dataset.reset_time_s=$reset_time \
                --dataset.single_task="$task_desc" \
                --dataset.root=$dataset_root
        fi
        ;;
    4)
        # Inference
        get_camera_ids
        get_model_path
        
        # Get inference dataset configuration
        echo ""
        read -p "Enter task description (default: 'inference task'): " inference_task
        inference_task=${inference_task:-"inference task"}
        read -p "Enter episode time in seconds (default: 20): " inference_episode_time
        inference_episode_time=${inference_episode_time:-20}
        
        # Use model name for dataset name with datetime suffix to avoid conflicts
        model_name=$(basename "$MODEL_PATH")
        datetime_suffix=$(date +"%Y%m%d_%H%M%S")
        inference_dataset_name="eval_${model_name}_${datetime_suffix}"
        
        # Ensure evals directory exists
        if [ ! -d "$EVALS_BASE_DIR" ]; then
            mkdir -p "$EVALS_BASE_DIR"
        fi
        
        inference_dataset_root="$EVALS_BASE_DIR/$inference_dataset_name"
        inference_repo_id="versag/$inference_dataset_name"
        
        echo ""
        echo "Starting inference with model: $MODEL_PATH"
        echo "  Task: $inference_task"
        echo "  Episode time: $inference_episode_time"
        echo "  Dataset root: $inference_dataset_root"
        echo "  Repo ID: $inference_repo_id"
        echo ""
        
        # Check if model is smolvla (expects camera1, camera2, camera3)
        # For smolvla models, we need rename_map to map side/top/front to camera1/camera2/camera3
        if [[ "$model_name" == *"smolvla"* ]]; then
            echo "Detected smolvla model - applying camera rename mapping"
            lerobot-record \
                --robot.type=so101_follower \
                --robot.port=$FOLLOWER_PORT \
                --robot.id=$FOLLOWER_NAME \
                --robot.cameras="{top: {type: opencv, index_or_path: $TOP_CAM, width: 320, height: 240, fps: 20}, side: {type: opencv, index_or_path: $SIDE_CAM, width: 320, height: 240, fps: 20}, front: {type: opencv, index_or_path: $FRONT_CAM, width: 320, height: 240, fps: 20}}" \
                --policy.path=$MODEL_PATH \
                --dataset.rename_map='{"observation.images.top": "observation.images.camera1", "observation.images.side": "observation.images.camera2", "observation.images.front": "observation.images.camera3"}' \
                --dataset.single_task="$inference_task" \
                --dataset.repo_id=$inference_repo_id \
                --dataset.root=$inference_dataset_root \
                --dataset.episode_time_s=$inference_episode_time \
                --dataset.num_episodes=1 \
                --dataset.push_to_hub=false \
                --display_data=true
        else
lerobot-record \
    --robot.type=so101_follower \
                --robot.port=$FOLLOWER_PORT \
                --robot.id=$FOLLOWER_NAME \
                --robot.cameras="{top: {type: opencv, index_or_path: $TOP_CAM, width: 320, height: 240, fps: 20}, side: {type: opencv, index_or_path: $SIDE_CAM, width: 320, height: 240, fps: 20}, front: {type: opencv, index_or_path: $FRONT_CAM, width: 320, height: 240, fps: 20}}" \
                --policy.path=$MODEL_PATH \
                --dataset.single_task="$inference_task" \
                --dataset.repo_id=$inference_repo_id \
                --dataset.root=$inference_dataset_root \
                --dataset.episode_time_s=$inference_episode_time \
                --dataset.num_episodes=1 \
                --dataset.push_to_hub=false \
                --display_data=true
        fi
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
