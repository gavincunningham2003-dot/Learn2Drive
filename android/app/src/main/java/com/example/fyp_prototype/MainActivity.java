package com.example.fyp_prototype;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        Button btnPracticeDriving = findViewById(R.id.btnPracticeDriving);
        btnPracticeDriving.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                // Navigate to the StreamingActivity
                Intent intent = new Intent(MainActivity.this, StreamingActivity.class);
                startActivity(intent);
            }
        });


        // Button to navigate to Track Progress Activity
        Button trackProgressButton = findViewById(R.id.btnTrackProgress);
        trackProgressButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent intent = new Intent(MainActivity.this, TrackProgressActivity.class);
                startActivity(intent);
            }
        });


    }
}
