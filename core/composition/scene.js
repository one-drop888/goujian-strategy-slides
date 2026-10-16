const kinds=new Set(['native_text','image_text','ocr','generated_annotation','source_data','derived_insight']);
function provenance(node) {
  const p=node.provenance||{kind:node.kind==='image'?'image_text':node.kind==='chart'||node.kind==='table'?'source_data':'native_text',render_mode:node.kind==='image'?'embedded':'editable'};
  if(!kinds.has(p.kind))throw Error('Unknown provenance kind: '+p.kind);
  if(['image_text','ocr'].includes(p.kind)&&(!p.source_asset||!p.source_region||typeof p.confidence!=='number'||!p.render_mode))throw Error('Image/OCR text requires source_asset, source_region, confidence and render_mode');
  return p;
}
function deduplicateSection(s,assets=[]) {
  const out=JSON.parse(JSON.stringify(s)), decisions=[];
  const number=out.number==null?null:String(out.number).padStart(2,'0');
  if(number&&out.type==='section') {
    const match=(out.title||'').match(/^\s*(\d+)\s+[\s\S]+$/);
    if(match&&Number(match[1])===Number(number)){
      out.title=out.title.replace(/^\s*\d+\s+/,'');decisions.push({action:'MERGE',roles:['section_number','title_prefix'],source:'native_text',reason:'Same section identity on the same section page',original:s.title});
    }
    if(out.section&&Number(out.section.trim())===Number(number)) {out.section='';decisions.push({action:'SUPPRESS',role:'decorative_marker',reason:'Separate section number already present'});}
  }
  const prefix=(out.title||'').match(/^\s*(\d+)\s+/);
  const used=new Set([...(out.asset_ids||[]),...(out.panels||[]).filter(p=>p.kind==='image').map(p=>p.asset_id)]);
  if(prefix)for(const asset of assets.filter(a=>used.has(a.id))) {
    for(const p of asset.provenance||[]) {
      const r=p.source_region,crop=asset.crop||{x:0,y:0,w:1,h:1};
      const visible=r&&r.x>=crop.x&&r.y>=crop.y&&r.x+r.w<=crop.x+crop.w&&r.y+r.h<=crop.y+crop.h;
      const contained=asset.crop||asset.fit==='contain'||!asset.fit&&['document_screenshot','ui_screenshot','chart_screenshot','table_screenshot','diagram'].includes(asset.type);
      // Pixel markers are kept; suppress only a corroborated native prefix in the same page context.
      if(p.semantic_role==='section_number'&&['image_text','ocr'].includes(p.kind)&&p.render_mode==='embedded'&&p.confidence>=.9&&Number(p.text)===Number(prefix[1])&&r?.x<=.25&&r?.y<=.25&&visible&&contained) {
        out.title=out.title.replace(/^\s*\d+\s+/,'');
        decisions.push({action:'KEEP',role:'section_number',source_asset:asset.id,source_region:r,source:p.kind,reason:'Embedded source marker cannot be edited independently'});
        decisions.push({action:'MERGE',role:'title_prefix',source:'native_text',original:s.title,reason:'Matching section identity, embedded provenance and top-left spatial role on this page'});
        break;
      }
    }
    if(out.title!==s.title)break;
  }
  out.deduplication=decisions;return out;
}
module.exports={provenance,deduplicateSection};
