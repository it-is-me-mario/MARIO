"""Append an Artifact Tool-authored notice, preserving original XLSX parts.

The import/export engine cannot handle the legacy multi-axis inventories within
reasonable memory. This serializer copies their worksheets and formula caches
verbatim; all newly authored cells and styles come from Artifact Tool.

Use a namespace-preserving DOM for the edited package parts. ElementTree drops
declarations used only inside attribute values (for example mc:Ignorable and
mc:Choice/@Requires), leaving workbooks that Excel asks to repair.
"""
from copy import deepcopy
from pathlib import Path
import sys
import zipfile
from xml.dom import minidom

M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
C='http://schemas.openxmlformats.org/package/2006/content-types'
XMLNS = 'http://www.w3.org/2000/xmlns/'


def children(node, name=None):
    return [child for child in node.childNodes
            if child.nodeType == child.ELEMENT_NODE
            and (name is None or child.localName == name)]


def child(node, name):
    return next(iter(children(node, name)), None)


def imported(node, document):
    """Copy a subtree with its inherited namespace declarations intact."""
    result = document.importNode(node, deep=True)
    ancestor = node
    while ancestor.nodeType == ancestor.ELEMENT_NODE:
        for attr in ancestor.attributes.values():
            if attr.namespaceURI == XMLNS and not result.hasAttribute(attr.name):
                result.setAttributeNS(XMLNS, attr.name, attr.value)
        ancestor = ancestor.parentNode
    return result


def element(parent, namespace, name, attributes=None):
    prefix = parent.prefix if parent.namespaceURI == namespace else None
    result = parent.ownerDocument.createElementNS(
        namespace, f'{prefix}:{name}' if prefix else name)
    for key, value in (attributes or {}).items():
        result.setAttribute(key, value)
    parent.appendChild(result)
    return result


def append(original, notice, output):
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(notice) as note:
        def read(archive, part):
            return minidom.parseString(archive.read(part)).documentElement

        original_styles = read(src, 'xl/styles.xml')
        styles = read(note, 'xl/styles.xml')
        offsets, numfmt = {}, {}
        for key in ['numFmts', 'fonts', 'fills', 'borders', 'cellStyleXfs', 'cellXfs']:
            old, new = child(original_styles, key), child(styles, key)
            if new is None:
                continue
            if old is None:
                old = element(original_styles, M, key, {'count': '0'})
                original_styles.insertBefore(old, original_styles.firstChild)
            offsets[key] = len(children(old))
            for entry in children(new):
                item = imported(entry, original_styles.ownerDocument)
                if key == 'numFmts':
                    before = item.getAttribute('numFmtId')
                    after = str(max([163] + [int(x.getAttribute('numFmtId'))
                                            for x in children(old)]) + 1)
                    numfmt[before] = after
                    item.setAttribute('numFmtId', after)
                if key in ['cellStyleXfs', 'cellXfs']:
                    for attr, category in [('fontId', 'fonts'), ('fillId', 'fills'),
                                           ('borderId', 'borders'), ('xfId', 'cellStyleXfs')]:
                        if item.hasAttribute(attr):
                            item.setAttribute(attr, str(int(item.getAttribute(attr))
                                                        + offsets.get(category, 0)))
                    if item.getAttribute('numFmtId') in numfmt:
                        item.setAttribute('numFmtId', numfmt[item.getAttribute('numFmtId')])
                old.appendChild(item)
            old.setAttribute('count', str(len(children(old))))

        sheet = read(note, 'xl/worksheets/sheet1.xml')
        shared = (children(read(note, 'xl/sharedStrings.xml'), 'si')
                  if 'xl/sharedStrings.xml' in note.namelist() else [])
        for cell in sheet.getElementsByTagNameNS(M, 'c'):
            if cell.hasAttribute('s'):
                cell.setAttribute('s', str(int(cell.getAttribute('s')) + offsets['cellXfs']))
            if cell.getAttribute('t') == 's':
                value = child(cell, 'v')
                index = int(''.join(n.data for n in value.childNodes
                                    if n.nodeType == n.TEXT_NODE))
                si = imported(shared[index], sheet.ownerDocument)
                sheet.ownerDocument.renameNode(si, M, f'{si.prefix}:is' if si.prefix else 'is')
                cell.removeChild(value)
                cell.appendChild(si)
                cell.setAttribute('t', 'inlineStr')

        book = read(src, 'xl/workbook.xml')
        sheets = child(book, 'sheets')
        rels = read(src, 'xl/_rels/workbook.xml.rels')
        types = read(src, '[Content_Types].xml')
        existing = next((s for s in children(sheets) if s.getAttribute('name') == 'Read me'), None)
        if existing is not None:
            rid = existing.getAttributeNS(R, 'id')
            relationship = next(r for r in children(rels) if r.getAttribute('Id') == rid)
            target = relationship.getAttribute('Target')
            part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        else:
            sid = max(int(s.getAttribute('sheetId')) for s in children(sheets)) + 1
            ids = [r.getAttribute('Id')[3:] for r in children(rels)
                   if r.getAttribute('Id').startswith('rId')]
            rid = 'rId' + str(max([0] + [int(i) for i in ids if i.isdigit()]) + 1)
            part = f'xl/worksheets/source_notice{sid}.xml'
            added = element(sheets, M, 'sheet', {'name': 'Read me', 'sheetId': str(sid)})
            added.setAttributeNS(XMLNS, 'xmlns:r', R)
            added.setAttributeNS(R, 'r:id', rid)
            element(rels, P, 'Relationship', {'Id': rid, 'Type': R + '/worksheet',
                                             'Target': part.removeprefix('xl/')})
            element(types, C, 'Override', {'PartName': '/' + part,
                                          'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
        changed = {'xl/styles.xml': original_styles, 'xl/workbook.xml': book,
                   'xl/_rels/workbook.xml.rels': rels, '[Content_Types].xml': types, part: sheet}
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as out:
            for info in src.infolist():
                payload = (changed.pop(info.filename).ownerDocument.toxml(encoding='utf-8')
                           if info.filename in changed else src.read(info.filename))
                out.writestr(deepcopy(info), payload)
            for name, xml in changed.items():
                out.writestr(name, xml.ownerDocument.toxml(encoding='utf-8'))
        # Data and calculation parts must be byte-identical, not merely close.
        with zipfile.ZipFile(output) as out:
            for name in src.namelist():
                if name != part and name.startswith(('xl/worksheets/', 'xl/tables/',
                                                    'xl/sharedStrings', 'xl/calcChain',
                                                    'xl/metadata')):
                    assert out.read(name) == src.read(name), name


if __name__ == '__main__':
    append(*map(Path, sys.argv[1:]))
