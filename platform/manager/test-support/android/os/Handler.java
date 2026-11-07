package android.os;
import java.util.ArrayDeque;
public class Handler {
    private final Looper looper;
    private final ArrayDeque<Runnable> tasks = new ArrayDeque<>();
    public boolean accepting = true;
    public Handler(Looper value) { looper=value; }
    public Looper getLooper() { return looper; }
    public boolean post(Runnable task) { if (!accepting) return false; tasks.add(task); return true; }
    public void drain() {
        for (int i=0;!tasks.isEmpty();i++) {
            if (i>50) throw new AssertionError("unexpected Handler retry loop");
            tasks.remove().run();
        }
    }
}
