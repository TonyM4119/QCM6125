package android.os;
public class PowerManager {
    public int calls;
    public long lastUptime;
    public void goToSleep(long uptime) { calls++; lastUptime=uptime; }
}
