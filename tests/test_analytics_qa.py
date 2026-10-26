import importlib.util,json,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('fidelity',ROOT/'core/qa/data_fidelity.py');qa=importlib.util.module_from_spec(s);s.loader.exec_module(qa)
class FidelityTests(unittest.TestCase):
    def test_static_node_cli_uses_analyze_and_rejects_bad_input(self):
        source=json.loads((ROOT/'skill/analytics/business-performance.json').read_text(encoding='utf-8'))
        result=subprocess.run(['node',str(qa.RECOMPUTE_CLI)],input=json.dumps(source),capture_output=True,text=True,cwd=ROOT,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        output=json.loads(result.stdout)
        self.assertEqual(output['audit']['recipe'],source['recipe'])
        self.assertEqual(output['spec']['slides'][0]['type'],'cover')
        self.assertTrue(output['spec']['slides'])
        bad=subprocess.run(['node',str(qa.RECOMPUTE_CLI)],input='{not json',capture_output=True,text=True,cwd=ROOT,timeout=30)
        self.assertNotEqual(bad.returncode,0)
    def test_all_three_native_outputs_match_recomputed_source(self):
        for name,file in [('business-performance','executive-business-review'),('sales-conversion','sales-conversion-diagnostic'),('project-analytics','project-performance-review')]:
            r=qa.inspect(ROOT/f'out/analytics-regression/{name}.pptx',ROOT/f'skill/analytics/{name}.json',ROOT/f'skill/examples/{file}.json')
            self.assertEqual(r['status'],'PASS',r);self.assertGreater(r['native_cells_checked'],0);self.assertGreater(r['native_chart_values_checked'],0)
    def test_null_chart_cache_values_and_machine_epsilon_tolerance(self):
        self.assertTrue(qa.equal(None,None))
        self.assertFalse(qa.equal(None,0))
        self.assertFalse(qa.equal(0,1e-300))
        self.assertTrue(qa.equal(0.1+0.2,0.3))
        self.assertFalse(qa.equal(0.1+0.2,0.3+1e-12))
    def test_edited_spec_cannot_claim_source_fidelity(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec=json.loads((ROOT/'skill/examples/executive-business-review.json').read_text());spec['slides'][1]['items'][0]['value']='999'
            p=Path(tmp)/'spec.json';p.write_text(json.dumps(spec));r=qa.inspect(ROOT/'out/analytics-regression/business-performance.pptx',ROOT/'skill/analytics/business-performance.json',p)
            self.assertEqual(r['status'],'FAIL')
    def test_changed_native_chart_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'tampered.pptx';changed=False
            with zipfile.ZipFile(ROOT/'out/analytics-regression/business-performance.pptx') as src,zipfile.ZipFile(p,'w') as out:
                for n in src.namelist():
                    data=src.read(n)
                    if not changed and n.startswith('ppt/charts/chart') and n.endswith('.xml'):
                        root=ET.fromstring(data);v=root.find(f'.//{{{qa.C}}}numCache/{{{qa.C}}}pt/{{{qa.C}}}v');v.text='999999';data=ET.tostring(root);changed=True
                    out.writestr(n,data)
            self.assertTrue(changed);r=qa.inspect(p,ROOT/'skill/analytics/business-performance.json',ROOT/'skill/examples/executive-business-review.json');self.assertEqual(r['status'],'FAIL')
if __name__=='__main__':unittest.main()
