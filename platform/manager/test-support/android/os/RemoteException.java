package android.os;
// Test-only API shape; never include in an Android build.
public class RemoteException extends Exception {
    public RemoteException(String message) { super(message); }
}
