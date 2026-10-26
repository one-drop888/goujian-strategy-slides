import copy, importlib.util, json, runpy, subprocess, sys, tempfile, unittest
from pathlib import Path
from PIL import Image
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
spatial=load('spatial','core/qa/spatial.py');specqa=load('specqa','core/qa/spec_check.py');prepare=load('prepare','core/renderer/prepare_asset.py');ingest=load('ingest','skill/scripts/inspect_pptx.py')
caps=load('caps','core/qa/capabilities.py')

class Regression(unittest.TestCase):
    def test_invalid_schema_retains_original_diagnostics(self):
        data={'title':'Invalid chart','slides':[{'type':'chart','title':'Missing chart data'}]}
        result=subprocess.run(['node',str(ROOT/'core/schema/validate.js')],input=json.dumps(data),capture_output=True,text=True,cwd=ROOT)
        self.assertEqual(result.returncode,2)
        errors=json.loads(result.stdout)['errors']
        self.assertTrue(errors)
        self.assertEqual(specqa.check(data),[('ERROR','schema',error) for error in errors])
    def test_spec_validator_timeout_is_typed_error(self):
        with patch.object(specqa.subprocess,'run',side_effect=subprocess.TimeoutExpired(['node'],specqa.SCHEMA_TIMEOUT_SECONDS)):
            issues=specqa.check({'title':'Timeout','slides':[]})
        self.assertTrue(any(severity=='ERROR' and path=='schema' and 'timed out' in message for severity,path,message in issues))
    def test_script_and_module_entrypoints_and_legacy_shim_match(self):
        example='skill/examples/executive-review.json'
        script=subprocess.run([sys.executable,'core/qa/capabilities.py'],cwd=ROOT,capture_output=True,text=True)
        module=subprocess.run([sys.executable,'-m','core.qa.capabilities'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(script.returncode,0,script.stderr)
        self.assertEqual(module.returncode,0,module.stderr)
        self.assertEqual(json.loads(script.stdout),json.loads(module.stdout))
        outputs=[]
        for args in ([sys.executable,'skill/scripts/validate_spec.py',example],[sys.executable,'-m','skill.scripts.validate_spec',example]):
            result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            outputs.append(json.loads(result.stdout))
        shim=subprocess.run([sys.executable,'core/qa/spec-check.py',example],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(shim.returncode,0,shim.stderr)
        self.assertEqual(outputs[0],outputs[1])
        self.assertEqual(outputs[0],json.loads(shim.stdout))
        static=runpy.run_path(str(ROOT/'core/qa/spec_check.py'),run_name='spec_check_static')
        compat=runpy.run_path(str(ROOT/'core/qa/spec-check.py'),run_name='spec_check_compat')
        for name in ('TOPIC_TITLES','ACTION_WORDS','DESCRIPTIVE_OK','load_ids','title_score','check','result_for','main','json','sys','subprocess','Path','ROOT'):
            self.assertIn(name,compat)
        self.assertEqual(compat['TOPIC_TITLES'],static['TOPIC_TITLES'])
        self.assertEqual(compat['ACTION_WORDS'],static['ACTION_WORDS'])
    def test_render_capability_never_claims_visual_pass_without_tools(self):
        with patch.object(caps.shutil,'which',return_value=None):
            result=caps.detect();self.assertEqual(result['VISUAL_QA'],'UNAVAILABLE');self.assertEqual(result['levels']['3_native_render'],'UNAVAILABLE')
    def test_b_contained_screenshot_table_occlusion(self):
        graph={'slides':[{'slide':1,'nodes':[{'id':'table','role':'evidence','kind':'table','bbox':{'x':1,'y':2,'w':8,'h':4},'z':0},{'id':'shot','role':'evidence','kind':'image','bbox':{'x':2,'y':3,'w':2,'h':1},'z':1}]}]}
        result=spatial.audit(graph);self.assertEqual(result['status'],'FAIL');self.assertIn('SEMANTIC_OCCLUSION',[i['code'] for i in result['issues']])
        native=spatial.inspect(ROOT/'out/regression/occlusion.pptx');self.assertEqual(native['status'],'FAIL');self.assertIn('SEMANTIC_OCCLUSION',[i['code'] for i in native['issues']])
    def test_c_local_contrast_and_protected_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'mixed.png';im=Image.new('RGB',(20,20),'white')
            for x in range(10):
                for y in range(20):im.putpixel((x,y),(0,0,0))
            im.save(source)
            data={'asset':{'type':'background'},'path':str(source),'output':str(Path(tmp)/'prepared.png'),'ratio':1,'overlay':{'x':0,'y':0,'w':1,'h':1}}
            r=prepare.prepare(data);self.assertEqual(r['contrast']['scrim'],'000000');self.assertGreaterEqual(r['contrast']['ratio'],4.5)
            data['asset']={'type':'document_screenshot','fit':'cover'};data['ratio']=2
            with self.assertRaisesRegex(ValueError,'contrast-treated'):prepare.prepare(data)
            data.pop('overlay')
            with self.assertRaisesRegex(ValueError,'Evidence assets require contain'):prepare.prepare(data)
            data['asset'].update(allow_crop=True,safe_area={'x':0,'y':0,'w':1,'h':1})
            with self.assertRaisesRegex(ValueError,'protected evidence'):prepare.prepare(data)
    def test_f_context_aware_regional_repetition(self):
        d=json.loads((ROOT/'skill/examples/title-subtitle-layout.json').read_text());d['slides']=d['slides'][-4:]
        self.assertFalse(any('4 consecutive' in i[2] for i in specqa.check(d)))
        d['slides'][-1]['analytical_series']['task']='unrelated'
        self.assertTrue(any('4 consecutive' in i[2] for i in specqa.check(d)))
    def test_h_title_divider_collision_and_actual_native_scene(self):
        p=ROOT/'out/regression/multimodal.pptx';self.assertNotEqual(spatial.inspect(p)['status'],'FAIL')
        graph=json.loads(Path(str(p)+'.scene.json').read_text());slide=graph['slides'][1]
        title=next(n for n in slide['nodes'] if n['role']=='claim');rule=next(n for n in slide['nodes'] if n['role']=='divider');rule['bbox']['y']=title['bbox']['y']+.1
        codes=[i['code'] for i in spatial.audit(graph)['issues']];self.assertIn('TITLE_DIVIDER_COLLISION',codes)
    def test_ingestion_preserves_text_picture_table_chart_mapping(self):
        p=ROOT/'out/regression/multimodal.pptx'
        with tempfile.TemporaryDirectory() as tmp:
            report=ingest.inspect(p,tmp);objects=[o for s in report['slides'] for o in s['shapes']]
            self.assertTrue({'native_text','picture','table','chart'}<={o['kind'] for o in objects})
            self.assertTrue(all(o['source_mapping']['pptx_sha256']==report['source_sha256'] for o in objects))
            self.assertTrue(report['assets']);self.assertEqual(report['fidelity']['unresolved_assets'],[])
            self.assertTrue(any(s['relationships'] for s in report['slides']))
            self.assertTrue(any(o['kind']=='table' and len(o['rows'][0])==9 for o in objects))
            self.assertTrue(any(o['text']=='12.8%' for o in report['slides'][1]['shapes']))
    def test_overlapping_native_value_note_is_blocking(self):
        nodes=[{'id':str(i),'kind':'text','role':'evidence','text':t,'bbox':{'x':1,'y':y,'w':2,'h':.62},'z':i} for i,(t,y) in enumerate([('22%',2.55),('Target 24%',3.13)])]
        result=spatial.audit({'slides':[{'slide':1,'nodes':nodes}]});self.assertEqual(result['status'],'FAIL');self.assertIn('TEXT_TEXT_COLLISION',[i['code'] for i in result['issues']])
    def test_scene_hash_mismatch_never_passes(self):
        p=ROOT/'out/regression/multimodal.pptx'
        with tempfile.TemporaryDirectory() as tmp:
            report=json.loads(Path(str(p)+'.scene.json').read_text());report['pptx_sha256']='wrong';sidecar=Path(tmp)/'scene.json';sidecar.write_text(json.dumps(report))
            self.assertEqual(spatial.inspect(p,sidecar)['status'],'FAIL')

if __name__=='__main__':unittest.main()
