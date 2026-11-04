package android.microntek;

import android.microntek.ICarManageCallback;
import android.os.Bundle;

// Declaration order preserves the observed transactions 1..26. Original names,
// including spelling errors, are part of the compatibility contract.
interface ICarService {
    void putBooleanState(String key, boolean value);
    void putByteState(String key, byte value);
    void putIntState(String key, int value);
    void putStringState(String key, String value);
    void putByteArraryState(String key, in byte[] value);
    void putIntArraryState(String key, in int[] value);
    void putStringArraryState(String key, in String[] value);
    boolean getBooleanState(String key);
    byte getByteState(String key);
    int getIntState(String key);
    String getStringState(String key);
    byte[] getByteArrayState(String key);
    int[] getIntArrayState(String key);
    String[] getStringArrayState(String key);
    void registerCallback(ICarManageCallback callback);
    void unregisterCallback(ICarManageCallback callback);
    int setParameters(String command);
    String getParameters(String query);
    void putDataChanage(String type, String value);
    void dispatchMessage(String event, in Bundle data);
    void setEqIdx(int index);
    int getEqIdx();
    void setLud(boolean enabled);
    int getLud();
    void setVideoOverSpeed(boolean enabled);
    boolean getVideoEnable();
}
