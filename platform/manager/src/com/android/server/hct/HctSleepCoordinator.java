package com.android.server.hct;

import java.util.Objects;
import java.util.concurrent.Executor;

/** Single-flight preparation policy for a future manager; no hardware APIs here. */
public final class HctSleepCoordinator implements AutoCloseable {
    public interface Ports {
        String readCarPower() throws Exception;
        boolean prepareStorage() throws Exception;
        void requestSleep() throws Exception;
    }

    public enum Outcome { IDLE, CANCELLED, STORAGE_FAILED, REQUESTED, ERROR, CLOSED }

    private final Object mLock = new Object();
    private final Ports mPorts;
    private final Executor mWorker;
    private String mPower;
    private long mGeneration;
    private long mActiveGeneration;
    private boolean mRunning;
    private boolean mClosed;
    private Outcome mLastOutcome = Outcome.IDLE;
    private Exception mLastFailure;

    public HctSleepCoordinator(Ports ports, Executor worker) {
        mPorts = Objects.requireNonNull(ports);
        mWorker = Objects.requireNonNull(worker);
    }

    /** Called immediately on receipt of a power event, including wake/unknown states. */
    public void onCarPowerState(String power) {
        long launch = -1;
        synchronized (mLock) {
            if (mClosed || Objects.equals(mPower, power)) return;
            mPower = power;
            mGeneration++;
            if (!mRunning && "sleep".equals(power)) {
                mRunning = true;
                mActiveGeneration = mGeneration;
                launch = mGeneration;
            }
        }
        if (launch != -1) submit(launch);
    }

    private boolean current(long generation) {
        synchronized (mLock) {
            return !mClosed && mGeneration == generation && "sleep".equals(mPower);
        }
    }

    private void submit(long generation) {
        try {
            mWorker.execute(() -> run(generation));
        } catch (RuntimeException failure) {
            synchronized (mLock) {
                if (mActiveGeneration == generation) {
                    mRunning = false;
                    mLastFailure = failure;
                    mLastOutcome = mClosed ? Outcome.CLOSED : Outcome.ERROR;
                }
            }
        }
    }

    private void run(long generation) {
        Outcome result = Outcome.CANCELLED;
        Exception failure = null;
        try {
            if (current(generation) && "sleep".equals(mPorts.readCarPower())
                    && current(generation)) {
                boolean prepared = mPorts.prepareStorage();
                if (current(generation) && "sleep".equals(mPorts.readCarPower())
                        && current(generation)) {
                    if (prepared) {
                        // No remote call runs under mLock. This final check is not
                        // atomic with PowerManager's later Binder transaction.
                        mPorts.requestSleep();
                        result = Outcome.REQUESTED;
                    } else {
                        result = Outcome.STORAGE_FAILED;
                    }
                }
            }
        } catch (Exception error) {
            result = Outcome.ERROR;
            failure = error;
        }
        long launch = -1;
        synchronized (mLock) {
            mRunning = false;
            mLastFailure = failure;
            mLastOutcome = mClosed ? Outcome.CLOSED : result;
            // Wake followed by a new sleep must get a fresh acknowledgement,
            // even if the original storage call completed successfully.
            if (!mClosed && mGeneration != generation && "sleep".equals(mPower)) {
                mRunning = true;
                mActiveGeneration = mGeneration;
                launch = mGeneration;
            }
        }
        if (launch != -1) submit(launch);
    }

    public Outcome getLastOutcome() {
        synchronized (mLock) { return mLastOutcome; }
    }

    public Exception getLastFailure() {
        synchronized (mLock) { return mLastFailure; }
    }

    @Override
    public void close() {
        synchronized (mLock) {
            mClosed = true;
            mGeneration++;
            mLastOutcome = Outcome.CLOSED;
        }
    }
}
