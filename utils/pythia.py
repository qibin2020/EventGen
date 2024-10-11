import re


def replace_in_config(config, replacements={}):
    new_config = []
    for line in config.splitlines(keepends=True):
        for key, value in replacements.items():
            pattern = rf"^\s*{re.escape(key)}\s*=\s*.*"
            replacement = f"{key} = {value}"
            if re.match(pattern, line):
                _line = re.sub(pattern, replacement, line)
            else:
                _line = line
        new_config.append(_line)
    return "".join(new_config)


def replacements(n_events=1, beams_lhef=None):
    _replacements = {"Main:numberOfEvents": n_events}
    if beams_lhef is not None:
        _replacements["Beams:LHEF"] = beams_lhef
    return _replacements
