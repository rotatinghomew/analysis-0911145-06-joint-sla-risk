from app.study_schema import rows_by_id, positive_integer


def validate(case):
    merchants = rows_by_id(case['merchants'])
    for transfer in case['transfers']:
        origin, destination = merchants[transfer['from']], merchants[transfer['to']]
        if origin['id'] == destination['id']:
            raise ValueError('不接受自转记录')
        positive_integer(transfer['boxes'])
        if [origin['region'], destination['region']] not in case['allowed_region_pairs']:
            raise ValueError('区域组合不可交易')
    return merchants


def current_transfers(case):
    validate(case)
    latest = {}
    for transfer in case['transfers']:
        if transfer['known_at'] > case['as_of_week']:
            continue
        if transfer['id'] not in latest or transfer['revision'] > latest[transfer['id']]['revision']:
            latest[transfer['id']] = transfer
    return [transfer for transfer in latest.values() if not transfer['cancelled']]


def owner_flows(case):
    merchants = validate(case)
    flows = {}
    for transfer in current_transfers(case):
        origin = merchants[transfer['from']]['owner']
        destination = merchants[transfer['to']]['owner']
        if origin == destination:
            continue
        key = (transfer['week'], origin, destination)
        flows[key] = flows.get(key, 0) + transfer['boxes']
    return flows


def preview(case):
    flows = owner_flows(case)
    return {'snapshot': case['_snapshot'], 'transfers': len(current_transfers(case)),
            'owner_flows': [{'week': key[0], 'from': key[1], 'to': key[2], 'boxes': boxes}
                            for key, boxes in sorted(flows.items())], 'descriptive_only': True}
