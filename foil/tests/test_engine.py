import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import run,inside,NODES
class PipelineTests(unittest.TestCase):
    def test_route_avoids_hazard(self):
        r=run({}); p=next(p for p in r['projections'] if p['minutes']==60)
        self.assertTrue(r['route']['path'])
        for a,b in zip(r['route']['path'],r['route']['path'][1:]):
            for i in range(101): self.assertFalse(inside((NODES[a][0]+(NODES[b][0]-NODES[a][0])*i/100,NODES[a][1]+(NODES[b][1]-NODES[a][1])*i/100),p))
    def test_closure_changes_route(self):
        self.assertNotEqual(run({})['route']['path'],run({'closures':['junction-south']})['route']['path'])
    def test_no_route(self):
        self.assertEqual(run({'closures':['community-junction','community-west']})['route']['status'],'no_route')
    def test_no_detection(self):
        r=run({}, {'smoke_detected':False,'confidence':.2,'reason':'Clear sky','source':'test'})
        self.assertEqual(r['projections'],[]);self.assertEqual(r['route']['status'],'no_detection')
    def test_invalid_input(self):
        for x in [{'wind':-1},{'humidity':110},{'horizon':7},{'direction':float('nan')}]:
            with self.assertRaises(ValueError):run(x)
    def test_wind_changes_spread(self):
        self.assertGreater(run({'wind':70})['projections'][1]['a'],run({'wind':5})['projections'][1]['a'])
if __name__=='__main__':unittest.main()
