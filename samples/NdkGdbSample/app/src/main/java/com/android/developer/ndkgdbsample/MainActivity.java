package com.android.developer.ndkgdbsample;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView tv = new TextView(this);
        setContentView(tv);
        tv.setText(getHelloString());
    }

    private native String getHelloString();

    static {
        System.loadLibrary("app");
    }
}
