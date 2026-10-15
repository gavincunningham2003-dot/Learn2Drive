#!/usr/bin/env python3
"""Step 4: count observation checks around each turn from the driver-facing video.

For the 15 seconds around every detected turn, MediaPipe Face Mesh tracks the driver's eye
landmarks. The first 30 frames set a "looking straight ahead" baseline; afterwards each frame is
classified as Left / Centre / Right by how far the face has moved from that baseline, and the
number of Centre-to-Left and Centre-to-Right transitions is recorded. Fewer than two looks to a
side is later flagged as an incident.

Set SHOW_PREVIEW=0 in the environment to run without OpenCV preview windows (e.g. on a server).
"""

import cv2
import mediapipe as mp
import statistics
import pandas as pd
import os

SHOW_PREVIEW = os.environ.get("SHOW_PREVIEW", "1") != "0"

def rotate_frame_90_left(frame):
    return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

def estimate_head_offsets(landmarks, image_width, image_height):
    left_eye_outer_idx = 33
    right_eye_outer_idx = 263
    
    left_x = landmarks[left_eye_outer_idx].x * image_width
    left_y = landmarks[left_eye_outer_idx].y * image_height
    
    right_x = landmarks[right_eye_outer_idx].x * image_width
    right_y = landmarks[right_eye_outer_idx].y * image_height
    
    face_center_x = (left_x + right_x) / 2.0
    face_center_y = (left_y + right_y) / 2.0
    
    frame_center_x = image_width / 2.0
    frame_center_y = image_height / 2.0
    
    x_offset = face_center_x - frame_center_x
    y_offset = face_center_y - frame_center_y
    return (x_offset, y_offset)

def classify_direction(relative_offset_x, relative_offset_y,
                       offset_threshold_left=20.0,
                       offset_threshold_right=90.0,
                       pitch_threshold=15.0):

    # 1) Check for left
    if relative_offset_x < -offset_threshold_left:
        return "Left"
    # 2) Check for right
    elif relative_offset_x > offset_threshold_right:
        return "Right"
    else:
        return "Center"

def process_turn_segment(
    video_path,
    start_time,
    end_time,
    offset_threshold_left=20.0,
    offset_threshold_right=80.0,
    pitch_threshold=15.0,
    baseline_frames=30,
    debug=False
):
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Could not open video: {video_path}")
        return (0, 0)
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0
    
    # Clamp times
    start_time = max(0, min(start_time, duration_sec))
    end_time   = max(0, min(end_time,   duration_sec))
    if start_time >= end_time:
        cap.release()
        return (0, 0)
    
    start_frame = int(start_time * fps)
    end_frame   = int(end_time * fps)
    
    # Seek to start frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    # For debugging
    window_name = f"Segment [{start_time:.1f}-{end_time:.1f}]"
    if SHOW_PREVIEW:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    
    # Baseline collections
    x_offsets_for_baseline = []
    y_offsets_for_baseline = []
    baseline_offset_x = None
    baseline_offset_y = None
    
    current_frame = start_frame
    frame_count = 0
    
    # Track how many times we go from "Center" -> "Left" or "Center" -> "Right"
    center_to_left_count = 0
    center_to_right_count = 0
    
    # We'll track the previous state to detect transitions
    last_state = "No face"
    
    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:
        
        while cap.isOpened():
            if current_frame > end_frame:
                break
            
            ret, frame = cap.read()
            if not ret:
                break
            
            rotated_frame = rotate_frame_90_left(frame)
            frame_rgb = cv2.cvtColor(rotated_frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(frame_rgb)
            
            direction_text = "No face"
            new_state = "No face"
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Draw landmarks
                    mp_drawing.draw_landmarks(
                        rotated_frame,
                        face_landmarks,
                        mp_face_mesh.FACEMESH_CONTOURS,
                        mp_drawing.DrawingSpec(color=(0,255,0), thickness=1, circle_radius=1),
                        mp_drawing.DrawingSpec(color=(255,0,0), thickness=1)
                    )
                    
                    h, w, _ = rotated_frame.shape
                    x_offset, y_offset = estimate_head_offsets(face_landmarks.landmark, w, h)
                    
                    if frame_count < baseline_frames:
                        # Collect for baseline
                        x_offsets_for_baseline.append(x_offset)
                        y_offsets_for_baseline.append(y_offset)
                        direction_text = "Collecting baseline..."
                        new_state = "No face"  # Not classifying yet
                    else:
                        # Once baseline is set, classify
                        if baseline_offset_x is None and len(x_offsets_for_baseline) > 0:
                            baseline_offset_x = statistics.median(x_offsets_for_baseline)
                            baseline_offset_y = statistics.median(y_offsets_for_baseline)
                            if debug:
                                print(f"[INFO] Baseline offsets: X={baseline_offset_x:.2f}, Y={baseline_offset_y:.2f} "
                                      f"({start_time:.1f}-{end_time:.1f}s)")
                        
                        if baseline_offset_x is not None:
                            rel_x = x_offset - baseline_offset_x
                            rel_y = y_offset - baseline_offset_y
                            
                            # Classify using our function
                            new_state = classify_direction(
                                rel_x, rel_y,
                                offset_threshold_left,
                                offset_threshold_right,
                                pitch_threshold
                            )
                            direction_text = f"Looking {new_state}"
            
            # Check for transitions from "Center" to "Left"/"Right"
            if last_state == "Center" and new_state == "Left":
                center_to_left_count += 1
            elif last_state == "Center" and new_state == "Right":
                center_to_right_count += 1
            
            # Update last_state
            last_state = new_state if new_state != "No face" else last_state
            
            # Show text on frame
            cv2.putText(rotated_frame,
                        direction_text,
                        (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 0, 255), 2, cv2.LINE_AA)
            
            if SHOW_PREVIEW:
                cv2.imshow(window_name, rotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            frame_count += 1
            current_frame += 1
    
    cap.release()
    if SHOW_PREVIEW:
        cv2.destroyWindow(window_name)
    
    return (center_to_left_count, center_to_right_count)

def process_turns(csv_file, video_path, debug=False):
    """Analyse every turn in csv_file and write the look counts to turn_transitions.csv."""

    if not os.path.exists(csv_file):
        print(f"[ERROR] CSV file not found: {csv_file}")
        return
    
    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found: {video_path}")
        return
    
    df = pd.read_csv(csv_file)
    if "video_time_offset" not in df.columns:
        print(f"[ERROR] 'video_time_offset' column not found in {csv_file}")
        return
    
    if len(df) == 0:
        print(f"[WARNING] CSV file {csv_file} has no rows.")  # still fall through so an empty results file is written
    
    print(f"[INFO] Loaded {len(df)} turn(s) from '{csv_file}'.")
    
    # We'll store results for each turn in a list of dicts
    results = []
    
    for index, row in df.iterrows():
        turn_time_ms = float(row["video_time_offset"])
        turn_time_s = turn_time_ms / 1000.0
        
        # Example: analyze from turn_time_s - 6 to turn_time_s + 9
        start_time = turn_time_s - 6.0
        end_time   = turn_time_s + 9.0
        
        if debug:
            print(f"\n[DEBUG] Turn {index+1}/{len(df)} at {turn_time_s:.2f}s => segment: [{start_time:.2f}, {end_time:.2f}]")
        
        c2l, c2r = process_turn_segment(
            video_path,
            start_time,
            end_time,
            offset_threshold_left=20.0,
            offset_threshold_right=150.0,
            pitch_threshold=15.0,
            baseline_frames=30,
            debug=debug
        )
        
        # Save the result for this turn
        results.append({
            "turn_index": index+1,
            "turn_time_s": turn_time_s,
            "center_to_left": c2l,
            "center_to_right": c2r
        })
    
    # Write out a CSV summarizing all turns (empty if there were none)
    out_df = pd.DataFrame(results, columns=["turn_index", "turn_time_s", "center_to_left", "center_to_right"])
    out_df.to_csv("turn_transitions.csv", index=False)
    print("[INFO] Results saved to 'turn_transitions.csv'.")

def main():
    csv_file = "detected_turns.csv"  # CSV with 'video_time_offset' in ms
    video_path = "front_video.mp4"   # Path to your video
    
    # Enable debug prints for extra info
    process_turns(csv_file, video_path, debug=True)

if __name__ == "__main__":
    main()
