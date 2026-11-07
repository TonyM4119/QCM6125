package android.microntek;
import android.os.Bundle;
import android.os.RemoteException;
public interface ICarManageCallback {
    void onStatusChanged(String event, Bundle data) throws RemoteException;
    abstract class Stub implements ICarManageCallback {}
}
