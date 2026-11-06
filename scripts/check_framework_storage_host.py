"""Compile actual staged Java methods with fake framework objects, not Android."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from prepare_framework_storage_patch import SERVICE, CONTROLLER, CONNECTION
from prepare_vold_native_patch import extract_method

HARNESS = r'''
import java.util.*;
public class FrameworkStorageHost {
  static final List<String> calls = new ArrayList<>();
  static int scenarios;
  static void check(boolean yes, String why) { if (!yes) throw new AssertionError(why + calls); }
  static void expect(String... expected) {
    check(calls.equals(Arrays.asList(expected)), "unexpected sequence ");
    calls.clear();
    scenarios++;
  }
  static class Binder {
    static long clearCallingIdentity() { calls.add("clear"); return 77; }
    static void restoreCallingIdentity(long token) {
      check(token == 77, "identity token lost"); calls.add("restore");
    }
  }
  static class Slog { static void wtf(String tag, Exception e) { calls.add("error"); } }
  static class VolumeInfo {
    static final int TYPE_PUBLIC = 0, TYPE_PRIVATE = 1;
    static final int STATE_UNMOUNTED = 0, STATE_MOUNTED = 2, STATE_MOUNTED_READ_ONLY = 3;
  }
  static class DiskInfo {
    String id = "disk:fake";
    int flags; DiskInfo(int f) { flags = f; }
    boolean isSd() { return (flags & 4) != 0; }
    boolean isUsb() { return (flags & 8) != 0; }
  }
  static class ImmutableVolumeInfo {
    String id; DiskInfo disk; int type, state;
    ImmutableVolumeInfo(String i, DiskInfo d, int t, int s) { id=i; disk=d; type=t; state=s; }
    String getId() { return id; } DiskInfo getDisk() { return disk; }
    int getType() { return type; } int getState() { return state; }
  }
  static class WatchedVolumeInfo {
    ImmutableVolumeInfo vol;
    WatchedVolumeInfo(ImmutableVolumeInfo v) { vol=v; }
    ImmutableVolumeInfo getClonedImmutableVolumeInfo() { return vol; }
  }
  static class Volumes extends ArrayList<WatchedVolumeInfo> {
    WatchedVolumeInfo valueAt(int i) { return get(i); }
  }
  static class ExternalStorageServiceException extends Exception {
    ExternalStorageServiceException(String s) { super(s); }
  }
  static class StorageUserConnection {
    Set<String> sessions = new HashSet<>(Arrays.asList("external", "internal"));
    boolean fail;
    static class Session { String id; Session(String i) { id=i; } }
    class ActiveConnection {
      void endSession(Session session) throws ExternalStorageServiceException {
        calls.add("end:"+session.id);
        if (fail) throw new ExternalStorageServiceException("synthetic failure");
      }
    }
    ActiveConnection mActiveConnection = new ActiveConnection();
    Session removeSession(String id) { return sessions.remove(id) ? new Session(id) : null; }
    @@STRICT_END_SESSION@@
    void removeSessionAndWait(String id) throws ExternalStorageServiceException {
      calls.add("end:"+id);
      if (fail) throw new ExternalStorageServiceException("synthetic failure");
      sessions.remove(id);
    }
  }
  static class Controller {
    Object mLock = new Object(); boolean resetting;
    Map<Integer, StorageUserConnection> mConnections = new HashMap<>();
    boolean shouldHandle(ImmutableVolumeInfo vol) { return !resetting; }
    int getConnectionUserIdForVolume(ImmutableVolumeInfo vol) { return 10; }
    @@END_SESSION@@
  }
  static class Vold {
    boolean fail, failReset;
    String[] requestedIds;
    void unmount(String id) throws Exception {
      calls.add("unmount:"+id); if (fail) throw new Exception("synthetic vold failure");
    }
    void exreset() { calls.add("exreset"); }
    void exresetPublic(String[] ids) throws Exception {
      requestedIds = ids; calls.add("exreset");
      if (failReset) throw new Exception("synthetic native reset failure");
    }
  }
  static class PermissionBase {
    boolean allowed = true;
    void unmount_enforcePermission() {
      calls.add("permission"); if (!allowed) throw new SecurityException();
    }
    void prepareHctExternalDisksForSleep_enforcePermission() { unmount_enforcePermission(); }
  }
  static class Service extends PermissionBase {
    static final String TAG = "fake";
    boolean mBootCompleted = true, mDaemonConnected = true;
    Object mLock = new Object(); Volumes mVolumes = new Volumes();
    Vold mVold = new Vold(); Controller mStorageSessionController = new Controller();
    WatchedVolumeInfo findVolumeByIdOrThrow(String id) {
      calls.add("find:"+id); return mVolumes.get(0);
    }
    void unmount(ImmutableVolumeInfo vol) { calls.add("ordinary:"+vol.getId()); }
    @@UNMOUNT@@
    @@ACK_ENTRY@@
    @@RESET@@
  }
  static Service service(int type, int state) {
    Service s = new Service();
    s.mVolumes.add(new WatchedVolumeInfo(new ImmutableVolumeInfo("external",new DiskInfo(12),type,state)));
    s.mStorageSessionController.mConnections.put(10,new StorageUserConnection());
    return s;
  }
  public static void main(String[] args) {
    Service s = service(0,2);
    s.unmount("hctall"); expect("permission","clear","unmount:external","end:external","exreset","restore");
    if (@@SCOPED@@) check(Arrays.equals(s.mVold.requestedIds, new String[]{"disk:fake"}), "disk IDs lost ");
    check(s.mStorageSessionController.mConnections.get(10).sessions.equals(Set.of("internal")),
          "unrelated session removed ");
    s=service(0,2); s.allowed=false;
    try { s.unmount("hctall"); throw new AssertionError("permission bypass"); }
    catch (SecurityException expected) {} expect("permission");
    for (int gate=0; gate<2; gate++) {
      s=service(0,2); if (gate==0) s.mBootCompleted=false; else s.mDaemonConnected=false;
      s.unmount("hctall"); expect("permission");
    }
    s=service(0,2); s.unmount("ordinary-id"); expect("permission","find:ordinary-id","ordinary:external");
    s=service(0,2);
    s.mVolumes.add(new WatchedVolumeInfo(new ImmutableVolumeInfo("private",new DiskInfo(8),1,2)));
    s.unmount("hctall"); expect("permission","clear","error","restore");
    s=service(0,1); s.unmount("hctall"); expect("permission","clear","error","restore");
    s=service(0,0); s.unmount("hctall"); expect("permission","clear","exreset","restore");
    s=service(0,3); s.unmount("hctall"); expect("permission","clear","unmount:external","end:external","exreset","restore");
    s=service(0,2); s.mVold.fail=true; s.unmount("hctall");
    expect("permission","clear","unmount:external","error","restore");
    s=service(0,2); s.mStorageSessionController.mConnections.get(10).fail=true; s.unmount("hctall");
    expect("permission","clear","unmount:external","end:external","error","restore");
    s=service(0,2); s.mStorageSessionController.resetting=true; s.unmount("hctall");
    expect("permission","clear","unmount:external","error","restore");
    for (int flags : new int[]{0,16}) {
      s=service(0,2); s.mVolumes.get(0).vol.disk=new DiskInfo(flags); s.unmount("hctall");
      expect("permission","clear","exreset","restore");
    }
    s=service(0,2); s.mVolumes.get(0).vol.disk=null; s.unmount("hctall");
    expect("permission","clear","exreset","restore");
    if (@@SCOPED@@) {
      check(s.mVold.requestedIds.length==0, "null disk leaked into selection ");
      s=service(0,2);
      s.mVolumes.add(new WatchedVolumeInfo(new ImmutableVolumeInfo("external2",s.mVolumes.get(0).vol.disk,0,2)));
      s.mStorageSessionController.mConnections.get(10).sessions.add("external2");
      s.unmount("hctall");
      expect("permission","clear","unmount:external","end:external","unmount:external2","end:external2","exreset","restore");
      check(s.mVold.requestedIds.length==1, "disk IDs were duplicated ");
      s=service(0,0); s.unmount("hctall");
      expect("permission","clear","exreset","restore");
      check(s.mVold.requestedIds.length==1, "unmounted public disk omitted ");
      s=service(0,2);
      for (int i=0; i<64; i++) {
        DiskInfo d = new DiskInfo(8); d.id="disk:"+i;
        s.mVolumes.add(new WatchedVolumeInfo(new ImmutableVolumeInfo("v"+i,d,0,2)));
      }
      s.unmount("hctall"); expect("permission","clear","error","restore");
      s=service(0,2); s.mStorageSessionController.mConnections.clear();
      s.unmount("hctall"); expect("permission","clear","unmount:external","error","restore");
      s=service(0,2); s.mStorageSessionController.mConnections.get(10).sessions.remove("external");
      s.unmount("hctall"); expect("permission","clear","unmount:external","error","restore");
    }
    @@ACK_TESTS@@
    System.out.println(scenarios + " extracted Java method scenarios passed; fake framework objects only.");
  }
}
'''

ACK_TESTS = r'''
    s=service(0,2); check(s.prepareHctExternalDisksForSleep(),"success not acknowledged ");
    expect("permission","clear","unmount:external","end:external","exreset","restore");
    for (int gate=0;gate<2;gate++) {
      s=service(0,2); if (gate==0) s.mBootCompleted=false; else s.mDaemonConnected=false;
      check(!s.prepareHctExternalDisksForSleep(),"readiness failure acknowledged "); expect("permission");
    }
    s=service(1,2); check(!s.prepareHctExternalDisksForSleep(),"private media acknowledged ");
    expect("permission","clear","error","restore");
    s=service(0,2); s.mStorageSessionController.mConnections.get(10).fail=true;
    check(!s.prepareHctExternalDisksForSleep(),"session failure acknowledged ");
    expect("permission","clear","unmount:external","end:external","error","restore");
    s=service(0,2); s.mVold.fail=true;
    check(!s.prepareHctExternalDisksForSleep(),"unmount failure acknowledged ");
    expect("permission","clear","unmount:external","error","restore");
    s=service(0,2); s.allowed=false;
    try { s.prepareHctExternalDisksForSleep(); throw new AssertionError("ack permission bypass"); }
    catch (SecurityException expected) {} expect("permission");
    s=service(0,2); s.mStorageSessionController.mConnections.clear();
    check(!s.prepareHctExternalDisksForSleep(),"missing connection acknowledged ");
    expect("permission","clear","unmount:external","error","restore");
    s=service(0,2); s.mStorageSessionController.mConnections.get(10).sessions.remove("external");
    check(!s.prepareHctExternalDisksForSleep(),"missing session acknowledged ");
    expect("permission","clear","unmount:external","error","restore");
    s=service(0,2); s.mVold.failReset=true;
    check(!s.prepareHctExternalDisksForSleep(),"native failure acknowledged ");
    expect("permission","clear","unmount:external","end:external","exreset","error","restore");
'''


def check(source_root, work_dir, java, scoped=False, ack=False):
    if ack and not scoped:
        raise ValueError('Acknowledgement harness requires scoped sources')
    source_root, work_dir = source_root.resolve(), work_dir.resolve()
    if source_root == work_dir or source_root in work_dir.parents or work_dir in source_root.parents:
        raise ValueError('Harness output must not overlap the source tree')
    service = (source_root / SERVICE).read_text()
    controller = (source_root / CONTROLLER).read_text()
    methods = {
        'UNMOUNT': extract_method(service, 'public void unmount(String volId)'),
        'RESET': extract_method(service, ('private boolean' if ack else 'private void') + ' resetHctExternalDisks()'),
        'END_SESSION': extract_method(controller, 'public void endHctExternalSession(ImmutableVolumeInfo vol)'),
    }
    methods['STRICT_END_SESSION'] = (extract_method((source_root / CONNECTION).read_text(),
        'public void removeSessionAndWaitForHctReset(String sessionId)') if scoped else '')
    methods['ACK_ENTRY'] = extract_method(service, 'public boolean prepareHctExternalDisksForSleep()') if ack else ''
    harness = HARNESS.replace('@@SCOPED@@', 'true' if scoped else 'false').replace('@@ACK_TESTS@@', ACK_TESTS if ack else '')
    for name, method in methods.items():
        harness = harness.replace('@@' + name + '@@', method)
    work_dir.mkdir(parents=True, exist_ok=True)
    source = work_dir / 'FrameworkStorageHost.java'
    source.write_text(harness)
    # JRE includes jdk.compiler; use its module entry point without a javac launcher.
    subprocess.run([str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                    '-d', str(work_dir), str(source)], check=True, capture_output=True, text=True)
    run = subprocess.run([str(java), '-cp', str(work_dir), 'FrameworkStorageHost'],
                         check=True, capture_output=True, text=True)
    return {'check_kind': 'Extracted staged Java methods compiled with fake framework scaffolding',
            'source_file_sha256': {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                                   for name in (SERVICE, CONTROLLER, CONNECTION)},
            'host_recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'method_sha256': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in methods.items()},
            'harness_sha256': hashlib.sha256(harness.encode()).hexdigest(),
            'test_output': run.stdout.strip(),
            'limits': ['Not full Android translation-unit compilation or runtime validation.',
                       'Mock API shapes and state transitions do not prove target API compatibility.',
                       'No real Binder identity, permissions, FUSE, vold, sessions or device effects.',
                       'No hotplug/user/mount/concurrency validation.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--java', default='/usr/bin/java', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--scoped', action='store_true')
    parser.add_argument('--ack', action='store_true')
    args = parser.parse_args()
    report = check(args.source_root, args.work_dir, args.java, args.scoped, args.ack)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(report['test_output'])
