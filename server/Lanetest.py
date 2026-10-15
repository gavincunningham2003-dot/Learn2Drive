#!/usr/bin/env python3
import cv2
import numpy as np
import pandas as pd

def load_turn_times(csv_path):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"CSV file '{csv_path}' not found.")  #return error if empty
        return []
    
    if "video_time_offset" in df.columns:
        turn_times = list(df["video_time_offset"] / 1000.0)
    elif "Time" in df.columns:
        turn_times = list(df["Time"])
    else:
        print(f"CSV file '{csv_path}' does not have 'video_time_offset' or 'Time' column.")
        turn_times = []
    return turn_times

def is_in_turn_window(current_time, turn_times, buffer=7):      #set time for when not to scheck lane location due to turning
    for t in turn_times:
        if t - buffer <= current_time <= t + buffer:
            return True
    return False

def apply_roi(frame, roi_polygon):
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [roi_polygon], 255)
    return cv2.bitwise_and(frame, frame, mask=mask)

def detect_car_dnn(frame, net, conf_threshold=0.5):
    (h, w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), (127.5, 127.5, 127.5))
    net.setInput(blob)
    detections = net.forward()
    
    best_box = None
    best_area = 0
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > conf_threshold:
            class_id = int(detections[0, 0, i, 1])
            if class_id == 7:  # "car" class in MobileNetSSD
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                area = (endX - startX) * (endY - startY)
                if area > best_area:
                    best_area = area
                    best_box = (startX, startY, endX - startX, endY - startY)
    return best_box

def main():
    video_path = "rear_video.mp4"
    turns_csv_path = "detected_turns.csv"
    prototxt_path = "MobileNetSSD_deploy.prototxt"
    model_path = "MobileNetSSD_deploy.caffemodel"
    
    turn_times = load_turn_times(turns_csv_path)
    if turn_times:
        print("Turn times loaded:", turn_times)
    else:
        print("No turn times loaded. Proceeding without turn filtering.")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file '{video_path}'.")
        return
    
    try:
        net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
    except Exception as e:
        print(f"Error loading DNN: {e}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    cv2.namedWindow("Vehicle Detection", cv2.WINDOW_NORMAL)
    
    # For sustained departure:
    not_in_lane_start_time = None
    DEPARTURE_DURATION_THRESHOLD = 2.0
    departure_event_logged = False
    lane_departure_events = []

    roi_polygon = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Rotate frame 90° clockwise.
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        
        height, width = frame.shape[:2]

        # ROI specified
        if roi_polygon is None:
            roi_polygon = np.array([
            [int(0.25 * width), int(0.40 * height)],
            [int(0.75 * width), int(0.40 * height)], 
            [int(0.90 * width), int(0.60 * height)], 
            [int(0.10 * width), int(0.60 * height)]   
        ])

        cv2.polylines(frame, [roi_polygon], True, (255, 255, 0), 2)
        frame_roi = apply_roi(frame, roi_polygon)
        
        current_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
        current_time = current_frame / fps

        if turn_times and is_in_turn_window(current_time, turn_times, buffer=7):
            cv2.putText(frame, "Turn Window - Skipping Detection", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            not_in_lane_start_time = None
            departure_event_logged = False
        else:
            detection = detect_car_dnn(frame_roi, net, conf_threshold=0.5)
            if detection is not None:
                (x, y, w_box, h_box) = detection
                # Draw bounding box in the original frame coordinates.
                cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), (0, 255, 0), 2)
                car_center = x + w_box / 2
                frame_center = width / 2
                offset = frame_center - car_center
                threshold = 0.1 * width
                new_status = "In Lane" if abs(offset) < threshold else "Not in Lane"
                cv2.putText(frame, new_status, (50, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            else:
                new_status = "Not in Lane"
                cv2.putText(frame, "No car detected", (50, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            # If "Not in Lane," start or maintain the timer.
            if new_status == "Not in Lane":
                if not_in_lane_start_time is None:   # "is None" because a start time of 0.0 is valid
                    not_in_lane_start_time = current_time
                    departure_event_logged = False
                else:
                    duration = current_time - not_in_lane_start_time
                    if duration >= DEPARTURE_DURATION_THRESHOLD and not departure_event_logged:
                        print(f"[EVENT] Car left from behind at time {current_time:.2f}s (sustained {duration:.2f}s)")
                        lane_departure_events.append(current_time)
                        departure_event_logged = True
            else:
                # Reset if we go back to "In Lane"
                not_in_lane_start_time = None
                departure_event_logged = False


        cv2.putText(frame, f"Time: {current_time:.2f}s", (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
        
        cv2.imshow("Vehicle Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    
    # always write the file (even when empty) so a stale result from a previous run is never reused
    df_events = pd.DataFrame(lane_departure_events, columns=["Departure_Time"])
    df_events.to_csv("departure_events.csv", index=False)
    if lane_departure_events:
        print("[INFO] Departure events saved to 'departure_events.csv'.")
    else:
        print("[INFO] No departure events detected.")

if __name__ == "__main__":
    main()
