"""Generate an ignored C++ test fixture from the reviewed numeric EQ evidence."""
import json
from pathlib import Path
import sys

tables = json.loads(Path(sys.argv[1]).read_text())['tables']
parts = []
for key, width in [('music_stytle_data', 3), ('music_stytle_data15', 15), ('music_stytle_data31', 31)]:
    rows = tables[key]
    if len(rows) != 6 or any(len(row) != width or any(type(v) is not int or not -(2**31) <= v < 2**31
                                                    for v in row) for row in rows):
        raise ValueError('Invalid fixture dimensions/value')
    parts.append('{' + ','.join('{' + ','.join(map(str, row)) + '}' for row in rows) + '}')
Path(sys.argv[2]).write_text('#pragma once\n#include "eq_policy.hpp"\n'
                           'inline hct::EqPresetTables reference_eq_tables() { return {' +
                           ','.join(parts) + '}; }\n')
