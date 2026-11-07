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
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;

public final class AndroidHctSleepBridgeTest {
    static int scenarios;
    static void check(boolean yes, String why) { if (!yes) throw new AssertionError(why); }
    static final class Binder implements IBinder {
        final Set<DeathRecipient> recipients = new HashSet<>();
        int links, unlinks;
        boolean failLink;
        @Override public void linkToDeath(DeathRecipient d,int flags) throws RemoteException {
            if (failLink) throw new RemoteException("death-link failed");
            recipients.add(d); links++;
        }
        @Override public boolean unlinkToDeath(DeathRecipient d,int flags) { unlinks++; return recipients.remove(d); }
        void die() { for (DeathRecipient d : new ArrayList<>(recipients)) d.binderDied(); }
    }
    static final class Car implements ICarService {
        final Binder binder = new Binder();
        ICarManageCallback callback;
        String state="power_on";
        int registers, unregisters;
        boolean failRegistration;
        Runnable readHook;
        @Override public IBinder asBinder() { return binder; }
        @Override public String getStringState(String key) {
            check("carpower".equals(key),"wrong state key"); String value=state;
            if (readHook!=null) { Runnable r=readHook;readHook=null;r.run(); }
            return value;
        }
        @Override public void registerCallback(ICarManageCallback c) throws RemoteException {
            registers++;callback=c;
            if (failRegistration) throw new RemoteException("registration failed");
        }
        @Override public void unregisterCallback(ICarManageCallback c) {
            check(callback==c,"wrong callback unregistered");unregisters++;callback=null;
        }
        void emit(String value) {
            state=value;Bundle data=new Bundle();data.putString("type",value);emit("CarPower",data);
        }
        void emit(String event,Bundle data) {
            try { callback.onStatusChanged(event,data); }
            catch (RemoteException impossible) { throw new AssertionError(impossible); }
        }
    }
    static final class Storage implements IStorageManager {
        final Binder binder=new Binder();boolean success=true,fail;int calls;Runnable during;
        @Override public IBinder asBinder() { return binder; }
        @Override public boolean prepareHctExternalDisksForSleep() throws RemoteException {
            calls++;if (during!=null) { Runnable r=during;during=null;r.run(); }
            if (fail) throw new RemoteException("storage failed");return success;
        }
    }
    static final class Fixture {
        final Car car=new Car();final Storage storage=new Storage();
        final PowerManager power=new PowerManager();final Handler worker=new Handler(new Looper());
        final AndroidHctSleepBridge bridge=new AndroidHctSleepBridge(car,storage,power,worker);
        void start() { bridge.start();worker.drain(); }
        void expect(int preparation,int sleeps,HctSleepCoordinator.Outcome outcome) {
            check(storage.calls==preparation,"wrong preparation calls");
            check(power.calls==sleeps,"wrong power calls");
            check(bridge.getLastOutcome()==outcome,"wrong outcome: "+bridge.getLastOutcome());scenarios++;
        }
    }
    public static void main(String[] args) {
        Fixture f=new Fixture();f.start();f.bridge.start();f.worker.drain();
        check(f.car.registers==1,"duplicate registration");f.bridge.close();f.bridge.close();f.worker.drain();
        check(f.car.unregisters==1 && f.car.binder.unlinks==1 && f.storage.binder.unlinks==1,"cleanup mismatch");
        f.expect(0,0,HctSleepCoordinator.Outcome.CLOSED);
        f=new Fixture();f.car.state="sleep";f.start();
        f.expect(1,1,HctSleepCoordinator.Outcome.REQUESTED);
        check(f.power.lastUptime==SystemClock.uptimeMillis(),"wall clock used for sleep");
        f=new Fixture();f.start();f.car.emit("sleep");f.car.emit("sleep");f.worker.drain();
        f.expect(1,1,HctSleepCoordinator.Outcome.REQUESTED);
        f=new Fixture();f.start();f.car.emit("Other",new Bundle());f.worker.drain();
        f.expect(0,0,HctSleepCoordinator.Outcome.IDLE);
        Fixture wake=new Fixture();wake.car.state="sleep";wake.storage.during=()->wake.car.emit("power_on");wake.start();
        wake.expect(1,0,HctSleepCoordinator.Outcome.CANCELLED);
        Fixture carDeath=new Fixture();carDeath.car.state="sleep";carDeath.storage.during=carDeath.car.binder::die;carDeath.start();
        carDeath.expect(1,0,HctSleepCoordinator.Outcome.CLOSED);
        check(carDeath.car.unregisters==1,"death did not unregister callback");
        Fixture storageDeath=new Fixture();storageDeath.car.state="sleep";storageDeath.storage.during=storageDeath.storage.binder::die;storageDeath.start();
        storageDeath.expect(1,0,HctSleepCoordinator.Outcome.CLOSED);
        Fixture malformed=new Fixture();malformed.car.state="sleep";
        malformed.storage.during=()->{Bundle data=new Bundle();data.putInt("type",1);malformed.car.emit("CarPower",data);};malformed.start();
        malformed.expect(1,0,HctSleepCoordinator.Outcome.CANCELLED);
        f=new Fixture();f.car.state="sleep";f.storage.success=false;f.start();
        f.expect(1,0,HctSleepCoordinator.Outcome.STORAGE_FAILED);
        f=new Fixture();f.car.state="sleep";f.storage.fail=true;f.start();
        f.expect(1,0,HctSleepCoordinator.Outcome.ERROR);
        f=new Fixture();f.car.failRegistration=true;f.start();
        f.expect(0,0,HctSleepCoordinator.Outcome.CLOSED);
        check(f.car.unregisters==1 && f.car.binder.unlinks==1 && f.storage.binder.unlinks==1,"failed registration leaked");
        f=new Fixture();f.worker.accepting=false;f.bridge.start();
        f.expect(0,0,HctSleepCoordinator.Outcome.CLOSED);
        f=new Fixture();f.bridge.close();f.bridge.start();f.worker.drain();
        check(f.car.registers==0,"closed bridge registered");f.expect(0,0,HctSleepCoordinator.Outcome.CLOSED);
        try {
            new AndroidHctSleepBridge(new Car(),new Storage(),new PowerManager(),new Handler(Looper.getMainLooper()));
            throw new AssertionError("main looper accepted");
        } catch (IllegalArgumentException expected) { scenarios++; }
        Fixture startup=new Fixture();startup.car.state="sleep";startup.car.readHook=()->startup.car.emit("power_on");startup.start();
        startup.expect(0,0,HctSleepCoordinator.Outcome.IDLE);
        Fixture nullData=new Fixture();nullData.car.state="sleep";
        nullData.storage.during=()->nullData.car.emit("CarPower",null);nullData.start();
        nullData.expect(1,0,HctSleepCoordinator.Outcome.CANCELLED);
        f=new Fixture();f.car.binder.failLink=true;f.start();
        check(f.car.registers==0 && f.car.binder.unlinks==0,"failed car link cleanup wrong");
        f.expect(0,0,HctSleepCoordinator.Outcome.CLOSED);
        f=new Fixture();f.storage.binder.failLink=true;f.start();
        check(f.car.registers==0 && f.car.binder.unlinks==1 && f.storage.binder.unlinks==0,
                "partial death-link setup leaked");
        f.expect(0,0,HctSleepCoordinator.Outcome.CLOSED);
        f=new Fixture();f.start();f.worker.accepting=false;f.car.emit("sleep");
        f.expect(0,0,HctSleepCoordinator.Outcome.ERROR);
        System.out.println(scenarios+" Android bridge scenarios passed against test-only API shapes; no Binder/device calls.");
    }
}
