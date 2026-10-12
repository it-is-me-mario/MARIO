"""Append an Artifact Tool-authored notice, preserving original XLSX parts.

The import/export engine cannot handle the legacy multi-axis inventories within
reasonable memory. This serializer copies their worksheets and formula caches
verbatim; all newly authored cells and styles come from Artifact Tool.
"""
from copy import deepcopy
from pathlib import Path
import sys, zipfile
from xml.etree import ElementTree as E

M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
C='http://schemas.openxmlformats.org/package/2006/content-types'
E.register_namespace('',M);E.register_namespace('r',R)

def serialize(xml):
 # OPC readers require default namespaces on package Types/Relationships.
 # Register each part's root namespace locally before serializing it.
 E.register_namespace('',xml.tag.split('}')[0].removeprefix('{'))
 return E.tostring(xml,encoding='utf-8',xml_declaration=True)

def append(original,notice,output):
 with zipfile.ZipFile(original) as src,zipfile.ZipFile(notice) as note:
  original_styles=E.fromstring(src.read('xl/styles.xml'));styles=E.fromstring(note.read('xl/styles.xml'))
  offsets={};numfmt={}
  for key in ['numFmts','fonts','fills','borders','cellStyleXfs','cellXfs']:
   old=original_styles.find('{'+M+'}'+key);new=styles.find('{'+M+'}'+key)
   if new is None:continue
   if old is None:
    old=E.Element('{'+M+'}'+key,{'count':'0'});original_styles.insert(0,old)
   offsets[key]=len(old)
   for entry in new:
    item=deepcopy(entry)
    if key=='numFmts':
     before=item.attrib['numFmtId'];after=str(max([163]+[int(x.attrib['numFmtId']) for x in old])+1);numfmt[before]=after;item.attrib['numFmtId']=after
    if key in ['cellStyleXfs','cellXfs']:
     for attr,category in [('fontId','fonts'),('fillId','fills'),('borderId','borders'),('xfId','cellStyleXfs')]:
      if attr in item.attrib:item.attrib[attr]=str(int(item.attrib[attr])+offsets.get(category,0))
     if item.get('numFmtId')in numfmt:item.attrib['numFmtId']=numfmt[item.attrib['numFmtId']]
    old.append(item)
   old.set('count',str(len(old)))
  sheet=E.fromstring(note.read('xl/worksheets/sheet1.xml'))
  shared=[]
  if 'xl/sharedStrings.xml'in note.namelist():shared=E.fromstring(note.read('xl/sharedStrings.xml')).findall('{'+M+'}si')
  for cell in sheet.iter('{'+M+'}c'):
   if cell.get('s'):cell.set('s',str(int(cell.attrib['s'])+offsets['cellXfs']))
   if cell.get('t')=='s':
    value=cell.find('{'+M+'}v');si=deepcopy(shared[int(value.text)]);cell.remove(value);si.tag='{'+M+'}is';cell.append(si);cell.set('t','inlineStr')
  book=E.fromstring(src.read('xl/workbook.xml'));sheets=book.find('{'+M+'}sheets')
  rels=E.fromstring(src.read('xl/_rels/workbook.xml.rels'))
  types=E.fromstring(src.read('[Content_Types].xml'))
  existing=next((s for s in sheets if s.get('name')=='Read me'),None)
  if existing is not None:
   rid=existing.attrib['{'+R+'}id'];relationship=next(r for r in rels if r.get('Id')==rid)
   target=relationship.attrib['Target'];part=target.lstrip('/') if target.startswith('/') else 'xl/'+target
  else:
   sid=max(int(s.attrib['sheetId'])for s in sheets)+1
   rid='rId'+str(max([0]+[int(r.get('Id','rId0')[3:]) for r in rels if r.get('Id','').startswith('rId') and r.get('Id')[3:].isdigit()])+1)
   part=f'xl/worksheets/source_notice{sid}.xml'
   E.SubElement(sheets,'{'+M+'}sheet',{'name':'Read me','sheetId':str(sid),'{'+R+'}id':rid})
   E.SubElement(rels,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/worksheet','Target':part.removeprefix('xl/')})
   E.SubElement(types,'{'+C+'}Override',{'PartName':'/'+part,'ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
  changed={'xl/styles.xml':original_styles,'xl/workbook.xml':book,'xl/_rels/workbook.xml.rels':rels,'[Content_Types].xml':types,part:sheet}
  with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED)as out:
   for info in src.infolist():out.writestr(deepcopy(info),serialize(changed.pop(info.filename))if info.filename in changed else src.read(info.filename))
   for name,xml in changed.items():out.writestr(name,serialize(xml))
  # Data and calculation parts must be byte-identical, not merely numerically close.
  with zipfile.ZipFile(output)as out:
   for name in src.namelist():
    if name != part and name.startswith(('xl/worksheets/','xl/tables/','xl/sharedStrings')):assert out.read(name)==src.read(name),name

if __name__=='__main__':append(*map(Path,sys.argv[1:]))
