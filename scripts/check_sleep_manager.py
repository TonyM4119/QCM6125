"""Compile proposed manager sources with test-only Android API shapes and execute host tests."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(root, work_dir, java):
    manager = root / 'platform/manager'
    work_dir = work_dir.resolve()
    if work_dir == manager.resolve() or manager.resolve() in work_dir.parents or work_dir in manager.resolve().parents:
        raise ValueError('Host output must not overlap manager source')
    paths = sorted(manager.rglob('*.java'))
    paths.append(root / 'Android.bp')
    source_hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    work_dir.mkdir(parents=True, exist_ok=True)
    sources = [str(p) for p in paths if p.suffix == '.java']
    compilation = subprocess.run([str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                    '-source', '17', '-target', '17', '-d', str(work_dir), *sources],
                   check=True, capture_output=True, text=True)
    outputs = []
    for name in ['HctSleepCoordinatorTest', 'AndroidHctSleepBridgeTest']:
        result = subprocess.run([str(java), '-cp', str(work_dir), 'com.android.server.hct.' + name],
                                check=True, capture_output=True, text=True)
        outputs.append(result.stdout.strip())
        print(outputs[-1])
    return {'check_kind': 'Actual proposed manager sources compiled/executed with host-only Android stubs',
            'compiler_mode': 'JDK compiler module with source/target 17; host APIs, not --release 17',
            'compiler_diagnostics': compilation.stderr.strip(),
            'source_sha256': source_hashes,
            'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'test_outputs': outputs,
            'limits': ['Android API shapes are test stubs, not a compiled Android platform or real Binder.',
                       'Android.bp has not been evaluated by Soong.',
                       'No startup registration, manager replacement, privilege grants or device operations.',
                       'Final power check is not atomic with the later PowerManager call.',
                       'Blocked remote calls cannot be cancelled; late replies are invalidated.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, default=Path('work/manager-host'))
    parser.add_argument('--java', type=Path, default=Path('/usr/bin/java'))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(Path(__file__).resolve().parents[1], args.work_dir, args.java)
    except subprocess.CalledProcessError as error:
        print(error.stderr or error.stdout)
        raise SystemExit(error.returncode)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
