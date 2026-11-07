package android.os.storage;
import android.os.IBinder;
import android.os.RemoteException;
public interface IStorageManager {
    IBinder asBinder();
    boolean prepareHctExternalDisksForSleep() throws RemoteException;
}
