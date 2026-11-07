package com.android.server.hct;

import android.microntek.ICarManageCallback;
import android.microntek.ICarService;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.RemoteException;
import android.os.SystemClock;
import android.os.storage.IStorageManager;
import android.util.Slog;

import java.util.Objects;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Uninstalled experimental Android adapter. Requires patched IStorageManager and
 * platform privileges. Caller owns the worker thread and service discovery.
 */
public final class AndroidHctSleepBridge implements AutoCloseable {
    private static final String TAG = "HctSleepBridge";
    private final ICarService mCar;
    private final IStorageManager mStorage;
    private final Handler mWorker;
    private final HctSleepCoordinator mCoordinator;
    private final AtomicBoolean mStarted = new AtomicBoolean();
    private final AtomicBoolean mClosed = new AtomicBoolean();
    private final Object mEventLock = new Object();
    private long mEventCount;
    // Only accessed by mWorker's thread.
    private boolean mCarLinked;
    private boolean mStorageLinked;
    private boolean mRegistrationAttempted;

    private final IBinder.DeathRecipient mDeath = this::close;
    private final ICarManageCallback mCallback = new ICarManageCallback.Stub() {
        @Override
        public void onStatusChanged(String event, Bundle data) {
            if (!"CarPower".equals(event)) return;
            String power = null;
            try {
                if (data != null) power = data.getString("type");
            } catch (RuntimeException malformed) {
                Slog.w(TAG, "Invalid power callback", malformed);
            }
            synchronized (mEventLock) {
                mEventCount++;
                mCoordinator.onCarPowerState(power);
            }
        }
    };

    public AndroidHctSleepBridge(ICarService car, IStorageManager storage,
            PowerManager power, Handler worker) {
        mCar = Objects.requireNonNull(car);
        mStorage = Objects.requireNonNull(storage);
        Objects.requireNonNull(power);
        mWorker = Objects.requireNonNull(worker);
        if (worker.getLooper() == Looper.getMainLooper()) {
            throw new IllegalArgumentException("Storage preparation requires a background looper");
        }
        mCoordinator = new HctSleepCoordinator(new HctSleepCoordinator.Ports() {
            @Override public String readCarPower() throws RemoteException {
                return mCar.getStringState("carpower");
            }
            @Override public boolean prepareStorage() throws RemoteException {
                return mStorage.prepareHctExternalDisksForSleep();
            }
            @Override public void requestSleep(long eventUptime) {
                power.goToSleep(eventUptime);
            }
        }, command -> {
            if (!mWorker.post(command)) {
                throw new RejectedExecutionException("HCT sleep worker stopped");
            }
        }, SystemClock::uptimeMillis);
    }

    public void start() {
        if (mClosed.get() || !mStarted.compareAndSet(false, true)) return;
        if (!mWorker.post(this::register)) close();
    }

    private void register() {
        if (mClosed.get()) return;
        try {
            mCar.asBinder().linkToDeath(mDeath, 0);
            mCarLinked = true;
            if (mClosed.get()) return;
            mStorage.asBinder().linkToDeath(mDeath, 0);
            mStorageLinked = true;
            if (mClosed.get()) return;
            mRegistrationAttempted = true;
            mCar.registerCallback(mCallback);
            long before;
            synchronized (mEventLock) { before = mEventCount; }
            String initial = mCar.getStringState("carpower");
            synchronized (mEventLock) {
                // A newer callback must win over an in-flight startup read.
                if (before == mEventCount) mCoordinator.onCarPowerState(initial);
            }
        } catch (RemoteException | RuntimeException error) {
            Slog.w(TAG, "Sleep bridge registration failed", error);
            close();
        } finally {
            if (mClosed.get()) cleanup();
        }
    }

    public HctSleepCoordinator.Outcome getLastOutcome() {
        return mCoordinator.getLastOutcome();
    }

    public Exception getLastFailure() {
        return mCoordinator.getLastFailure();
    }

    @Override
    public void close() {
        if (!mClosed.compareAndSet(false, true)) return;
        // Invalidate a late acknowledgement immediately, even while IPC blocks
        // the worker. Queued cleanup never owns or shuts down the caller's looper.
        mCoordinator.close();
        if (!mWorker.post(this::cleanup)) {
            Slog.w(TAG, "Worker stopped before Binder cleanup");
        }
    }

    private void cleanup() {
        if (mRegistrationAttempted) {
            mRegistrationAttempted = false;
            try { mCar.unregisterCallback(mCallback); }
            catch (RemoteException | RuntimeException error) {
                Slog.w(TAG, "Callback cleanup failed", error);
            }
        }
        if (mCarLinked) {
            mCarLinked = false;
            try { mCar.asBinder().unlinkToDeath(mDeath, 0); }
            catch (RuntimeException error) { Slog.w(TAG, "Car death-link cleanup failed", error); }
        }
        if (mStorageLinked) {
            mStorageLinked = false;
            try { mStorage.asBinder().unlinkToDeath(mDeath, 0); }
            catch (RuntimeException error) { Slog.w(TAG, "Storage death-link cleanup failed", error); }
        }
    }
}
