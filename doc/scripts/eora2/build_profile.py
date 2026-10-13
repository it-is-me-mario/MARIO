"""Verify source-only Eora2 Common metadata; never read numerical MRIO blocks."""
from pathlib import Path
import hashlib,json

VERSION='20260825T154218'
SOURCE='https://www.eora.org/metadata'
STRUCTURE='https://www.eora.org/Eora2Structure.xlsx'
ROOT=f'https://www.eora.org/r2/Eoras/versions/{VERSION}'


def build(folder, data):
    folder,data=Path(folder),Path(data)
    countries=json.loads((folder/'countries.json').read_text())
    rows=[row.split('\t') for row in (folder/'classification-common.txt').read_text().splitlines()]
    if len(countries)!=190 or len(rows)!=25 or any(r[0]!='Industries' or len(r)!=2 for r in rows):
        raise ValueError('Recheck Eora2 country coverage and common classification')
    registry={r['iso3']:r for r in json.loads((data/'world-country-map.json').read_text())['countries']}
    if set(countries)-set(registry):raise ValueError('Unreviewed source country codes')
    sectors=[row[1] for row in rows]
    if len(set(sectors))!=25:raise ValueError('Duplicate native categories')
    factors=json.loads((folder/'pi_categories.json').read_text())
    consumption=json.loads((folder/'fd_categories.json').read_text())
    satellites=json.loads((folder/'satellite_categories.json').read_text())
    if len(factors)!=6 or len(consumption)!=6 or len(satellites)!=42:raise ValueError('Source metadata set changed')
    regions=[{'label':code,'name':registry[code]['name'],'source_name':name,'kind':'country','iso3':code} for code,name in countries.items()]
    sets={'Region':list(countries),'Sector':sectors,'Factor of production':factors,'Consumption category':consumption,'Satellite account':list(satellites)}
    digest=lambda value:hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    files={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ['countries.json','classification-common.txt','pi_categories.json','fd_categories.json','satellite_categories.json','Eora2Structure.xlsx']}
    pid='eora2-common-2024-scope'
    return {'schema_version':1,'id':pid,'source':'EORA','guide':'eora2','version':'2','variant':'Common',
        'label':'Eora2 · Common classification · 2024 metadata','release':'Eora2 · Common',
        'year':2024,'years':[2024],'website_years':[],'table':'Common classification','status':'source_verified',
        'parser_supported':False,'numeric_publication':False,'workbook_allowed':False,'environmental':True,'scope_group':'Eora2 Common',
        'counts':{key:len(value) for key,value in sets.items()},'sets':sets,
        'native_codes':{'Sector':{name:str(i+1) for i,name in enumerate(sectors)}},
        'native_descriptions':{'Satellite account':satellites},
        'region_counts':[{'region':r['label'],'set':'Sector','count':25} for r in regions],
        'region_items':[],'set_flags':{},
        'geography':{'status':'source_verified_individual_regions','scope':'global','regions':regions,
            'individual_countries':190,'aggregate_count':0,'unresolved_count':0,'country_memberships':[],
            'method':'Official public Eora2 countries.json; ISO3 codes verified against the country registry.'},
        'coverage_signatures':{'geography':digest(sorted(countries)),'economic':digest(sectors)},
        'classifications':{'status':'native_labels','native_classification':'Eora2 custom 25-sector common classification; no verified NACE/CPA correspondence.','mappings':[]},
        'provenance':{'method':'public_source_metadata','source_filename':'Eora2 public metadata JSON and classification file',
            'source_sha256':digest(files),'source_checksums':files,'source_url':SOURCE,'metadata_version':VERSION,
            'source_urls':{'countries':ROOT+'/common/countries.json','sectors':ROOT+'/datasets/national_io/ABW/2024/Classification_ABW_2024.txt',
                'factors':ROOT+'/common/pi_categories.json','consumption':ROOT+'/common/fd_categories.json','satellites':ROOT+'/common/satellite_categories.json','structure':STRUCTURE},
            'options':{'unit':'Monetary'},'reading_scope':'Public classification metadata only; no login, numerical MRIO blocks, parser run or indicator values.'},
        'source_url':SOURCE,'source_structure_url':STRUCTURE,'license_url':'https://www.eora.org/licensing',
        'attribution':'Eora2, KGM & Associates. Public country and classification metadata; source rights retained.',
        'scope_note':'Eora2 Common: public 2024 metadata only, version '+VERSION+'. No MARIO parser or numerical browser indicators. The source structure workbook contains older 26-sector examples; this inventory uses the current 25-sector metadata. Other years, Full Eora2 national classifications and NACE/CPA mappings are not inferred.',
        'workbook':f'_static/data/external_profiles/{pid}-sets.xlsx','detail':f'_static/data/external_profiles/{pid}.json'}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata',type=Path,required=True);parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();profile=build(args.metadata,args.data);args.output.mkdir(parents=True,exist_ok=True)
    (args.output/(profile['id']+'.json')).write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'id':profile['id'],'counts':profile['counts'],'parser_supported':False,'numeric_publication':False}))
