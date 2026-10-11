"""Refresh governed and published native activity paths from nxbase after a sets update."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--nxbase',type=Path,required=True)
    cli.add_argument('--workbook',type=Path)
    cli.add_argument('--correspondence',type=Path)
    cli.add_argument('--nace-correspondence',type=Path)
    cli.add_argument('--doc',type=Path,default=Path(__file__).resolve().parents[1])
    args=cli.parse_args()
    module=args.nxbase/'src/nxbase/sets/activity_correspondence.py'
    spec=importlib.util.spec_from_file_location('nxbase_activity_correspondence',module)
    resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
    workbook=args.workbook or args.nxbase/'data/sets/nxbase_sets.xlsx'
    correspondence=args.correspondence or args.nxbase/'data/sets/activity_correspondences.json'
    result=resolver.snapshot(workbook,correspondence,args.doc/'classifications/sectoral/nace21-structure.json')
    for target in [args.doc/'classifications/sectoral/nxbase-gloria-icio.json',args.doc/'source/_static/data/economy/nxbase-gloria-icio.json']:
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    target=args.doc/'source/_static/data/economy/activity_correspondences.json'
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(correspondence,target)
    print(json.dumps({'native':len(result['items']),'families':sorted(set(n['namespace'] for n in result['items'])),'workbook_sha256':result['workbook_sha256']}))

    module=args.nxbase/'src/nxbase/sets/reviewed_activity_correspondence.py'
    spec=importlib.util.spec_from_file_location('nxbase_reviewed_activity',module)
    resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
    correspondence=args.nxbase/'data/sets/reviewed_activity_correspondences.json'
    result=resolver.snapshot(workbook,correspondence,args.doc/'classifications/sectoral/nace21-structure.json')
    for target in [args.doc/'classifications/sectoral/nxbase-reviewed-activities.json',args.doc/'source/_static/data/economy/nxbase-reviewed-activities.json']:
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    shutil.copyfile(correspondence,args.doc/'source/_static/data/economy/reviewed-activity-correspondences.json')
    print(json.dumps({'reviewed_native':len(result['items']),'linked':sum(bool(n['links']) for n in result['items'])}))

    module=args.nxbase/'src/nxbase/sets/commodity_correspondence.py'
    spec=importlib.util.spec_from_file_location('nxbase_commodity_correspondence',module)
    resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
    correspondence=args.nxbase/'data/sets/commodity_correspondences.json'
    result=resolver.snapshot(workbook,correspondence)
    for target in [args.doc/'classifications/sectoral/nxbase-products.json',args.doc/'source/_static/data/economy/nxbase-products.json']:
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    shutil.copyfile(correspondence,args.doc/'classifications/sectoral/commodity-correspondences.json')
    for destination in ['classifications/sectoral/product-production-reviews.json','source/_static/data/economy/product-production-reviews.json']:
        shutil.copyfile(args.nxbase/'data/sets/product_production_reviews.json',args.doc/destination)
    print(json.dumps({'commodity_native':len(result['items']),'linked':sum(bool(n['links']) for n in result['items'])}))

    module=args.nxbase/'src/nxbase/sets/nace_activity_correspondence.py'
    spec=importlib.util.spec_from_file_location('nxbase_nace_activity_correspondence',module)
    resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
    correspondence=args.nace_correspondence or args.nxbase/'data/sets/nace2_activity_correspondences.json'
    result=resolver.snapshot(workbook,correspondence,args.doc/'classifications/sectoral/nace21-structure.json')
    for target in [args.doc/'classifications/sectoral/nxbase-figaro-wiod.json',args.doc/'source/_static/data/economy/nxbase-figaro-wiod.json']:
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'native':len(result['items']),'families':sorted(set(n['namespace'] for n in result['items'])),'workbook_sha256':result['workbook_sha256']}))

    module=args.nxbase/'src/nxbase/sets/gtap_activity_correspondence.py'
    spec=importlib.util.spec_from_file_location('nxbase_gtap_activity_correspondence',module)
    resolver=importlib.util.module_from_spec(spec);spec.loader.exec_module(resolver)
    correspondence=args.nxbase/'data/sets/gtap_activity_correspondences.json'
    result=resolver.snapshot(workbook,correspondence,args.doc/'classifications/sectoral/nace21-structure.json')
    for target in [args.doc/'classifications/sectoral/nxbase-gtap.json',args.doc/'source/_static/data/economy/nxbase-gtap.json']:
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'native':len(result['items']),'families':sorted(set(n['namespace'] for n in result['items'])),'workbook_sha256':result['workbook_sha256']}))
