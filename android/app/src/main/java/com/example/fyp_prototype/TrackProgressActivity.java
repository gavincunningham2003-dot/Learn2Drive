package com.example.fyp_prototype;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.util.Log;
import android.widget.Button;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;

import com.google.android.gms.maps.*;
import com.google.android.gms.maps.model.*;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.DataInputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class TrackProgressActivity extends AppCompatActivity
        implements OnMapReadyCallback,
        GoogleMap.OnMarkerClickListener {

    private static final String TAG = "TrackProgress";

    // ─────────── TCP SERVER CONFIG ───────────
    private static final String SERVER_HOST = "192.168.0.247"; //set as your servers ip
    private static final int    SERVER_PORT = 9000;
    private static final int    TIMEOUT_MS  = 7_000;

    // ─────────── CACHE PREFS ───────────
    private static final String SP_NAME      = "EventCache";
    private static final String SP_JSON      = "events_json";
    private static final String SP_LAST_SYNC = "last_sync_time";

    private GoogleMap mMap;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.track_behaviour);

        // Home button
        Button btnHome = findViewById(R.id.btnHome);
        btnHome.setOnClickListener(v -> {
            startActivity(new Intent(this, MainActivity.class));
            finish();
        });

        // Obtain the MapFragment and get notified when it’s ready
        SupportMapFragment frag =
                (SupportMapFragment)getSupportFragmentManager()
                        .findFragmentById(R.id.map);
        if (frag != null) frag.getMapAsync(this);
        else Toast.makeText(this, "Map failed to load", Toast.LENGTH_LONG).show();
    }

    @Override
    public void onMapReady(@NonNull GoogleMap googleMap) {
        mMap = googleMap;
        mMap.setOnMarkerClickListener(this);
        pullAndPlot();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
    }

    private void pullAndPlot() {
        io.execute(() -> {
            String json = fetchViaTcp();    //request from network
            if (json == null) {
                SharedPreferences prefs = getSharedPreferences(SP_NAME, MODE_PRIVATE);     //use cached version
                json = prefs.getString(SP_JSON, null);
                if (json == null) {
                    runOnUiThread(() ->
                            Toast.makeText(this, "No data available", Toast.LENGTH_LONG).show()
                    );
                    return;
                }
            }

            List<MarkerOptions>    opts = new ArrayList<>();
            List<JSONObject>       tags = new ArrayList<>();

            JSONArray arr;
            try {
                arr = new JSONArray(json);
            } catch (Exception ex) {
                Log.e(TAG, "Parse error", ex);
                arr = new JSONArray();
            }
            for (int i = 0; i < arr.length(); i++) {
                try {
                    JSONObject ev = arr.getJSONObject(i);

                    // events with no GPS match arrive with null coordinates and cannot be plotted
                    if (ev.isNull("latitude") || ev.isNull("longitude")) continue;

                    double lat = ev.getDouble("latitude");
                    double lon = ev.getDouble("longitude");
                    String type = ev.getString("type");
                    int    c2l  = ev.optInt("center_to_left",  0);
                    int    c2r  = ev.optInt("center_to_right", 0);

                    float hue;
                    switch (type) {
                        case "departure":
                            hue = BitmapDescriptorFactory.HUE_BLUE; break;
                        case "turn":
                            if (c2l >= 2 && c2r >= 2) hue = BitmapDescriptorFactory.HUE_GREEN;
                            else if (c2l >= 1 && c2r >= 1) hue = BitmapDescriptorFactory.HUE_ORANGE;
                            else hue = BitmapDescriptorFactory.HUE_RED;     //decide marker hue by event
                            break;
                        default:
                            hue = BitmapDescriptorFactory.HUE_VIOLET;
                    }

                    MarkerOptions mo = new MarkerOptions()
                            .position(new LatLng(lat, lon))
                            .icon(BitmapDescriptorFactory.defaultMarker(hue));
                    opts.add(mo);
                    tags.add(ev);
                } catch (Exception ex) {
                    Log.e(TAG, "Skipping malformed event " + i, ex);   // keep going with the rest
                }
            }

            // Draw on UI thread
            runOnUiThread(() -> {
                mMap.clear();
                for (int i = 0; i < opts.size(); i++) {
                    Marker mk = mMap.addMarker(opts.get(i));
                    mk.setTag(tags.get(i));
                }

                if (!opts.isEmpty()) {
                    LatLng first = opts.get(0).getPosition();
                    mMap.moveCamera(CameraUpdateFactory.newLatLngZoom(first, 14f));
                } else {
                    mMap.moveCamera(CameraUpdateFactory
                            .newLatLngZoom(new LatLng(53.3498, -6.2603), 12f));
                }

                long last = getSharedPreferences(SP_NAME, MODE_PRIVATE)
                        .getLong(SP_LAST_SYNC, 0);
                if (last > 0) {
                    Toast.makeText(this, "Last sync: " + new Date(last),
                            Toast.LENGTH_SHORT).show();
                }
            });
        });
    }

    private String fetchViaTcp() {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress(SERVER_HOST, SERVER_PORT), TIMEOUT_MS);     //connect to tcp with timeout
            s.setSoTimeout(TIMEOUT_MS);

            // send request
            OutputStream out = s.getOutputStream();
            out.write("GET_EVENTS\n".getBytes(StandardCharsets.US_ASCII));
            out.flush();

            // read length prefix + payload
            DataInputStream in = new DataInputStream(s.getInputStream());
            int len = in.readInt();
            byte[] buf = new byte[len];
            in.readFully(buf);
            String json = new String(buf, StandardCharsets.UTF_8);

            // cache
            getSharedPreferences(SP_NAME, MODE_PRIVATE).edit()
                    .putString(SP_JSON, json)
                    .putLong(SP_LAST_SYNC, System.currentTimeMillis())
                    .apply();

            Log.d(TAG, "Fetched " + len + " bytes");
            return json;
        } catch (Exception e) {
            Log.e(TAG, "TCP fetch failed", e);
            return null;
        }
    }

    @Override
    public boolean onMarkerClick(@NonNull Marker marker) {
        JSONObject ev = (JSONObject)marker.getTag();
        if (ev == null) return false;

        try {
            String type = ev.getString("type");
            long   tms  = ev.getLong("event_time_ms");
            int    c2l  = ev.optInt("center_to_left",  0);
            int    c2r  = ev.optInt("center_to_right", 0);
            String when = String.format(Locale.US, "%.1fs", tms/1000.0);

            String msg;
            switch (type) {
                case "departure":
                    msg = "Left lane at " + when; break;
                case "turn":
                    if (c2l >=2 && c2r >=2) {
                        msg = "Good turn at " + when;
                    } else if (c2l>=1 && c2r>=1) {
                        String side = c2l<2? "left":"right";
                        msg = "Minor: only once looked " + side + " at " + when;
                    } else {
                        String side = (c2l==0)? "left":"right";
                        msg = "Missed entirely looking " + side + " at " + when;
                    }
                    break;
                default:
                    msg = "Event at " + when;
            }

            Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
        } catch (Exception ex) {
            Log.e(TAG, "onMarkerClick error", ex);
        }

        return true;
    }
}
