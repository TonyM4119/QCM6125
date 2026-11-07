package com.android.server.hct;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public final class HctSleepCoordinatorTest {
    private static int scenarios;
    static void check(boolean yes, String why) { if (!yes) throw new AssertionError(why); }
    static final class Queue implements Executor {
        final ArrayDeque<Runnable> tasks = new ArrayDeque<>();
        @Override public void execute(Runnable task) { tasks.add(task); }
        void drain() {
            for (int i = 0; !tasks.isEmpty(); i++) {
                check(i < 20, "unexpected retry loop"); tasks.remove().run();
            }
        }
    }
    static final class Fixture implements HctSleepCoordinator.Ports {
        final Queue queue = new Queue();
        final List<String> calls = new ArrayList<>();
        final HctSleepCoordinator coordinator = new HctSleepCoordinator(this, queue);
        String power = "sleep";
        boolean prepared = true;
        Runnable duringRead, duringPreparation;
        boolean failRead, failPreparation, failSleep;
        @Override public String readCarPower() throws Exception {
            calls.add("read");
            if (failRead) throw new Exception("read failed");
            if (duringRead != null) { Runnable r = duringRead; duringRead = null; r.run(); }
            return power;
        }
        @Override public boolean prepareStorage() throws Exception {
            calls.add("prepare");
            if (failPreparation) throw new Exception("prepare failed");
            if (duringPreparation != null) {
                Runnable r = duringPreparation; duringPreparation = null; r.run();
            }
            return prepared;
        }
        @Override public void requestSleep() throws Exception {
            calls.add("sleep"); if (failSleep) throw new Exception("sleep failed");
        }
        void run() { coordinator.onCarPowerState("sleep"); queue.drain(); }
        void expect(HctSleepCoordinator.Outcome outcome, String... expected) {
            check(coordinator.getLastOutcome() == outcome, "wrong outcome");
            check(calls.equals(Arrays.asList(expected)), "wrong calls: " + calls);
            scenarios++;
        }
    }
    public static void main(String[] args) throws Exception {
        Fixture f = new Fixture(); f.run();
        f.expect(HctSleepCoordinator.Outcome.REQUESTED, "read", "prepare", "read", "sleep");
        f = new Fixture(); f.prepared = false; f.run();
        f.expect(HctSleepCoordinator.Outcome.STORAGE_FAILED, "read", "prepare", "read");
        Fixture wake = new Fixture();
        wake.duringPreparation = () -> wake.coordinator.onCarPowerState("power_on"); wake.run();
        wake.expect(HctSleepCoordinator.Outcome.CANCELLED, "read", "prepare");
        Fixture aba = new Fixture();
        aba.duringPreparation = () -> {
            aba.coordinator.onCarPowerState("power_on");
            aba.coordinator.onCarPowerState("sleep");
        };
        aba.run(); aba.expect(HctSleepCoordinator.Outcome.REQUESTED,
                "read", "prepare", "read", "prepare", "read", "sleep");
        f = new Fixture(); f.coordinator.onCarPowerState("sleep");
        f.coordinator.onCarPowerState("sleep"); f.queue.drain();
        f.expect(HctSleepCoordinator.Outcome.REQUESTED, "read", "prepare", "read", "sleep");
        f = new Fixture(); f.coordinator.onCarPowerState("sleep");
        f.coordinator.onCarPowerState("power_on"); f.queue.drain();
        f.expect(HctSleepCoordinator.Outcome.CANCELLED);
        f = new Fixture(); f.coordinator.onCarPowerState("sleep"); f.coordinator.close(); f.queue.drain();
        f.expect(HctSleepCoordinator.Outcome.CLOSED);
        Fixture closing = new Fixture(); closing.duringPreparation = closing.coordinator::close;
        closing.run(); closing.expect(HctSleepCoordinator.Outcome.CLOSED, "read", "prepare");
        f = new Fixture(); f.failRead = true; f.run();
        f.expect(HctSleepCoordinator.Outcome.ERROR, "read");
        check(f.coordinator.getLastFailure() != null, "exception was lost");
        f = new Fixture(); f.failPreparation = true; f.run();
        f.expect(HctSleepCoordinator.Outcome.ERROR, "read", "prepare");
        f = new Fixture(); f.failSleep = true; f.run();
        f.expect(HctSleepCoordinator.Outcome.ERROR, "read", "prepare", "read", "sleep");
        f = new Fixture(); f.power = "power_on"; f.run();
        f.expect(HctSleepCoordinator.Outcome.CANCELLED, "read");
        Fixture unknown = new Fixture();
        unknown.duringPreparation = () -> unknown.coordinator.onCarPowerState(null); unknown.run();
        unknown.expect(HctSleepCoordinator.Outcome.CANCELLED, "read", "prepare");
        Fixture changedRead = new Fixture();
        changedRead.duringRead = () -> changedRead.coordinator.onCarPowerState("power_on");
        changedRead.run(); changedRead.expect(HctSleepCoordinator.Outcome.CANCELLED, "read");
        Fixture changedState = new Fixture(); changedState.duringPreparation = () -> changedState.power = "power_on";
        changedState.run(); changedState.expect(HctSleepCoordinator.Outcome.CANCELLED, "read", "prepare", "read");
        f = new Fixture(); f.coordinator.onCarPowerState("power_on"); f.queue.drain();
        f.expect(HctSleepCoordinator.Outcome.IDLE);
        Fixture rejected = new Fixture();
        HctSleepCoordinator bad = new HctSleepCoordinator(rejected, r -> { throw new RejectedExecutionException(); });
        bad.onCarPowerState("sleep");
        check(bad.getLastOutcome() == HctSleepCoordinator.Outcome.ERROR && rejected.calls.isEmpty(), "rejection performed work");
        scenarios++;
        // Genuine concurrent arrival while the first call is blocked. No sleeps or hardware.
        ExecutorService worker = Executors.newSingleThreadExecutor();
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1), slept = new CountDownLatch(1);
        AtomicInteger prepares = new AtomicInteger(), active = new AtomicInteger(), maxActive = new AtomicInteger();
        try {
            HctSleepCoordinator concurrent = new HctSleepCoordinator(new HctSleepCoordinator.Ports() {
                @Override public String readCarPower() { return "sleep"; }
                @Override public boolean prepareStorage() throws Exception {
                    int count = prepares.incrementAndGet();
                    int now = active.incrementAndGet(); maxActive.accumulateAndGet(now, Math::max);
                    try {
                        if (count == 1) { entered.countDown(); check(release.await(5, TimeUnit.SECONDS), "release timed out"); }
                        return true;
                    } finally { active.decrementAndGet(); }
                }
                @Override public void requestSleep() { slept.countDown(); }
            }, worker);
            concurrent.onCarPowerState("sleep"); check(entered.await(5, TimeUnit.SECONDS), "worker did not enter");
            concurrent.onCarPowerState("power_on"); concurrent.onCarPowerState("sleep"); release.countDown();
            check(slept.await(5, TimeUnit.SECONDS), "fresh request did not finish");
            worker.submit(() -> {}).get(5, TimeUnit.SECONDS);
            check(prepares.get() == 2 && maxActive.get() == 1, "preparation overlapped or acknowledgement reused");
            check(concurrent.getLastOutcome() == HctSleepCoordinator.Outcome.REQUESTED, "concurrent outcome wrong");
            concurrent.close(); scenarios++;
        } finally { release.countDown(); worker.shutdownNow(); }
        System.out.println(scenarios + " coordinator scenarios passed; fake storage/power ports only.");
    }
}
