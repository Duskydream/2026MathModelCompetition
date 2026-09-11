"""Read original files without changing them. Run with bundled Python."""
from pathlib import Path
import hashlib, json, struct, zipfile
from lxml import etree as E
from pypdf import PdfReader
import pypdfium2

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / 'source_extract'
OUT.mkdir(exist_ok=True)

def legacy_doc_text(path):
    b = path.read_bytes()
    u16 = lambda off: struct.unpack_from('<H', b, off)[0]
    u32 = lambda off: struct.unpack_from('<I', b, off)[0]
    size = 1 << u16(30)
    sector = lambda n: b[(n+1)*size:(n+2)*size]
    difat = list(struct.unpack_from('<109I', b, 76))
    ds = u32(68)
    for _ in range(u32(72)):
        row = struct.unpack('<'+'I'*(size//4), sector(ds))
        difat.extend(row[:-1]); ds = row[-1]
    fat=[]
    for sid in difat:
        if sid < 0xfffffffa: fat.extend(struct.unpack('<'+'I'*(size//4),sector(sid)))
    def chain(sid, table=fat):
        out=[]; seen=set()
        while sid < 0xfffffffa:
            if sid in seen: raise ValueError('CFB cycle')
            seen.add(sid);out.append(sid);sid=table[sid]
        return out
    directory=b''.join(sector(s) for s in chain(u32(48)))
    entries={}
    for k in range(0,len(directory),128):
        e=directory[k:k+128]; n=struct.unpack_from('<H',e,64)[0]
        if n:
            name=e[:n-2].decode('utf-16le');entries[name]=(e[66],struct.unpack_from('<I',e,116)[0],struct.unpack_from('<Q',e,120)[0])
    root=next(v for v in entries.values() if v[0]==5)
    mini=b''.join(sector(s) for s in chain(root[1]))[:root[2]]
    mf=b''.join(sector(s) for s in chain(u32(60)))
    minifat=struct.unpack('<'+'I'*(len(mf)//4),mf)
    def stream(name):
        _,sid,n=entries[name]
        if n>=u32(56): return b''.join(sector(s) for s in chain(sid))[:n]
        ms=1<<u16(32)
        return b''.join(mini[s*ms:(s+1)*ms] for s in chain(sid,minifat))[:n]
    w=stream('WordDocument');flags=struct.unpack_from('<H',w,10)[0]
    tab=stream('1Table' if flags & 0x200 else '0Table')
    pos=32;csw=struct.unpack_from('<H',w,pos)[0];pos+=2+2*csw
    cslw=struct.unpack_from('<H',w,pos)[0];pos+=2+4*cslw
    pairs=pos+2;fc,lcb=struct.unpack_from('<II',w,pairs+33*8)
    clx=tab[fc:fc+lcb];i=0
    while clx[i]==1:i+=3+struct.unpack_from('<H',clx,i+1)[0]
    assert clx[i]==2
    length=struct.unpack_from('<I',clx,i+1)[0];plc=clx[i+5:i+5+length];n=(length-4)//12
    cps=struct.unpack_from('<'+'I'*(n+1),plc,0);parts=[]
    for j in range(n):
        f=struct.unpack_from('<I',plc,4*(n+1)+8*j+2)[0];compressed=bool(f&0x40000000);f&=0x3fffffff
        count=cps[j+1]-cps[j]
        if compressed:f//=2;parts.append(w[f:f+count].decode('cp1252'))
        else:parts.append(w[f:f+2*count].decode('utf-16le'))
    return ''.join(parts).replace('\r','\n').replace('\x07','\t')

manifest=[]
for f in sorted((ROOT/'Question B').rglob('*')):
    if not f.is_file():continue
    record={'path':str(f.relative_to(ROOT)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
    if f.suffix=='.pdf':
        pdf=PdfReader(f);record['pages']=len(pdf.pages)
        text='\n'.join(f'=== PAGE {i+1} ===\n'+p.extract_text() for i,p in enumerate(pdf.pages))
        render=pypdfium2.PdfDocument(f)
        for i in range(len(render)):render[i].render(scale=1.5).to_pil().save(OUT/f'question_{i+1}.png')
    elif f.suffix=='.docx':
        z=zipfile.ZipFile(f);r=E.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
        text='\n'.join(''.join(p.xpath('.//w:t/text()|.//m:t/text()',namespaces=ns)) for p in r.xpath('//w:p',namespaces=ns))
        record.update(tables=len(r.xpath('//w:tbl',namespaces=ns)),media=[x for x in z.namelist() if x.startswith('word/media/')],math_objects=len(r.xpath('//m:oMath',namespaces=ns)),tracked_changes=len(r.xpath('//w:ins|//w:del',namespaces=ns)))
    elif f.suffix=='.doc':text=legacy_doc_text(f)
    else:raise ValueError(f)
    (OUT/(f.stem+'.txt')).write_text(text,encoding='utf-8');manifest.append(record)
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
