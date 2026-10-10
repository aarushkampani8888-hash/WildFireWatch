"""Opt-in real provider smoke tests. Never prints credentials or request URLs."""
import argparse,asyncio,base64,json,os,struct,sys,zlib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
import httpx
from backend.integrations import detect,mapbox_route
from engine import projection

def control_image():
    # Generated 128px uniform blue PNG: connectivity control, not accuracy evidence.
    def chunk(name,data):return struct.pack('!I',len(data))+name+data+struct.pack('!I',zlib.crc32(name+data)&0xffffffff)
    raw=b''.join(b'\0'+bytes((135,185,225))*128 for _ in range(128))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',128,128,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,help='Optional authorized non-sensitive JPEG/PNG/WebP sent to OpenAI; otherwise a generated blue control is used.')
    args=parser.parse_args();load_dotenv(ROOT/'.env',override=False)
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'tests':{},'limitations':['Connectivity/contract tests do not measure smoke accuracy or evacuation safety.','Mapbox requests use demonstration endpoints near Paradise, CA.']}
    for name,key in [('vision','OPENAI_API_KEY'),('mapbox','MAPBOX_ACCESS_TOKEN')]:
        if not os.environ.get(key):report['tests'][name]={'status':'blocked','reason':key+' is not configured.'};continue
        try:
            if name=='vision':
                if args.image:
                    mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}.get(args.image.suffix.lower())
                    if not mime:raise ValueError('Use PNG, JPEG, or WebP.')
                    content=args.image.read_bytes()
                    if len(content)>5_000_000:raise ValueError('Image exceeds 5 MB.')
                    evidence='operator-supplied image'
                else:mime='image/png';content=control_image();evidence='generated uniform blue connectivity control'
                result=await detect('data:'+mime+';base64,'+base64.b64encode(content).decode())
                report['tests'][name]={'status':'passed','evidence':evidence,'smoke_detected':result['smoke_detected'],'confidence':result['confidence'],'reason':result['reason'][:500]}
            else:
                result=await mapbox_route(projection(24,22,270,60))
                count=result.get('candidate_count',0)
                report['tests'][name]={'status':'passed' if count else 'failed','candidate_count':count,'route_status':result['status'],'rejected_candidates':len(result['excluded']),'selected_minutes':result['minutes'],'geometry_received':bool(result.get('geometry'))}
        except httpx.HTTPStatusError as e:report['tests'][name]={'status':'failed','reason':'Provider HTTP '+str(e.response.status_code)+'; inspect account access, billing, and token permissions.'}
        except httpx.RequestError:report['tests'][name]={'status':'failed','reason':'Provider network or timeout failure.'}
        except Exception as e:report['tests'][name]={'status':'failed','reason':str(e) if isinstance(e,ValueError) else type(e).__name__}
    output=ROOT/'docs/live-provider-report.json';output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));print('Report: '+str(output))
    return 0 if all(t['status']=='passed' for t in report['tests'].values()) else 2
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
