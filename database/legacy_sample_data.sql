INSERT INTO routes (test_centre, route_name) VALUES 
('Test Centre A', 'City Route'), 
('Test Centre B', 'Highway Route'), 
('Test Centre C', 'Suburban Route');

INSERT INTO drive_sessions (route_id, start_timestamp, end_timestamp) VALUES 
(1, '2025-02-17 08:30:00', '2025-02-17 09:15:00'), 
(2, '2025-02-17 10:00:00', '2025-02-17 10:45:00'), 
(3, '2025-02-17 12:00:00', '2025-02-17 12:40:00');

INSERT INTO movements (movement_name, movement_description) VALUES 
('acceleration', 'Increasing the vehicle speed'), 
('driving straight', 'Moving forward without turning'), 
('turning', 'Making a left or right turn at an intersection'), 
('stopping', 'Bringing the vehicle to a complete halt');

INSERT INTO fault_types (fault_type, fault_description, prevention_tips) VALUES 
('Left mirror check miss', 'Driver failed to check the left mirror before turning', 'Always check mirrors before turning.'), 
('Too sharp turn', 'Turn was made too aggressively', 'Slow down and take a controlled turn.'), 
('Too slow', 'Driving significantly below the speed limit', 'Maintain appropriate speed for the road conditions.'), 
('Harsh acceleration', 'Sudden increase in speed', 'Accelerate smoothly and progressively.'), 
('Harsh braking', 'Abrupt deceleration', 'Brake gently and anticipate stops.'), 
('Not in lane', 'Drifting out of lane boundaries', 'Keep the vehicle centered in the lane.');

INSERT INTO clips (front_video_name, rear_video_name, clip_time) VALUES 
('front_video_001.mp4', 'rear_video_001.mp4', '00:05:12'), 
('front_video_002.mp4', 'rear_video_002.mp4', '00:10:34'), 
('front_video_003.mp4', 'rear_video_003.mp4', '00:15:45');

INSERT INTO gps_logs (route_id, drive_id, longitude, latitude, gps_timestamp) VALUES 
(1, 1, 51.5074, -0.1278, '2025-02-17 08:35:00'), 
(1, 1, 51.5075, -0.1279, '2025-02-17 08:40:00'), 
(2, 2, 51.5094, -0.1308, '2025-02-17 10:05:00');

INSERT INTO faults (fault_type_id, movement_id, route_id, clip_id, gps_log_id, drive_id, fault_timestamp) VALUES 
(1, 1, 1, 1, 1, 1, '2025-02-17 08:36:00'), 
(3, 2, 1, 2, 2, 1, '2025-02-17 08:42:00'), 
(5, 4, 2, 3, 3, 2, '2025-02-17 10:10:00');



select * from faults;
