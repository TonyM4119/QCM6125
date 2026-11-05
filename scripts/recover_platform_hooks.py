"""Inventory selected working-reference HCT hooks outside the car-service package."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from recover_binder_constants import analysis_copy
from androguard.core.dex import DEX

HOOKS = {
    'Lcom/android/server/SystemServer;': {'startMtcManage'},
    'Lcom/android/server/am/ActivityManagerService;': {'sendHCTRemoveTask'},
    'Lcom/android/server/pm/permission/PermissionManagerService;': {'isHctAppLists'},
    'Lcom/android/server/policy/PhoneWindowManager;': {'checkHctAuioApp', 'sendHctKeyCode'},
    'Lcom/android/server/wm/AppWarnings;': {'isHctAppLists'},
    'Lcom/android/server/wm/PointerEventDispatcher;': {'sendHctTouchStudy'},
    'Lcom/android/server/wm/Task;': {'HctSendAppinfo'},
}


def recover(path):
    hooks, callers = [], []
    references = {cls + '->' + method + '(' for cls, methods in HOOKS.items() for method in methods}
    with zipfile.ZipFile(path) as archive:
        for entry in sorted(archive.namelist()):
            if not entry.endswith('.dex'):
                continue
            for cls in DEX(analysis_copy(archive.read(entry))).get_classes():
                if cls.get_name() not in HOOKS:
                    continue
                for method in cls.get_methods():
                    selected = method.get_name() in HOOKS[cls.get_name()]
                    calls, strings, fields, offset = [], [], [], 0
                    for ins in method.get_instructions():
                        output, name = ins.get_output(), ins.get_name()
                        if name.startswith('invoke-'):
                            match = re.search(r'(L[^ ]+;->.*)$', output)
                            if match:
                                ref = match.group(1)
                                if selected:
                                    calls.append({'offset': offset, 'reference': ref})
                                if any(ref.startswith(prefix) for prefix in references):
                                    callers.append({'class': cls.get_name(), 'method': method.get_name(),
                                                    'descriptor': method.get_descriptor(),
                                                    'offset': offset, 'hook': ref})
                        if selected and name.startswith('const-string'):
                            value = output.split(', ', 1)[-1].strip('"')
                            if value.startswith(('android.microntek.', 'com.microntek.', 'com.hct.',
                                                 'ro.', 'persist.')):
                                strings.append({'offset': offset, 'value': value})
                        if selected and name.startswith(('iget', 'iput', 'sget', 'sput')):
                            match = re.search(r'(L[^ ]+;->.*)$', output)
                            if match:
                                fields.append({'offset': offset, 'operation': name, 'reference': match.group(1)})
                        offset += ins.get_length()
                    if selected:
                        hooks.append({'class': cls.get_name(), 'method': method.get_name(),
                                      'descriptor': method.get_descriptor(), 'calls': calls,
                                      'reviewed_strings': strings, 'fields': fields})
    expected = {(cls, method) for cls, methods in HOOKS.items() for method in methods}
    if {(r['class'], r['method']) for r in hooks} != expected or len(hooks) != len(expected):
        raise ValueError('Expected hook methods missing or changed')
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'hooks': sorted(hooks, key=lambda r: (r['class'], r['method'])),
            'call_sites_within_selected_classes': callers,
            'limits': ['Selected-class scan only; not a complete platform call graph.',
                       'Static references do not prove branches or runtime execution.',
                       'Only reviewed string prefixes retained; no full bytecode or disassembly.',
                       'Hidden-API metadata omitted in an in-memory copy; originals unchanged.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(recover(args.jar), indent=2) + '\n')
