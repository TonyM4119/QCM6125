package android.os;
import java.util.HashMap;
public class Bundle {
    private final HashMap<String,Object> values = new HashMap<>();
    public void putString(String key, String value) { values.put(key,value); }
    public void putInt(String key, int value) { values.put(key,value); }
    public String getString(String key) { return (String) values.get(key); }
}
