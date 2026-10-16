import importlib.util, json, subprocess, sys, tempfile, unittest, zipfile
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
if __name__=='__main__':unittest.main()
