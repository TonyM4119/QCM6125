"""Record pinned Android source observations about sleep-event timestamp ordering."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_framework_storage_patch import REVISION
from prepare_vold_native_patch import extract_method

EXPECTED = {
    'core/java/android/os/PowerManager.java': '000b80fbd49aa0a18afa08e9d054b0fa09666c8aba5524a9e52228ddf7b3bc18',
    'services/core/java/com/android/server/power/PowerManagerService.java': 'eebc30ca368013710fd7bd87d69e23c6bef8e91c1a1262bf4d4dec9238b28b76',
    'services/core/java/com/android/server/power/PowerGroup.java': '4d8f76d7070ec4fd6ef4bf7d6c4ddf2e575b77e16192fe9c73eca9af797d7b4c',
}


def inspect(root):
    sources = {}
    for name, digest in EXPECTED.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Unreviewed power source: ' + name)
        sources[name] = data.decode()
    api, service, group = (sources[name] for name in EXPECTED)
    wrapper = extract_method(api, 'public void goToSleep(long time)')
    normal = extract_method(service,
        'private void goToSleepInternal(IntArray groupIds, long eventTime, int reason, int flags)')
    sleep = extract_method(group,
        'boolean sleepLocked(long eventTime, int uid, @PowerManager.GoToSleepReason int reason)')
    if ('goToSleep(time, GO_TO_SLEEP_REASON_APPLICATION, 0);' not in wrapper
            or 'eventTime < mLastWakeTime' not in sleep
            or 'eventTime < getLastWakeTimeLocked() || mWakefulness == WAKEFULNESS_DOZING' not in group
            or 'if (eventTime > now)' not in normal
            or 'to the timestamp of the input event' not in api):
        raise ValueError('Expected power event-order observations changed')
    if normal.index('mWakeUpDelegate.sleep(eventTime, reason, uid)') > normal.index('if (isNoDoze)'):
        raise ValueError('Power delegate ordering changed')
    return {'check_kind': 'Pinned source inspection only; no PowerManager execution',
            'source_revision': REVISION, 'input_sha256': EXPECTED,
            'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'observations': {
                'api_uses_uptime_input_event_timestamp': True,
                'single_argument_wrapper_uses_application_reason_and_zero_flags': True,
                'service_rejects_future_event_time': True,
                'normal_sleep_and_doze_reject_strictly_older_than_last_wake': True,
                'delegate_can_handle_request_before_normal_group_path': True},
            'limits': ['Strict less-than guards do not reject equal timestamps by time alone.',
                       'Callback receipt time is not the original hardware event timestamp.',
                       'CarPower wake callbacks need not correspond to an Android last-wake update.',
                       'Final check and later sleep call remain non-atomic.',
                       'No full platform build, real power service or hardware test.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.source_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print('Pinned sleep timestamp contract and normal-path/delegate ordering recorded; source inspection only.')
