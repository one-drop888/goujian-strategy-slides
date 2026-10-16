"""Prepare local raster assets before native PPTX serialization; never edit source files."""
import hashlib, json, math, sys, warnings
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

def luminance(pixel):
    values=[v/255 for v in pixel[:3]]
    values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return .2126*values[0]+.7152*values[1]+.0722*values[2]

def prepare(data):
    asset=data['asset']; source=Path(data['path']); out=Path(data['output'])
    if source.resolve()==out.resolve():raise ValueError('Prepared output must differ from source asset')
    warnings.simplefilter('error',Image.DecompressionBombWarning)
    with Image.open(source) as original:
        if original.format not in {'PNG','JPEG','WEBP'}:raise ValueError('Only PNG, JPEG and WEBP raster assets are supported')
        if original.width*original.height>32_000_000:raise ValueError('Asset exceeds 32 megapixels; resize a derivative explicitly')
        im=ImageOps.exif_transpose(original).convert('RGBA')
        mime=Image.MIME.get(original.format)
    iw,ih=im.size
    if iw*ih>32_000_000:raise ValueError('Asset exceeds 32 megapixels; resize a derivative explicitly')
    protected=asset.get('type') in {'document_screenshot','ui_screenshot','chart_screenshot','table_screenshot','diagram'}
    if protected and (asset.get('mask','rect')!='rect' or asset.get('opacity',1)!=1):raise ValueError('Protected evidence must retain a rectangular mask and full opacity')
    fit=data.get('fit') or asset.get('fit') or ('contain' if protected else 'cover')
    region=asset.get('crop')
    crop=[0,0,1,1]
    if region:crop=[region[k] for k in ('x','y','w','h')]
    elif fit in {'cover','crop'}:
        ratio=data['ratio']; focal=asset.get('focal_point',{'x':.5,'y':.5})
        cw=min(1,ratio/(iw/ih));ch=min(1,(iw/ih)/ratio)
        crop=[min(1-cw,max(0,focal['x']-cw/2)),min(1-ch,max(0,focal['y']-ch/2)),cw,ch]
    if protected and crop!=[0,0,1,1] and not asset.get('allow_crop'):raise ValueError('Evidence assets require contain; cropping needs explicit allow_crop and safe_area')
    if protected and crop!=[0,0,1,1] and not asset.get('safe_area'):raise ValueError('Cropped evidence requires a protected safe_area')
    safe=asset.get('safe_area')
    if safe and not(crop[0]<=safe['x']+1e-6 and crop[1]<=safe['y']+1e-6 and crop[0]+crop[2]>=safe['x']+safe['w']-1e-6 and crop[1]+crop[3]>=safe['y']+safe['h']-1e-6):raise ValueError('Crop removes the protected evidence safe area')
    x,y,w,h=crop
    im=im.crop((round(x*iw),round(y*ih),round((x+w)*iw),round((y+h)*ih)))
    if im.width<1 or im.height<1:raise ValueError('Empty crop')
    if asset.get('mask','rect')!='rect':
        mask=Image.new('L',im.size,0);draw=ImageDraw.Draw(mask)
        if asset['mask']=='ellipse':draw.ellipse((0,0,im.width,im.height),fill=255)
        else:draw.rounded_rectangle((0,0,im.width,im.height),radius=min(im.size)*.05,fill=255)
        from PIL import ImageChops
        im.putalpha(ImageChops.multiply(im.getchannel('A'),mask))
    opacity=asset.get('opacity',1)
    if opacity<1:im.putalpha(im.getchannel('A').point(lambda v:round(v*opacity)))
    im.save(out)
    if region:fit='contain'
    result={'path':str(out),'width':iw,'height':ih,'aspect_ratio':iw/ih,'mime':mime,'fit':fit,'crop':dict(zip(('x','y','w','h'),crop)),'render_ratio':im.width/im.height,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    if data.get('overlay'):
        r=data['overlay'];bg=data.get('background','FFFFFF')
        composite=Image.new('RGBA',im.size,'#'+bg);composite.alpha_composite(im);composite=composite.convert('RGB')
        sample=composite.crop((round(r['x']*im.width),round(r['y']*im.height),round((r['x']+r['w'])*im.width),round((r['y']+r['h'])*im.height)))
        sample.thumbnail((160,160));pixels=sample.get_flattened_data() if hasattr(sample,'get_flattened_data') else sample.getdata();ls=[luminance(p) for p in pixels]
        # Lower percentile avoids declaring a mixed light/dark photograph uniformly readable.
        white=sorted(1.05/(v+.05) for v in ls);black=sorted((v+.05)/.05 for v in ls)
        low=max(0,math.floor(len(ls)*.01)-1);wc,bc=white[low],black[low]
        if max(wc,bc)>=4.5:result['contrast']={'color':'FFFFFF' if wc>=bc else '000000','ratio':max(wc,bc),'scrim':None,'sample':'local 1st percentile'}
        else:result['contrast']={'color':'FFFFFF','ratio':21,'scrim':'000000','sample':'local opaque scrim required; source contrast insufficient'}
    return result

if __name__=='__main__':
    try:print(json.dumps(prepare(json.load(sys.stdin))))
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(2)
