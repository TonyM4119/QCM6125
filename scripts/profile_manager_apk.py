"""Profile the local working HCT manager APK and platform certificate; no execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from loguru import logger
logger.disable('androguard')
from androguard.core.apk import APK
from androguard.core.dex import DEX

ANDROID = '{http://schemas.android.com/apk/res/android}'
MANAGER = 'Landroid/microntek/service/ManageService;'


def certificates(apk):
    return sorted({hashlib.sha256(cert.dump()).hexdigest() for cert in apk.get_certificates()})


def profile(path, platform_path, framework_inventory=None):
    raw, platform_raw = path.read_bytes(), platform_path.read_bytes()
    apk, platform = APK(raw, raw=True), APK(platform_raw, raw=True)
    if apk.get_package() != 'android.microntek.service':
        raise ValueError('Expected HCT manager package')
    dexes = [DEX(data) for data in apk.get_all_dex()]
    defined = {cls.get_name() for dex in dexes for cls in dex.get_classes()}
    external_hct, hidden_platform, methods = set(), set(), []
    for dex in dexes:
        for cls in dex.get_classes():
            for method in cls.get_methods():
                selected = cls.get_name() == MANAGER and (
                    method.get_name() == 'onCreate' or method.get_name().lower().startswith('start'))
                calls, strings, offset = [], [], 0
                for ins in method.get_instructions():
                    output, name = ins.get_output(), ins.get_name()
                    if name.startswith('invoke-'):
                        match = re.search(r'(L[^ ]+;)->(.*)$', output)
                        if match:
                            ref = match.group(0)
                            if match[1].startswith('Landroid/microntek/') and match[1] not in defined:
                                external_hct.add(ref)
                            if match[1].startswith('Lcom/android/internal/'):
                                hidden_platform.add(ref)
                            if selected:
                                calls.append({'offset': offset, 'reference': ref})
                    if selected and name.startswith('const-string'):
                        value = output.split(', ', 1)[-1].strip('"')
                        if value.startswith(('android.microntek.', 'com.microntek.', 'com.hct.',
                                             'ro.', 'persist.', 'sys.')) or value in {'Appinfo', 'show_touches'}:
                            strings.append({'offset': offset, 'value': value})
                    offset += ins.get_length()
                if selected:
                    methods.append({'method': method.get_name(), 'descriptor': method.get_descriptor(),
                                    'calls': calls, 'reviewed_strings': strings})
    root = apk.get_android_manifest_xml()
    components = []
    for kind in ('service', 'receiver'):
        for node in root.findall('./application/' + kind):
            components.append({'kind': kind,
                               'attributes': {key.removeprefix(ANDROID): value for key, value in node.attrib.items()
                                              if key.startswith(ANDROID)},
                               'actions': sorted({action.get(ANDROID + 'name') for action in node.findall('./intent-filter/action')})})
    certs, platform_certs = certificates(apk), certificates(platform)
    result = {'sha256': hashlib.sha256(raw).hexdigest(), 'package': apk.get_package(),
            'shared_user_id': root.get(ANDROID + 'sharedUserId'),
            'min_sdk': apk.get_min_sdk_version(), 'target_sdk': apk.get_target_sdk_version(),
            'permissions': sorted(apk.get_permissions()), 'components': components,
            'certificate_sha256': certs,
            'platform_resource_sha256': hashlib.sha256(platform_raw).hexdigest(),
            'platform_certificate_sha256': platform_certs,
            'nonempty_certificate_sets_match': bool(certs) and certs == platform_certs,
            'defined_class_count': len(defined),
            'external_hct_calls': sorted(external_hct),
            'internal_platform_calls': sorted(hidden_platform),
            'manager_start_methods': sorted(methods, key=lambda r: r['method']),
            'limits': ['Static APK/DEX/manifest observations only; no APK, service or command executed.',
                       'Certificate identities are parsed metadata, not a complete signature-verification result.',
                       'Not all hidden APIs, native dependencies or reachable paths are inventoried.',
                       'Only selected constants retained; no full APK, bytecode or disassembly published.']}
    if framework_inventory is not None:
        inventory_raw = framework_inventory.read_bytes()
        tables = json.loads(inventory_raw)
        definitions = {signature.replace(' ', '') for table in tables
                       for signature in table['defined_signatures']}
        result['external_hct_definition_check'] = {
            'inventory_sha256': hashlib.sha256(inventory_raw).hexdigest(),
            'reference_count': len(external_hct),
            'missing_direct_definitions': sorted(reference for reference in external_hct
                                                  if reference.replace(' ', '') not in definitions),
            'limit': 'Exact direct signatures only; no visibility, inheritance, class-loading or runtime validation.'}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('platform_resources', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--framework-inventory', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(profile(args.apk, args.platform_resources,
                                              args.framework_inventory), indent=2) + '\n')
