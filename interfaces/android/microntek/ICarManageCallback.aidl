package android.microntek;

import android.os.Bundle;

// Reconstructed interface declaration; transaction 1 is one-way in the reference.
oneway interface ICarManageCallback {
    void onStatusChanged(String event, in Bundle data);
}
