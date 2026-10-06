#!/usr/bin/env python3
"""Builds data/graph.js and data/evidence.js from the Upstream model bundle (graph.json + links_detail.jsonl).
Usage: python3 tools/build_data.py "<path to out/model_v2>" """
import json, sys, os, collections
src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Downloads/work 2/out/model_v2')
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
g = json.load(open(os.path.join(src, 'graph.json')))
DISCLOSED = {'disclosed_share', 'disclosed_share_xbrl', 'disclosed_share_auto_extracted', 'derived_from_disclosed_amount',
             'disclosed_combined_group_share', 'disclosed_lower_bound', 'disclosed_share_unnamed_customer'}
dem = {e['link_id']: e for e in g['exposures'] if e['channel'] == 'demand'}
sup = {e['link_id']: e for e in g['exposures'] if e['channel'] == 'supply'}
nodes = []
for n in g['nodes']:
    v = n.get('value') or {}
    nodes.append({'id': n['id'], 'name': n['name'], 'ticker': n.get('ticker'), 'sp': bool(n.get('in_sp500')), 'sector': n.get('sector'),
                  'sub': n.get('sub_industry'), 'cap': v.get('value_used_usd_b'), 'capBasis': v.get('value_basis'),
                  'capAsOf': v.get('market_cap_as_of'), 'capNote': v.get('private_valuation_note'), 'rev': n.get('revenue_usd_b'), 'revEnd': n.get('revenue_period_end'),
                  'region': n.get('region'), 'tier': n.get('display_tier'), 'inModel': bool(n.get('in_model')), 'type': n.get('entity_type')})
links = []
for l in g['links']:
    o = {'id': l['link_id'], 'from': l['from'], 'to': l['to'], 'type': l['type'], 'label': l.get('label'), 'status': l.get('status'),
         'exist': l.get('existence_confidence'), 'method': l.get('classification_method'), 'review': l.get('review_status'),
         'role': l.get('model_role'), 'stake': l.get('stake_value_usd_b')}
    d, s = dem.get(l['link_id']), sup.get(l['link_id'])
    if d:
        o['basis'] = d.get('basis'); o['note'] = d.get('note')
        if d.get('basis') in DISCLOSED: o['share'] = d['weight_current']['mode']
    if s and s.get('basis') == 'disclosed_reliance':
        o['reliance'] = s['weight_current']['mode']; o['relNote'] = s.get('note')
    links.append({k: v for k, v in o.items() if v is not None})
# hand-added links kept outside the bundle (data/extra_links.json), merged on every rebuild
extra_path = os.path.join(root, 'data/extra_links.json'); extra = json.load(open(extra_path)) if os.path.exists(extra_path) else {'nodes': [], 'links': [], 'evidence': {}}
have = {n['id'] for n in nodes}
for n in extra['nodes']:
    if n['id'] not in have: nodes.append(n)
for n in nodes:
    if any(l['from'] == n['id'] or l['to'] == n['id'] for l in extra['links']): n['inModel'] = True
links += [l for l in extra['links'] if l['id'] not in {x['id'] for x in links}]
meta = {'version': g['meta'].get('version'), 'built': g['meta'].get('built'), 'coverage': g['meta'].get('coverage'),
        'priced': max((n['capAsOf'] or '') for n in nodes)}
os.makedirs(os.path.join(root, 'data'), exist_ok=True)
open(os.path.join(root, 'data/graph.js'), 'w').write('window.GRAPH = ' + json.dumps({'meta': meta, 'nodes': nodes, 'links': links}, separators=(',', ':')) + ';\n')
ev = {}
for line in open(os.path.join(src, 'links_detail.jsonl')):
    d = json.loads(line); out = []
    for e in (d.get('evidence') or [])[:2]:
        q = (e.get('quote') or '').strip()
        out.append({'q': q[:480] + ('…' if len(q) > 480 else ''), 'kind': e.get('quote_kind'), 'doc': e.get('form') or e.get('document'),
                    'filed': e.get('filed'), 'url': e.get('url'), 'by': e.get('reported_by'), 'tier': e.get('source_tier')})
    if out: ev[d['link_id']] = out
ev.update(extra['evidence'])
open(os.path.join(root, 'data/evidence.js'), 'w').write('window.EVIDENCE = ' + json.dumps(ev, separators=(',', ':'), ensure_ascii=False) + ';\n')
json.dump(g, open(os.path.join(root, 'data/graph.json'), 'w'), separators=(',', ':'))
c = collections.Counter
print('nodes', len(nodes), 'links', len(links), 'with evidence', len(ev))
print('propagating', sum(1 for l in links if l.get('role') == 'propagates'), 'with disclosed share', sum(1 for l in links if 'share' in l), 'with reliance', sum(1 for l in links if 'reliance' in l))
print(c((l.get('exist'), l.get('review')) for l in links if l.get('role') == 'propagates'))
