"""Layered exports using the same paint commands as PNG."""
from itertools import groupby
from io import BytesIO
from pathlib import Path
from struct import pack
from tempfile import TemporaryFile
from xml.sax.saxutils import quoteattr
from zipfile import ZIP_DEFLATED, ZipFile
import zlib

from PIL import Image
from map_painter import draw_items


def layer_kind(row):
    if row['oid'].startswith('F8_PAGE:') or row['oid']=='EXPORT_SCALE':
        return 'Chart furniture'
    if row.get('lamp_center'):
        return 'Lights'
    if row.get('draw_band')=='surface':
        return 'Pavement'
    if row['type']=='text':
        return 'Labels'
    return 'Geometry and markings'


def render_layers(items,size,origin,scale,background,progress):
    # Only adjacent runs are merged so interleaved labels and geometry keep their paint order.
    groups=[(name,list(rows)) for name,rows in groupby(items,key=layer_kind)]
    if len(groups)>100:
        # Most interleaving is generated text on markings. Preserve stack order
        # by joining adjacent object runs where fine-grained layers are impractical.
        groups=[(name,list(rows)) for name,rows in groupby(items,key=lambda r:
                'Objects and labels' if layer_kind(r) in ('Geometry and markings','Labels') else layer_kind(r))]
    emitted=False
    if background is not None:
        emitted=True
        yield 'Background',(0,0),Image.new('RGBA',size,background)
    counts={}
    for i,(name,rows) in enumerate(groups):
        if progress:progress(10+75*i/max(1,len(groups)),'Rendering export layers')
        image=draw_items(rows,size,origin,scale,(0,0,0,0))
        bounds=image.getbbox()
        if bounds:
            emitted=True
            counts[name]=counts.get(name,0)+1
            title=name if counts[name]==1 else f'{name} {counts[name]}'
            yield title,bounds[:2],image.crop(bounds)
        image.close()
    if not emitted:yield 'Empty drawing',(0,0),Image.new('RGBA',(1,1))


def write_psd(path,size,layers,progress):
    width,height=size
    records=[]
    locations=[]
    with TemporaryFile() as storage, Image.new('RGBA',size) as composite:
        for name,(x,y),image in layers:
            with image:
                composite.alpha_composite(image,(x,y))
                w,h=image.size
                name_bytes=name.encode('ascii')[:255]
                pascal=bytes([len(name_bytes)])+name_bytes
                extra=bytes(8)+pascal+bytes(-len(pascal)%4)
                record=pack('>4iH',y,x,y+h,x+w,4)
                for channel in (0,1,2,-1):
                    record+=pack('>hI',channel,2+w*h)
                records.append(record+b'8BIMnorm\xff\0\0\0'+pack('>I',len(extra))+extra)
                locations.append((storage.tell(),4*(2+w*h)))
                for name in 'RGBA':
                    with image.getchannel(name) as channel:
                        storage.write(b'\0\0')
                        storage.write(channel.tobytes())
        if len(records)>32767:raise ValueError('Too many PSD layers')
        info_len=2+sum(map(len,records))+storage.tell()
        if info_len>=2**31-8:raise ValueError('PSD layer data exceeds the format limit. Reduce the export width.')
        with Path(path).open('wb') as stream:
            stream.write(pack('>4sH6xHIIHH',b'8BPS',1,4,height,width,8,3))
            stream.write(pack('>IIIIh',0,0,4+info_len+(info_len%2)+4,info_len+(info_len%2),-len(records)))
            for record in reversed(records):stream.write(record)
            for index,(offset,length) in enumerate(reversed(locations)):
                if progress:progress(85+10*(index+1)/max(1,len(records)),'Writing PSD layers')
                storage.seek(offset)
                while length:
                    block=storage.read(min(length,1024*1024))
                    stream.write(block)
                    length-=len(block)
            stream.write(bytes(info_len%2)+bytes(4)+bytes(2))
            for channel in composite.split():
                with channel:stream.write(channel.tobytes())


def write_pdf(path,size,layers,dpi):
    page_width,page_height=(n*72/dpi for n in size)
    with Path(path).open('wb') as stream:
        stream.write(b'%PDF-1.5\n%\xe2\xe3\xcf\xd3\n')
        offsets=[0,0,0,0,0]

        def write_object(payload,number=None):
            if number is None:
                number=len(offsets)
                offsets.append(0)
            offsets[number]=stream.tell()
            stream.write(f'{number} 0 obj\n'.encode()+payload+b'\nendobj\n')
            return number

        def pdf_stream(settings,data):
            return f'<< {settings} /Length {len(data)} >>\nstream\n'.encode()+data+b'\nendstream'

        groups=[]
        images=[]
        operations=[]
        for index,(title,(x,y),image) in enumerate(layers):
            w,h=image.size
            group=write_object(f'<< /Type /OCG /Name ({title}) >>'.encode())
            groups.append(f'{group} 0 R')
            header=f'/Type /XObject /Subtype /Image /Width {w} /Height {h} /BitsPerComponent 8 /Filter /FlateDecode'
            alpha=write_object(pdf_stream(header+' /ColorSpace /DeviceGray',zlib.compress(image.getchannel('A').tobytes())))
            rgb=write_object(pdf_stream(header+f' /ColorSpace /DeviceRGB /SMask {alpha} 0 R',zlib.compress(image.convert('RGB').tobytes())))
            images.append(f'/I{index} {rgb} 0 R')
            operations.append(f'/OC /L{index} BDC q {w*72/dpi:.7f} 0 0 {h*72/dpi:.7f} {x*72/dpi:.7f} {(size[1]-y-h)*72/dpi:.7f} cm /I{index} Do Q EMC')
            image.close()
        listing=' '.join(groups)
        properties=' '.join(f'/L{i} {key}' for i,key in enumerate(groups))
        write_object(f'<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [{listing}] /D << /Order [{listing}] /BaseState /ON >> >> >>'.encode(),1)
        write_object(b'<< /Type /Pages /Count 1 /Kids [3 0 R] >>',2)
        write_object(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] /Resources << /XObject << {" ".join(images)} >> /Properties << {properties} >> >> /Contents 4 0 R >>'.encode(),3)
        write_object(pdf_stream('', '\n'.join(operations).encode()),4)
        xref=stream.tell()
        stream.write(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
        for offset in offsets[1:]:stream.write(f'{offset:010d} 00000 n \n'.encode())
        stream.write(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())


PART='http://schemas.openxmlformats.org/package/2006/'
OFFICE='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
MAIN='http://schemas.openxmlformats.org/presentationml/2006/main'
DRAW='http://schemas.openxmlformats.org/drawingml/2006/main'
NS=f'xmlns:p="{MAIN}" xmlns:a="{DRAW}" xmlns:r="{OFFICE}"'
ROOT_GROUP='<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
PPT_TYPE='application/vnd.openxmlformats-officedocument.presentationml.'


def relationships(entries):
    return f'<Relationships xmlns="{PART}relationships">'+''.join(
        f'<Relationship Id="rId{i}" Type="{OFFICE}/{kind}" Target="{target}"/>'
        for i,(kind,target) in enumerate(entries,1))+'</Relationships>'


def pptx_theme():
    colours={'dk1':'000000','lt1':'FFFFFF','dk2':'20354A','lt2':'EEF3F7',
             'accent1':'207390','accent2':'4E83A2','accent3':'FFD868',
             'accent4':'64758C','accent5':'44685B','accent6':'B84D5A',
             'hlink':'0563C1','folHlink':'954F72'}
    scheme=''.join(f'<a:{name}><a:srgbClr val="{value}"/></a:{name}>' for name,value in colours.items())
    fill='<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    line='<a:ln w="9525">'+fill+'</a:ln>'
    face='<a:latin typeface="Arial"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Arial"/>'
    return (f'<a:theme xmlns:a="{DRAW}" name="Airport Canvas"><a:themeElements>'
            f'<a:clrScheme name="Airport Canvas">{scheme}</a:clrScheme>'
            f'<a:fontScheme name="Airport Canvas"><a:majorFont>{face}</a:majorFont>'
            f'<a:minorFont>{face}</a:minorFont></a:fontScheme>'
            f'<a:fmtScheme name="Airport Canvas"><a:fillStyleLst>{fill*3}</a:fillStyleLst>'
            f'<a:lnStyleLst>{line*3}</a:lnStyleLst>'
            '<a:effectStyleLst>'+('<a:effectStyle><a:effectLst/></a:effectStyle>'*3)+'</a:effectStyleLst>'
            f'<a:bgFillStyleLst>{fill*3}</a:bgFillStyleLst></a:fmtScheme>'
            '</a:themeElements></a:theme>')


def write_pptx(path,size,layers):
    width,height=size
    # Fit the whole chart on one slide, preserving its aspect ratio.
    scale=914400*min(12/width,12/height)
    sw,sh=(max(914400,round(n*scale)) for n in size)
    dx,dy=(sw-width*scale)/2,(sh-height*scale)/2
    with ZipFile(path,'w',ZIP_DEFLATED) as doc:
        pictures=[]
        entries=[('slideLayout','../slideLayouts/slideLayout1.xml')]
        for index,(title,(x,y),image) in enumerate(layers,2):
            filename=f'image{index}.png'
            entries.append(('image','../media/'+filename))
            with BytesIO() as picture:
                image.save(picture,'PNG')
                doc.writestr('ppt/media/'+filename,picture.getvalue())
            w,h=image.size
            image.close()
            pictures.append(f'<p:pic><p:nvPicPr><p:cNvPr id="{index}" name={quoteattr(title)}/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId{index}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{round(x*scale+dx)}" y="{round(y*scale+dy)}"/><a:ext cx="{max(1,round(w*scale))}" cy="{max(1,round(h*scale))}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
        types={'presentation.xml':'presentation.main','slides/slide1.xml':'slide',
               'slideLayouts/slideLayout1.xml':'slideLayout','slideMasters/slideMaster1.xml':'slideMaster'}
        doc.writestr('ppt/theme/theme1.xml',pptx_theme())
        overrides='<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'+''.join(f'<Override PartName="/ppt/{name}" ContentType="{PPT_TYPE}{kind}+xml"/>' for name,kind in types.items())
        doc.writestr('[Content_Types].xml',f'<Types xmlns="{PART}content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>{overrides}</Types>')
        doc.writestr('_rels/.rels',relationships([('officeDocument','ppt/presentation.xml')]))
        doc.writestr('ppt/_rels/presentation.xml.rels',relationships([('slide','slides/slide1.xml'),('slideMaster','slideMasters/slideMaster1.xml')]))
        doc.writestr('ppt/presentation.xml',f'<p:presentation {NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId2"/></p:sldMasterIdLst><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst><p:sldSz cx="{sw}" cy="{sh}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
        doc.writestr('ppt/slides/_rels/slide1.xml.rels',relationships(entries))
        doc.writestr('ppt/slides/slide1.xml',f'<p:sld {NS}><p:cSld><p:spTree>{ROOT_GROUP}{"".join(pictures)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')
        doc.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels',relationships([('slideMaster','../slideMasters/slideMaster1.xml')]))
        doc.writestr('ppt/slideLayouts/slideLayout1.xml',f'<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="Blank"><p:spTree>{ROOT_GROUP}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
        doc.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels',relationships([('slideLayout','../slideLayouts/slideLayout1.xml'),('theme','../theme/theme1.xml')]))
        doc.writestr('ppt/slideMasters/slideMaster1.xml',f'<p:sldMaster {NS}><p:cSld><p:spTree>{ROOT_GROUP}</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>')


def write(path,kind,items,size,origin,scale,background,dpi,progress):
    if kind=='psd' and max(size)>30000:raise ValueError('PSD supports a maximum of 30,000 pixels on each side.')
    layers=render_layers(items,size,origin,scale,background,progress)
    if kind=='psd':write_psd(path,size,layers,progress)
    elif kind=='pdf':write_pdf(path,size,layers,dpi)
    else:write_pptx(path,size,layers)
