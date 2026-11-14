from collections import defaultdict


def environment_groups(rows):
    groups = defaultdict(list)
    holiday = {}
    for row in rows:
        key = row['environment']
        if key in holiday and holiday[key] != row['holiday']:
            raise ValueError('inconsistent common environment')
        holiday[key] = row['holiday']
        groups[key].append(row)
    return dict(groups)
