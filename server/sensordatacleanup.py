#!/usr/bin/env python3
import pandas as pd

def process_sensor_data(input_csv="sensor_data.csv", output_csv="gps_time_periods.csv", tol=1e-7):
    # Load sensor data from CSV
    df = pd.read_csv(input_csv)

    # Create a boolean Series that is True when the difference in latitude or longitude exceeds the tolerance
    new_group = (df['latitude'].diff().abs() > tol) | (df['longitude'].diff().abs() > tol)
    df['group'] = new_group.cumsum()

    # Group by contiguous GPS segments and aggregate the time periods, GPS values, and speed
    summary = df.groupby('group').agg(
        start_offsetMs=('offsetMs', 'first'),
        end_offsetMs=('offsetMs', 'last'),
        start_timestamp=('wallClockTimestamp', 'first'),
        end_timestamp=('wallClockTimestamp', 'last'),
        latitude=('latitude', 'first'),
        longitude=('longitude', 'first'),
        avg_speed_mps=('speed', 'mean')
    ).reset_index(drop=True)

    # Convert average speed from m/s to kph
    summary['avg_speed_kph'] = summary['avg_speed_mps'] * 3.6

    # Save the summary to a CSV file
    summary.to_csv(output_csv, index=False)
    print(f"CSV file '{output_csv}' has been created.")

if __name__ == "__main__":
    process_sensor_data()
