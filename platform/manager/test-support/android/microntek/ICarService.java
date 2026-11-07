package android.microntek;
import android.os.IBinder;
import android.os.RemoteException;
public interface ICarService {
    IBinder asBinder();
    String getStringState(String key) throws RemoteException;
    void registerCallback(ICarManageCallback callback) throws RemoteException;
    void unregisterCallback(ICarManageCallback callback) throws RemoteException;
}
