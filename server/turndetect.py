#!/usr/bin/env python3
import sys
import pandas as pd
import math
import numpy as np

def calculate_bearing(lat1, lon1, lat2, lon2):

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dLon = lon2 - lon1
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dLon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360

def detect_turns(gps_df, speed_threshold=0.1, turn_threshold=30, smoothing_window=3):

    # Debug: show some information about the loaded data
    print("Full GPS data loaded:")
    print(gps_df.head())
    print("Total rows in CSV:", len(gps_df))
    
    # Filter segments where the vehicle is moving
    moving_df = gps_df[gps_df['avg_speed_mps'] > speed_threshold].reset_index(drop=True)
    print("\nRows above speed threshold ({} m/s): {}".format(speed_threshold, len(moving_df)))
    if len(moving_df) < 2:
        print("Not enough moving segments to calculate bearings.")
        return []
    
    # Record the starting time of the video from the first timestamp
    video_start = moving_df.loc[0, 'start_offsetMs']
    print("Video start offset (ms):", video_start)
    
    # bearings for each consecutive pair of moving segments using their starting positions
    bearings = []
    for i in range(len(moving_df) - 1):
        lat1 = moving_df.loc[i, 'latitude']
        lon1 = moving_df.loc[i, 'longitude']
        lat2 = moving_df.loc[i+1, 'latitude']
        lon2 = moving_df.loc[i+1, 'longitude']
        b = calculate_bearing(lat1, lon1, lat2, lon2)
        bearings.append(b)
    print("\nComputed bearings:")
    print(bearings)
    
    # Create a DataFrame for bearings and apply a circular smoothing using a rolling window
    bearings_df = pd.DataFrame({'bearing': bearings})
    bearings_df['rad'] = np.deg2rad(bearings_df['bearing'])
    bearings_df['sin'] = np.sin(bearings_df['rad'])
    bearings_df['cos'] = np.cos(bearings_df['rad'])
    bearings_df['sin_smooth'] = bearings_df['sin'].rolling(window=smoothing_window, min_periods=1, center=True).mean()
    bearings_df['cos_smooth'] = bearings_df['cos'].rolling(window=smoothing_window, min_periods=1, center=True).mean()
    bearings_df['smoothed_bearing'] = np.degrees(np.arctan2(bearings_df['sin_smooth'], bearings_df['cos_smooth'])) % 360
    print("\nSmoothed bearings:")
    print(bearings_df['smoothed_bearing'].tolist())
    
    events = []
    # change in smoothed bearing between consecutive segments
    print("\nBearing differences:")
    for i in range(len(bearings_df) - 1):
        b1 = bearings_df.loc[i, 'smoothed_bearing']
        b2 = bearings_df.loc[i+1, 'smoothed_bearing']
        # Calculate the signed difference in the range -180 to 180
        diff = (b2 - b1 + 540) % 360 - 180
        print("Index {}: b1={:.2f}, b2={:.2f}, diff={:.2f}".format(i, b1, b2, diff))
        if abs(diff) >= turn_threshold:
            # use the midpoint between the segments to better approximate the turn time.
            if i + 2 < len(moving_df):
                event_time = (moving_df.loc[i+1, 'start_offsetMs'] + moving_df.loc[i+2, 'start_offsetMs']) / 2
            else:
                event_time = moving_df.loc[i+1, 'start_offsetMs']
            # Calculate the video time offset relative to the first timestamp
            video_time_offset = event_time - video_start
            events.append({
                "video_time_offset": video_time_offset,
                "turn_type": "left" if diff < 0 else "right",
                "turn_angle": round(diff, 2)
            })
    return events

def merge_events(events, merge_threshold_ms=1000):
 
    if not events:
        return []
    
    # Sort events by their time offset.
    events_sorted = sorted(events, key=lambda x: x["video_time_offset"])
    merged = []
    # Start with the first event as the current group
    current_group = [events_sorted[0]]
    
    for event in events_sorted[1:]:
        # If the gap between this event and the last event in the group is within the threshold, add it to the group.
        if event["video_time_offset"] - current_group[-1]["video_time_offset"] <= merge_threshold_ms:
            current_group.append(event)
        else:
            merged.append(merge_group(current_group))
            current_group = [event]
    # Merge the final group.
    if current_group:
        merged.append(merge_group(current_group))
    return merged

def merge_group(group):

    avg_offset = sum(e["video_time_offset"] for e in group) / len(group)
    avg_angle = sum(e["turn_angle"] for e in group) / len(group)
    # Take the turn type from the first event 
    turn_type = group[0]["turn_type"]
    return {
        "video_time_offset": round(avg_offset, 2),
        "turn_type": turn_type,
        "turn_angle": round(avg_angle, 2)
    }

if __name__ == "__main__":
    # Load the GPS summary data
    try:
        gps_df = pd.read_csv("gps_time_periods.csv")
    except Exception as e:
        print("Error loading CSV file:", e)
        sys.exit(1)
    
    # Parameters for detection 
    speed_threshold = 0.01     # m/s
    turn_threshold = 20        # degrees
    smoothing_window = 2       # smoothing window for bearings
    
    # Detect turn events
    events = detect_turns(gps_df, speed_threshold=speed_threshold, turn_threshold=turn_threshold, smoothing_window=smoothing_window)
    
    if events:
        print("\nRaw detected events:")
        for e in events:
            print(e)
        
        # Merge events occurring within 1000 ms of each other.
        merged_events = merge_events(events, merge_threshold_ms=1000)
        print("\nMerged events:")
        for e in merged_events:
            # Convert ms to seconds for display if desired:
            seconds = e["video_time_offset"] / 1000
            print(f"Time: {e['video_time_offset']} ms (~{seconds:.2f} s), Type: {e['turn_type']}, Angle: {e['turn_angle']}°")
        
        # Save merged events to CSV
        events_df = pd.DataFrame(merged_events)
        events_df.to_csv("detected_turns.csv", index=False)
        print("\nCSV file 'detected_turns.csv' has been created.")
    else:
        # still write an empty CSV so a stale file from a previous run is never picked up
        pd.DataFrame(columns=["video_time_offset", "turn_type", "turn_angle"]).to_csv("detected_turns.csv", index=False)
        print("\nNo turn events detected.")
