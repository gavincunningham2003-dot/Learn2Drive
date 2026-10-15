package com.example.fyp_prototype;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.hardware.camera2.*;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.media.MediaRecorder;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;
import android.util.Log;
import android.util.Size;
import android.view.Surface;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.widget.Toast;

import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileWriter;
import java.io.IOException;
import java.io.OutputStream;
import java.net.Socket;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;

public class StreamingActivity extends AppCompatActivity
        implements SensorEventListener, LocationListener {

    private static final String TAG = "StreamingActivity";

    // Update these with your server details:
    private static final String SERVER_IP = "192.168.0.247"; // Replace with your server IP
    private static final int SERVER_PORT = 5001;

    // Request codes
    private static final int PERMISSION_REQUEST_CODE = 101;

    private CameraDevice frontCameraDevice, rearCameraDevice;
    private CameraCaptureSession frontSession, rearSession;
    private Handler backgroundHandler;      // runs camera work on a background thread
    private HandlerThread backgroundThread;
    private MediaRecorder frontMediaRecorder, rearMediaRecorder;
    private String frontVideoPath, rearVideoPath;
    private boolean isRecording = false;

    private TextView streamingStatus;
    private Button btnStartRecording, btnStopRecording, btnReturnHome, btnSendFiles;

    private SensorManager sensorManager;
    private Sensor accelerometer;
    private float accelerationX, accelerationY, accelerationZ;

    private LocationManager locationManager;
    private double latitude, longitude, speed; // speed in m/s

    private FileWriter csvWriter;
    private File csvFile;
    private long videoStartTimeMillis; // to align CSV data with video

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.streaming);

        streamingStatus = findViewById(R.id.streamingStatus);
        btnStartRecording = findViewById(R.id.btnStartRecording);
        btnStopRecording = findViewById(R.id.btnStopRecording);
        btnSendFiles = findViewById(R.id.btnSendFiles);
        btnReturnHome = findViewById(R.id.btnReturnHome);

        Log.d(TAG, "UI Initialized: Buttons set up.");
        //set buttons
        btnStartRecording.setOnClickListener(v -> {
            Log.d(TAG, "Start Recording button clicked!");
            startCameraStreaming();
            Toast.makeText(StreamingActivity.this, "Driving session being recorded press Stop recording when done driving", Toast.LENGTH_LONG).show();
        });

        btnStopRecording.setOnClickListener(v -> {
            Log.d(TAG," Stop Recording button clicked!");
            stopRecording();
            Toast.makeText(StreamingActivity.this, "Driving session is saved to Generate driving report press Process driving behaviour", Toast.LENGTH_LONG).show();
        });

        btnSendFiles.setOnClickListener(v -> {
            Log.d(TAG, "Send Files button clicked!");
            sendFilesToServer();
            Toast.makeText(StreamingActivity.this, "Processing in progress. Go to View Behaviour on Map to see results.", Toast.LENGTH_LONG).show();
        });

        btnReturnHome.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent intent = new Intent(StreamingActivity.this, MainActivity.class);
                startActivity(intent);
            }
        });


        // Request needed permissions
        requestPermissions();

        // Initialize sensors & location
        initSensors();
        initLocation();
    }

    private void requestPermissions() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED
                || ActivityCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED
                || ActivityCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED
                || ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {

            Log.d(TAG, "Requesting permissions...");
            ActivityCompat.requestPermissions(
                    this,
                    new String[]{
                            Manifest.permission.CAMERA,
                            Manifest.permission.RECORD_AUDIO,
                            Manifest.permission.WRITE_EXTERNAL_STORAGE,
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION
                    },
                    PERMISSION_REQUEST_CODE
            );
        } else {
            Log.d(TAG, "All necessary permissions granted.");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
                                           @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        // Check if permissions are granted
        if (requestCode == PERMISSION_REQUEST_CODE) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }
            if (!allGranted) {
                Log.e(TAG, "Not all permissions granted. Functionality may be limited.");
            } else {
                Log.d(TAG, "Permissions granted by the user.");
            }
        }
    }

    private void initSensors() {
        sensorManager = (SensorManager) getSystemService(SENSOR_SERVICE);
        if (sensorManager != null) {
            accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event.sensor.getType() == Sensor.TYPE_ACCELEROMETER) {
            accelerationX = event.values[0];
            accelerationY = event.values[1];
            accelerationZ = event.values[2];

            // Attempt to log sensor data on each sensor change
            logSensorData();
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        // Not used but must be overridden
    }

    private void initLocation() {
        locationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
        if (locationManager != null) {
            // Request location updates
            if (ActivityCompat.checkSelfPermission(this,
                    Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                locationManager.requestLocationUpdates(
                        LocationManager.GPS_PROVIDER,
                        300,      // minimum time interval between updates
                        0,         // minimum distance between updates
                        this
                );
            }
        }
    }

    @Override
    public void onLocationChanged(@NonNull Location location) {
        latitude = location.getLatitude();
        longitude = location.getLongitude();

        // returns speed in m/s
        speed = location.hasSpeed() ? location.getSpeed() : 0.0;

        // Attempt to log sensor data on location change if needed
        logSensorData();
    }

    @Override
    public void onStatusChanged(String provider, int status, Bundle extras) {
    }

    @Override
    public void onProviderEnabled(@NonNull String provider) {
    }

    @Override
    public void onProviderDisabled(@NonNull String provider) {
    }


    @Override
    protected void onResume() {
        super.onResume();
        if (sensorManager != null && accelerometer != null) {
            sensorManager.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_GAME);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (sensorManager != null) {
            sensorManager.unregisterListener(this);
        }
    }

    private void startCameraStreaming() {
        if (isRecording) {
            Log.w(TAG, "Already recording, skipping duplicate start.");
            return;
        }
        isRecording = true;

        startBackgroundThread();

        // Create and Open CSV file for logging
        openCsvFile();

        try {
            CameraManager cameraManager = (CameraManager) getSystemService(CAMERA_SERVICE);

            // Commonly: 0 = rear, 1 = front. This can vary by device.
            String frontCameraId = cameraManager.getCameraIdList()[1]; // attempt front
            String rearCameraId = cameraManager.getCameraIdList()[0];  // attempt rear

            // Set up the media recorders with both camera IDs
            setupMediaRecorders(frontCameraId, rearCameraId);

            // Open the cameras
            if (ActivityCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                    != PackageManager.PERMISSION_GRANTED) {
                return;
            }
            Log.d(TAG, "Opening Front & Rear Cameras...");
            cameraManager.openCamera(frontCameraId, new CameraStateCallback(true), backgroundHandler);
            cameraManager.openCamera(rearCameraId, new CameraStateCallback(false), backgroundHandler);

        } catch (CameraAccessException e) {
            Log.e(TAG, " CameraAccessException: " + e.getMessage());
        }
    }



    private void setupMediaRecorders(String frontCameraId, String rearCameraId) {
        try {
            // Paths for saving files
            frontVideoPath = getExternalFilesDir(Environment.DIRECTORY_MOVIES) + "/front_video.mp4";
            rearVideoPath  = getExternalFilesDir(Environment.DIRECTORY_MOVIES) + "/rear_video.mp4";

            Log.d(TAG, "Front Video Path: " + frontVideoPath);
            Log.d(TAG, "Rear  Video Path: " + rearVideoPath);

            frontMediaRecorder = new MediaRecorder();
            rearMediaRecorder  = new MediaRecorder();

            // Configure them
            setupFrontRecorder(frontMediaRecorder, frontVideoPath, frontCameraId);
            setupRearRecorder(rearMediaRecorder, rearVideoPath, rearCameraId);

        } catch (Exception e) {
            Log.e(TAG, "Error setting up media recorders: " + e.getMessage());
        }
    }



    private void setupFrontRecorder(MediaRecorder recorder,
                                    String filePath,
                                    String frontCameraId) throws IOException {
        CameraManager cameraManager = (CameraManager) getSystemService(CAMERA_SERVICE);

        try {
            CameraCharacteristics characteristics =
                    cameraManager.getCameraCharacteristics(frontCameraId);

            StreamConfigurationMap map =
                    characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);

            if (map != null) {
                Size[] supportedSizes = map.getOutputSizes(MediaRecorder.class);

                // Pick the largest size by area
                Size largestSize = supportedSizes[0];
                for (Size size : supportedSizes) {
                    long area = (long) size.getWidth() * size.getHeight();
                    long largestArea = (long) largestSize.getWidth() * largestSize.getHeight();
                    if (area > largestArea) {
                        largestSize = size;
                    }
                }

                Log.d(TAG, "Front camera largest size: " +
                        largestSize.getWidth() + "x" + largestSize.getHeight());

                recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
                recorder.setVideoSource(MediaRecorder.VideoSource.SURFACE);
                recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
                recorder.setOutputFile(filePath);
                recorder.setVideoEncoder(MediaRecorder.VideoEncoder.H264);
                recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
                recorder.setVideoFrameRate(30);
                recorder.setVideoSize(largestSize.getWidth(), largestSize.getHeight());
                recorder.setVideoEncodingBitRate(5 * 1000 * 1000);

                recorder.prepare();
                Log.d(TAG, "Front MediaRecorder is ready with largest resolution.");
            }
        } catch (CameraAccessException e) {
            Log.e(TAG, "CameraAccessException in setupFrontRecorder: " + e.getMessage());
        }
    }

    private void setupRearRecorder(MediaRecorder recorder, String filePath, String rearCameraId) throws IOException {
        CameraManager cameraManager = (CameraManager) getSystemService(CAMERA_SERVICE);
        Size widestSize = null;     // selected resolution
        try {
            CameraCharacteristics characteristics =
                    cameraManager.getCameraCharacteristics(rearCameraId);
            StreamConfigurationMap map =
                    characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);

            if (map != null) {
                Size[] supportedSizes = map.getOutputSizes(MediaRecorder.class);
                if (supportedSizes != null && supportedSizes.length > 0) {
                    // Pick the size with the widest aspect ratio (width / height)
                    widestSize = supportedSizes[0];
                    double maxAspectRatio = (double) widestSize.getWidth() / widestSize.getHeight();
                    for (Size size : supportedSizes) {
                        double aspectRatio = (double) size.getWidth() / size.getHeight();
                        if (aspectRatio > maxAspectRatio) {
                            maxAspectRatio = aspectRatio;
                            widestSize = size;
                        }
                    }
                    Log.d(TAG, "Rear camera widest size: " +
                            widestSize.getWidth() + "x" + widestSize.getHeight() +
                            " (Aspect Ratio: " + maxAspectRatio + ")");
                }
            }
        } catch (CameraAccessException e) {
            Log.e(TAG, "CameraAccessException in setupRearRecorder: " + e.getMessage());
        }

        // Configure the recorder
        recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
        recorder.setVideoSource(MediaRecorder.VideoSource.SURFACE);
        recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
        recorder.setOutputFile(filePath);
        recorder.setVideoEncoder(MediaRecorder.VideoEncoder.H264);
        recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
        recorder.setVideoFrameRate(30);
        if (widestSize != null) {
            recorder.setVideoSize(widestSize.getWidth(), widestSize.getHeight());
        } else {
            // fallback resolution if no sizes were found
            recorder.setVideoSize(1920, 1080);
        }
        recorder.setVideoEncodingBitRate(5 * 1000 * 1000);

        // Attempt to prepare with chosen settings
        try {
            recorder.prepare();
            Log.d(TAG, "Rear MediaRecorder set up with chosen resolution.");
        } catch (Exception e) {
            Log.e(TAG, "Rear MediaRecorder failed to prepare with chosen resolution: " + e.getMessage());
            // Fallback to default resolution (e.g., 1920x1080)
            recorder.reset();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            recorder.setVideoSource(MediaRecorder.VideoSource.SURFACE);
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setOutputFile(filePath);
            recorder.setVideoEncoder(MediaRecorder.VideoEncoder.H264);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            recorder.setVideoFrameRate(30);
            recorder.setVideoSize(1920, 1080);
            recorder.setVideoEncodingBitRate(5 * 1000 * 1000);
            recorder.prepare();
            Log.d(TAG, "Rear MediaRecorder set up with fallback resolution 1920x1080.");
        }
    }

    //Receives camera-open events for either front or rear camera
    private class CameraStateCallback extends CameraDevice.StateCallback {
        private final boolean isFront;

        CameraStateCallback(boolean isFront) {
            this.isFront = isFront;
        }

        @Override
        public void onOpened(@NonNull CameraDevice camera) {
            if (isFront) {
                frontCameraDevice = camera;
                Log.d(TAG, "Front Camera Opened!");
            } else {
                rearCameraDevice = camera;
                Log.d(TAG, "Rear Camera Opened!");
            }
            createCameraCaptureSession(camera, isFront);     // Proceed to create a recording session on the opened camera.
        }

        @Override
        public void onDisconnected(@NonNull CameraDevice camera) {
            Log.e(TAG, "Camera Disconnected!");
            camera.close();
        }

        @Override
        public void onError(@NonNull CameraDevice camera, int error) {
            Log.e(TAG, "Camera Failed " + error);
            camera.close();
        }
    }

    private void createCameraCaptureSession(CameraDevice camera, boolean isFront) {
        try {
            Surface surface;
            try {
                surface = isFront ? frontMediaRecorder.getSurface() : rearMediaRecorder.getSurface();
            } catch (IllegalStateException e) {
                Log.e(TAG, "Failed to get recorder surface: " + e.getMessage());
                return;
            }
            camera.createCaptureSession(
                    Arrays.asList(surface),
                    new CameraCaptureSession.StateCallback() {
                        @Override
                        public void onConfigured(@NonNull CameraCaptureSession session) {
                            try {
                                // Build a repeating request for continuous recording.
                                CaptureRequest.Builder request =
                                        camera.createCaptureRequest(CameraDevice.TEMPLATE_RECORD);
                                request.addTarget(surface);

                                // Start the camera feed
                                session.setRepeatingRequest(
                                        request.build(),
                                        null,
                                        backgroundHandler
                                );

                                // Start recording and set the timestamp after the recorder starts
                                if (isFront) {
                                    frontMediaRecorder.start();
                                    // Use elapsedRealtime for a more accurate recording offset
                                    videoStartTimeMillis = SystemClock.elapsedRealtime();
                                    frontSession = session;
                                    Log.d(TAG, "Front Camera Recording Started (timestamp reset with elapsedRealtime).");
                                } else {
                                    rearMediaRecorder.start();
                                    rearSession = session;
                                    Log.d(TAG, "Rear Camera Recording Started.");
                                }
                            } catch (CameraAccessException e) {
                                Log.e(TAG, "Error configuring camera session: " + e.getMessage());
                            }
                        }

                        @Override
                        public void onConfigureFailed(@NonNull CameraCaptureSession session) {
                            Log.e(TAG, "Camera Configuration Failed.");
                        }
                    },
                    backgroundHandler
            );
        } catch (CameraAccessException e) {
            Log.e(TAG, "Error creating capture session: " + e.getMessage());
        }
    }

    private void stopRecording() {
        try {
            if (frontMediaRecorder != null) {
                frontMediaRecorder.stop();
                frontMediaRecorder.reset();
            }
            if (rearMediaRecorder != null) {
                rearMediaRecorder.stop();
                rearMediaRecorder.reset();
            }
            isRecording = false;
            Log.d(TAG, "Stopped recording.");

            // Close CSV logging
            closeCsvFile();

        } catch (Exception e) {
            Log.e(TAG, "Error stopping MediaRecorder: " + e.getMessage());
        }

        // Optionally close the cameras
        closeCameras();
    }

    private void closeCameras() {
        if (frontSession != null) {
            frontSession.close();
            frontSession = null;
        }
        if (rearSession != null) {
            rearSession.close();
            rearSession = null;
        }
        if (frontCameraDevice != null) {
            frontCameraDevice.close();
            frontCameraDevice = null;
        }
        if (rearCameraDevice != null) {
            rearCameraDevice.close();
            rearCameraDevice = null;
        }
        stopBackgroundThread();
    }


    private void startBackgroundThread() {
        backgroundThread = new HandlerThread("CameraBackground");
        backgroundThread.start();
        backgroundHandler = new Handler(backgroundThread.getLooper());
    }

    private void stopBackgroundThread() {
        if (backgroundThread != null) {
            backgroundThread.quitSafely();
            try {
                backgroundThread.join();
                backgroundThread = null;
                backgroundHandler = null;
            } catch (InterruptedException e) {
                Log.e(TAG, "Interrupted while stopping background thread: " + e.getMessage());
            }
        }
    }


    private void openCsvFile() {
        try {
            // Create a CSV file in your app's private external files directory
            File dir = getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
            if (dir == null) {
                Log.e(TAG, "Could not access external files directory for CSV.");
                return;
            }
            if (!dir.exists()) {
                dir.mkdirs();
            }

            csvFile = new File(dir, "sensor_data.csv");
            csvWriter = new FileWriter(csvFile, false); // false = overwrite if exists

            // Write CSV header
            csvWriter.append("offsetMs,wallClockTimestamp,accX,accY,accZ,speed,latitude,longitude\n");
            csvWriter.flush();

            Log.d(TAG, "CSV file created at: " + csvFile.getAbsolutePath());

        } catch (IOException e) {
            Log.e(TAG, "Error opening CSV file for writing: " + e.getMessage());
        }
    }

    private void closeCsvFile() {
        try {
            if (csvWriter != null) {
                csvWriter.flush();
                csvWriter.close();
                csvWriter = null;
            }
            Log.d(TAG, "CSV file closed.");
        } catch (IOException e) {
            Log.e(TAG, "Error closing CSV file: " + e.getMessage());
        }
    }


    private void logSensorData() {
        if (csvWriter == null) return;
        // The offset is measured from the moment the front recorder starts; rows written before
        // that point would carry meaningless offsets and break the video/sensor alignment.
        if (videoStartTimeMillis == 0) return;

        try {
            // Use elapsedRealtime for calculating elapsed time since video start
            long nowElapsed = SystemClock.elapsedRealtime();
            long offsetMs = nowElapsed - videoStartTimeMillis;

            // Also record the wall-clock time for reference
            long wallClockNow = System.currentTimeMillis();
            String wallClock = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(new Date(wallClockNow));

            String row = offsetMs + "," + wallClock + ","
                    + accelerationX + "," + accelerationY + "," + accelerationZ + ","
                    + speed + "," + latitude + "," + longitude + "\n";

            csvWriter.append(row);
            csvWriter.flush();

            Log.d("CSV", "Data logged: " + row);

        } catch (IOException e) {
            Log.e("CSV", "Error writing to CSV file", e);
        }
    }


    private void sendFilesToServer() {
        new Thread(() -> {
            // Send the front video
            sendFileToServer(frontVideoPath);

            // Send the rear video
            sendFileToServer(rearVideoPath);

            // Send the CSV file
            if (csvFile != null && csvFile.exists()) {
                sendFileToServer(csvFile.getAbsolutePath());
            }
        }).start();
    }

    private void sendFileToServer(String filePath) {
        try {
            File file = new File(filePath);
            if (!file.exists()) {
                Log.e(TAG, "File does not exist: " + filePath);
                return;
            }

            FileInputStream fileInputStream = new FileInputStream(file);
            Socket socket = new Socket(SERVER_IP, SERVER_PORT);
            OutputStream outputStream = socket.getOutputStream();
            DataOutputStream dos = new DataOutputStream(outputStream);

            // Send file name and length
            dos.writeUTF(file.getName());
            dos.writeLong(file.length());

            // Send file data in chunks
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = fileInputStream.read(buffer)) != -1) {
                outputStream.write(buffer, 0, bytesRead);
            }

            fileInputStream.close();
            socket.close();
            Log.d(TAG, "File sent successfully: " + filePath);

        } catch (Exception e) {
            Log.e(TAG, "Error sending file: " + e.getMessage());
        }
    }
}
