"""Recharacterise published EXIOBASE monetary snapshots from verified source satellites.

Read only F and F_Y emission members, never transaction matrices. Keep results
as staged patches until every old AR6 total has been reproduced and reviewed.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, pathlib, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parents[3]
STAGE = pathlib.Path(os.environ.get('MARIO_EXIOBASE_STAGE', HERE/'Output/exiobase-browser')).resolve()
OUT = pathlib.Path(os.environ.get('MARIO_EXIOBASE_AR5_PATCHES', STAGE/'ar5-patches')).resolve()
sys.path.insert(0, str(HERE/'doc/scripts/exiobase'))
from remote_zip import RemoteArchive, archive_url


def factors_ar5(old):
    factors = {}
    for label, weight in old.items():
        if label.startswith('CH4'): weight = 0.028
        elif label.startswith('N2O'): weight = 0.265
        elif label == 'SF6 - air': weight = 23.5
        elif label == 'NF3 - air': weight = 16.1
        # CO2 remains 0.001; source-characterised HFC/PFC remain 0.001.
        factors[label] = weight
    return factors


def native_frame(archive, remote, name):
    member = archive.getinfo(name)
    remote.prefetch(member)
    raw = archive.read(member)  # Verifies original ZIP CRC.
    frame = pd.read_csv(io.BytesIO(raw), sep='\t', index_col=0, header=[0, 1]).fillna(0)  # MARIO's _read_numeric_matrix rule
    return frame, {'name': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                   'crc32': f'{member.CRC:08x}', 'size': len(raw)}


def weighted(frame, factors):
    missing = set(factors) - set(frame.index)
    if missing or not frame.index.is_unique:
        raise ValueError(f'Unexpected emission rows: {missing}')
    selected = frame.loc[list(factors)]
    values = selected.to_numpy(dtype=float)
    if not np.isfinite(values).all(): raise ValueError('Non-finite GHG input')
    return selected.mul(pd.Series(factors), axis=0).sum(axis=0)


def mapped(series, recipe, regions, fd=False):
    if not isinstance(series.index, pd.MultiIndex) or series.index.nlevels != 2:
        raise ValueError('Unexpected source axes')
    if fd:
        return series.groupby(level=0).sum().to_dict()
    expected = {(r['code'], sector) for r in regions for sector in recipe['sectors']}
    actual = set(series.index.to_list())
    if actual != expected or len(series) != len(expected):
        raise ValueError(f'Changed source sector axes: {len(actual)} vs {len(expected)}')
    return {(r['code'], sector): float(series.loc[(r['code'], sector)])
            for r in regions for sector in recipe['sectors']}


def validate_old(snapshot, old_sector, old_fd):
    r = snapshot['recipe']; regions = snapshot['regions']
    previous = {(row['code'], sector): v for row in regions
                for sector, v in zip(r['sectors'], row['ghg'])}
    if previous.keys() != old_sector.keys(): raise ValueError('Stored sector mismatch')
    worst = max(abs(old_sector[key] - value) / max(1, abs(value)) for key, value in previous.items())
    old_households = {row['code']: row.get('household_ghg', 0) for row in regions}
    if old_households.keys() != old_fd.keys(): raise ValueError('Stored FD mismatch')
    worst_fd = max(abs(old_fd[key] - value) / max(1, abs(value)) for key, value in old_households.items())
    if worst > 1e-8 or worst_fd > 1e-8:
        raise ValueError(f'Original AR6 totals do not reproduce: sectors {worst:.3g}, FD {worst_fd:.3g}')
    return max(worst, worst_fd)


def run_one(job):
    start = time.monotonic(); target = OUT/(job['id']+'.json')
    if target.exists(): return job['id'], 'cached', 0
    source = STAGE/'readings'/job['id']/'snapshot.json'
    if not source.exists(): raise ValueError('Missing original snapshot')
    snapshot = json.loads(source.read_text()); r = snapshot['recipe']
    if snapshot['provenance']['archive_checksum'] != job['checksum']:
        raise ValueError('Archive provenance changed')
    if r['parser_options'].get('unit') != 'Monetary' or r['table'] != 'IOT':
        raise ValueError('Only monetary IOT supported here')
    remote = RemoteArchive(archive_url(job['record'], job['key']), job['size'])
    with zipfile.ZipFile(remote) as archive:
        names = {m.filename for m in archive.infolist()}
        # v3.8.2 nests all files under IOT_YEAR_SYSTEM/; later releases
        # place the same satellite members at the ZIP root.
        options = [name for name in names if name.endswith('air_emissions/F.txt')]
        if not options: options = [name for name in names if name.endswith('satellite/F.txt')]
        if len(options) != 1: raise ValueError('Expected one native satellite F member')
        member = options[0]
        frame, hash_sector = native_frame(archive, remote, member)
        final, hash_fd = native_frame(archive, remote, member[:-len('F.txt')]+'F_Y.txt')
    old_factors = r['ghg_factors']; new_factors = factors_ar5(old_factors)
    old_sector = mapped(weighted(frame, old_factors), r, snapshot['regions'])
    old_fd = mapped(weighted(final, old_factors), r, snapshot['regions'], True)
    old_error = validate_old(snapshot, old_sector, old_fd)
    new_sector = mapped(weighted(frame, new_factors), r, snapshot['regions'])
    new_fd = mapped(weighted(final, new_factors), r, snapshot['regions'], True)
    payload = {'id': job['id'], 'factors': new_factors,
               'regions': [{'code': row['code'],
                            'ghg': [new_sector[(row['code'], sector)] for sector in r['sectors']],
                            'household_ghg': float(new_fd[row['code']])}
                           for row in snapshot['regions']],
               'validation': {'old_max_relative_error': old_error,
                              'old_world_tonnes': sum(old_sector.values())+sum(old_fd.values()),
                              'new_world_tonnes': sum(new_sector.values())+sum(new_fd.values()),
                              'source_members': [hash_sector, hash_fd],
                              'downloaded_bytes': remote.downloaded,
                              'archive_checksum': job['checksum']}}
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix('.json.tmp');temp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False));temp.replace(target)
    return job['id'], 'ok', round(time.monotonic()-start,1)

if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--workers',type=int,default=3);cli.add_argument('--id');cli.add_argument('--limit',type=int);args=cli.parse_args()
    jobs=json.loads((STAGE/'inventory.json').read_text())
    if args.id:jobs=[j for j in jobs if j['id']==args.id]
    if args.limit:jobs=jobs[:args.limit]
    print('Recharacterising',len(jobs),'monetary IOT readings',flush=True)
    errors=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_one,j):j for j in jobs}
        for i,future in enumerate(as_completed(futures),1):
            j=futures[future]
            try: print(i,len(jobs),future.result(),flush=True)
            except Exception as exc:
                errors.append((j['id'],str(exc)));print('FAILED',j['id'],str(exc),flush=True)
    if errors:
        print('ERRORS',errors,flush=True);sys.exit(1)
