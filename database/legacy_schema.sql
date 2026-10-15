
DROP TABLE IF EXISTS gps_logs, faults, fault_types, movements, clips, drive_sessions, routes CASCADE;

-- Route Table
CREATE TABLE routes (
    route_id SERIAL PRIMARY KEY,
    test_centre TEXT NOT NULL,
    route_name TEXT NOT NULL
);

-- Drive Sessions Table
CREATE TABLE drive_sessions (
    drive_id SERIAL PRIMARY KEY,
    route_id INT REFERENCES routes(route_id),
    start_timestamp TIMESTAMP,
    end_timestamp TIMESTAMP
);

-- Movement Table 
CREATE TABLE movements (
    movement_id SERIAL PRIMARY KEY,
    movement_name TEXT UNIQUE NOT NULL,
    movement_description TEXT
);

-- Fault Type Table
CREATE TABLE fault_types (
    fault_type_id SERIAL PRIMARY KEY,
    fault_type TEXT UNIQUE NOT NULL,
    fault_description TEXT,
    prevention_tips TEXT
);

-- Clip Table
CREATE TABLE clips (
    clip_id SERIAL PRIMARY KEY,
    front_video_name TEXT NOT NULL,
    rear_video_name TEXT,
    clip_time TIME 
);

-- GPS Logs Table (Stores location tracking)
CREATE TABLE gps_logs (
    gps_log_id SERIAL PRIMARY KEY,
    route_id INT REFERENCES routes(route_id),
    drive_id INT REFERENCES drive_sessions(drive_id),
    longitude DECIMAL(10,8) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    gps_timestamp TIMESTAMP 
);

-- Faults Table
CREATE TABLE faults (
    fault_id SERIAL PRIMARY KEY,
    fault_type_id INT REFERENCES fault_types(fault_type_id),
    movement_id INT REFERENCES movements(movement_id),
    route_id INT REFERENCES routes(route_id),
    clip_id INT REFERENCES clips(clip_id),
    gps_log_id INT REFERENCES gps_logs(gps_log_id),
    drive_id INT REFERENCES drive_sessions(drive_id),
    fault_timestamp TIMESTAMP  -- Stores date & time fault occurred
);
