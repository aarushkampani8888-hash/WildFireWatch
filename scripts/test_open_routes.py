import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.open_routes import open_route
from engine import projection
async def main():
    route=await open_route(projection(24,22,270,60))
    report={k:v for k,v in route.items() if k!='geometry'};report['geometry_points']=len(route.get('geometry',[]))
    Path('docs/open-route-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':asyncio.run(main())
