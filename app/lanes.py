from collections import defaultdict
from app.calendar import environment_groups
from app.store import unique


def duration_evidence(row):
    lower = row['duration_lower']
    upper = row['duration_upper']
    if lower < 0 or (upper is not None and upper < lower):
        raise ValueError('invalid duration bounds')
    if row['complete'] and upper != lower:
        raise ValueError('complete journey requires an exact time')
    return lower, upper


def promise_status(row, threshold):
    lower, upper = duration_evidence(row)
    if lower > threshold:
        return 'late'
    if upper is not None and upper <= threshold:
        return 'on_time'
    return 'unknown'


def preview(case):
    unique(case['shipments'], 'id')
    segments = unique(case['segments'], 'id')
    counts = defaultdict(lambda: {'late': 0, 'on_time': 0, 'unknown': 0, 'complete': 0})
    for row in case['shipments']:
        for identifier in row['segment_ids']:
            if segments[identifier]['environment'] != row['environment']:
                raise ValueError('segment environment mismatch')
        count = counts[row['destination'] + ':' + row['route']]
        count[promise_status(row, case['thresholds'][row['destination']])] += 1
        count['complete'] += int(row['complete'])
    return {'snapshot': case['_snapshot'], 'lane_counts': dict(counts),
            'environments': len(environment_groups(case['shipments'])), 'marginal_only': True}
