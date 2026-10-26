import importlib.util, json, subprocess, sys, tempfile, unittest, zipfile, hashlib
from pathlib import Path
from collections import Counter
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
geom=module('geometry','core/qa/pptx_geometry.py');fonts=module('fonts','core/qa/font_check.py');render=module('render','skill/scripts/render_deck.py')
class QualityTests(unittest.TestCase):
    def fixture(self,path):
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{geom.P}"><p:sldSz cx="12192000" cy="6858000"/></p:presentation>')
            z.writestr('ppt/slides/slide1.xml',f'<p:sld xmlns:p="{geom.P}" xmlns:a="{geom.A}"><p:cSld><p:spTree><p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="1" name="Overflow table"/></p:nvGraphicFramePr><p:xfrm><a:off x="11887200" y="914400"/><a:ext cx="914400" cy="914400"/></p:xfrm></p:graphicFrame></p:spTree></p:cSld></p:sld>')
    def test_graphic_frames_are_checked(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.pptx';self.fixture(p);r=geom.inspect(p)
            self.assertEqual(r['status'],'FAIL');self.assertEqual(r['slides'][0]['objects'],1)
    def test_missing_font_inventory_never_passes(self):
        with patch.object(fonts,'used_fonts',return_value=Counter()),patch.object(fonts,'system_families',return_value=None):self.assertEqual(fonts.inspect('unused')['status'],'UNAVAILABLE')
    def test_font_inventory_timeout_is_unavailable_not_hang(self):
        with patch.object(fonts.subprocess,'check_output',side_effect=subprocess.TimeoutExpired(['fc-list',':','family'],fonts.FONT_TIMEOUT_SECONDS)):
            self.assertIsNone(fonts.system_families())
        with patch.object(fonts,'used_fonts',return_value=Counter()),patch.object(fonts.subprocess,'check_output',side_effect=subprocess.TimeoutExpired(['fc-list'],fonts.FONT_TIMEOUT_SECONDS)):
            self.assertEqual(fonts.inspect('unused')['status'],'UNAVAILABLE')
    def test_missing_renderer_never_passes(self):
        with patch.object(render.shutil,'which',return_value=None):self.assertEqual(render.render('unused','unused')['status'],'UNAVAILABLE')
    def test_edit_refuses_source_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.pptx';self.fixture(p);old=p.read_bytes();r=Path(td)/'replacements.json';r.write_text('{"old":"new"}')
            proc=subprocess.run([sys.executable,str(ROOT/'skill/scripts/edit_pptx_text.py'),str(p),str(r),str(p)],capture_output=True)
            self.assertNotEqual(proc.returncode,0);self.assertEqual(old,p.read_bytes())
    def test_native_composition_gallery(self):
        subprocess.run(['node',str(ROOT/'tests/build_gallery.js')],cwd=ROOT,check=True,capture_output=True)
        p=ROOT/'out/composition-gallery.pptx';r=geom.inspect(p)
        self.assertEqual(r['status'],'PASS');self.assertEqual(len(r['slides']),27)
        with zipfile.ZipFile(p) as z:
            names=z.namelist();self.assertTrue(any(n.startswith('ppt/charts/chart') and n.endswith('.xml') for n in names))
            self.assertTrue(any(n.endswith('.xlsx') for n in names))
            self.assertTrue(any(n.startswith('ppt/media/') and not n.endswith('/') for n in names))
    def test_visual_attestation_is_hash_bound(self):
        with tempfile.TemporaryDirectory() as td:
            p=ROOT/'out/test-v1.pptx';r=Path(td)/'review.json';r.write_text(json.dumps({'status':'PASS','pptx_sha256':'wrong','reviewer':'test','notes':'test','slides_reviewed':list(range(1,9))}))
            out=Path(td)/'qa.json';proc=subprocess.run([sys.executable,str(ROOT/'skill/scripts/quality_gate.py'),str(p),'--out',str(out),'--visual-review',str(r)],capture_output=True)
            self.assertNotEqual(proc.returncode,0);self.assertEqual(json.loads(out.read_text())['checks']['visual_review']['status'],'FAIL')
    def test_social_preview_public_copy_hides_status_internals(self):
        import os
        from PIL import Image
        social=module('social_preview','scripts/social_preview.py')
        public=(social.TITLE,social.SUBTITLE,social.EYEBROW,*social.FOOTER_LINES)
        for line in public:
            for marker in social.STATUS_MARKERS:
                self.assertNotIn(marker.lower(),line.lower())
        sources=[]
        for index in range(3):
            relative=f'out/test-social-{os.getpid()}-{index}.png'
            Image.new('RGB',(400,225),(20+index*30,40,60)).save(ROOT/relative)
            sources.append(f'Source {index}|{relative}|1')
        try:
            with tempfile.TemporaryDirectory() as td:
                png=Path(td)/'social.png';meta_path=Path(td)/'social.json'
                args=[sys.executable,str(ROOT/'scripts/social_preview.py'),'--out',str(png),'--meta',str(meta_path)]
                for source in sources: args.extend(['--source',source])
                proc=subprocess.run(args,cwd=ROOT,capture_output=True)
                self.assertEqual(proc.returncode,0,proc.stderr.decode())
                meta=json.loads(meta_path.read_text())
                self.assertEqual(meta['review']['status'],'NOT_RUN')
                self.assertEqual(meta['sha256'],hashlib.sha256(png.read_bytes()).hexdigest())
                self.assertEqual(meta['size'],{'width':1280,'height':640})
        finally:
            for source in sources:
                (ROOT/source.split('|')[1]).unlink(missing_ok=True)
    def test_quality_gate_semantic_tamper_overrides_pass_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);spec=td/'spec.json';pptx=td/'deck.pptx'
            spec.write_text(json.dumps({'title':'Gate semantics','slides':[{'type':'chart','chartType':'column','title':'指标','labels':['本期','目标'],
                'series':[{'name':'转化率','labels':['本期','目标'],'values':[8,10]}]}]},ensure_ascii=False))
            script=("const {buildDeck}=require(%s);"
                    "buildDeck(JSON.parse(require('fs').readFileSync(%s,'utf8')),%s)"
                    ".catch(error=>{console.error(error);process.exit(1);});") % (
                json.dumps(str(ROOT/'core/renderer')),json.dumps(str(spec)),json.dumps(str(pptx)))
            subprocess.run(['node','-e',script],cwd=ROOT,check=True,capture_output=True)
            out=td/'gate.json'
            proc=subprocess.run([sys.executable,str(ROOT/'skill/scripts/quality_gate.py'),str(pptx),'--spec',str(spec),'--out',str(out)],capture_output=True)
            self.assertEqual(proc.returncode,0,proc.stderr.decode())
            baseline=json.loads(out.read_text())
            self.assertIn(baseline['checks']['semantic_qa']['status'],{'PASS','PASS_WITH_NOTES'})
            self.assertTrue((td/'gate.semantic-qa.json').exists())
            tampered=td/'tampered.pptx'
            with zipfile.ZipFile(pptx) as source,zipfile.ZipFile(tampered,'w') as target:
                for name in source.namelist():
                    data=source.read(name)
                    if name=='ppt/charts/chart1.xml':data=data.replace(b'<c:v>8</c:v>',b'<c:v>7</c:v>',1)
                    target.writestr(name,data)
            scene=td/'scene.json'
            scene.write_text(json.dumps({'status':'PASS','pptx_sha256':hashlib.sha256(tampered.read_bytes()).hexdigest(),
                'visual_encoding':{'plans':[{'status':'PASS'}]},'theme_decision':{'selected_profile':'executive-clean'}}))
            out2=td/'gate-tampered.json'
            proc=subprocess.run([sys.executable,str(ROOT/'skill/scripts/quality_gate.py'),str(tampered),'--spec',str(spec),'--scene',str(scene),'--out',str(out2)],capture_output=True)
            self.assertEqual(proc.returncode,2,proc.stderr.decode())
            result=json.loads(out2.read_text())
            self.assertEqual(result['checks']['semantic_qa']['status'],'FAIL')
            self.assertEqual(result['checks']['semantic_qa']['checks']['NUMERIC_SEMANTIC_FIDELITY']['status'],'FAIL')
            self.assertEqual(result['checks']['semantic_qa']['checks']['SIDECAR_BINDING']['status'],'PASS')
            self.assertTrue((td/'gate-tampered.semantic-qa.json').exists())
if __name__=='__main__':unittest.main()
