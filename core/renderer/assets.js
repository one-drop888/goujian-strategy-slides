const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
function createAssetPipeline(assets,specDir,tempDir,background) {
  const map=new Map((assets||[]).map(a=>[a.id,a])),used=[];
  function draw(slide,id,box,options={}) {
    const asset=map.get(id);if(!asset)throw Error('Unknown asset: '+id);
    const source=path.resolve(specDir,asset.path);
    if(!fs.statSync(source).isFile())throw Error('Not an asset file: '+asset.path);
    let result;
    try {result=JSON.parse(execFileSync('python3',[path.join(__dirname,'prepare_asset.py')],{input:JSON.stringify({asset,path:source,output:path.join(tempDir,`asset-${used.length}.png`),ratio:box.w/box.h,background,overlay:options.overlay,fit:options.fit}),encoding:'utf8',maxBuffer:1024*1024,timeout:30000}));}
    catch(e){throw Error(`Asset ${id}: ${e.stderr?.toString().trim()||e.message}. Raster images require Pillow (requirements-render.txt).`);}
    let frame={...box};
    if(options.overlay&&result.fit==='contain'&&Math.abs(result.render_ratio-box.w/box.h)>.02)throw Error('Hero crop must fill its frame before local contrast can be guaranteed; choose a split composition');
    if(result.fit==='contain') {
      const ratio=result.render_ratio, w=Math.min(box.w,box.h*ratio),h=w/ratio;
      frame={x:box.x+(box.w-w)/2,y:box.y+(box.h-h)/2,w,h};
    }
    const nodeId=options.id||`asset-${id}-${used.length}`;
    slide.addImage({path:result.path,...frame,scene:{id:nodeId,role:options.role||'evidence',asset_id:id,space:'slide',provenance:{kind:'image_text',source_asset:id,source_region:result.crop,confidence:1,render_mode:'embedded'},contrast:result.contrast,asset_type:asset.type}});
    used.push({id,...asset,width:result.width,height:result.height,aspect_ratio:result.aspect_ratio,mime:result.mime,source_sha256:result.sha256,rendered_crop:result.crop});
    if(asset.provenance)for(const p of asset.provenance)slide._scene.content_provenance.push({...p,source_asset:id});
    return {...result,frame,nodeId,asset};
  }
  return {draw,map,used};
}
module.exports={createAssetPipeline};
