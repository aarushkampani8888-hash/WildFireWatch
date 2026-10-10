"""Traceable investigation evidence; deterministic screening, not confirmation."""
from datetime import datetime
from backend.reporting import read, distance, reports as list_reports

def temporal(frames):
    usable = sorted([f for f in frames if f.get('finding') and f.get('provider_updated_at')], key=lambda f:f['provider_updated_at'])[-6:]
    # Repeated provider timestamps cannot count as independent observations.
    unique = {f['provider_updated_at']:f for f in usable}
    usable = list(unique.values())
    if usable:
        latest = datetime.fromisoformat(usable[-1]['provider_updated_at'])
        usable = [f for f in usable if (latest-datetime.fromisoformat(f['provider_updated_at'])).total_seconds() <= 600]
    rows=[]
    for f in usable:
        boxes=[b['xyxy_normalized'] for b in f['finding'].get('boxes',[]) if b['score']>=.25]
        b=max(boxes,key=lambda b:(b[2]-b[0])*(b[3]-b[1])) if boxes else None
        rows.append({'time':f['provider_updated_at'],'score':f['finding']['confidence'],'candidate':f['finding']['smoke_detected'], 'box':b,'area':(b[2]-b[0])*(b[3]-b[1]) if b else 0})
    support=[]; against=[]; unknown=[]
    positives=sum(r['candidate'] for r in rows)
    if len(rows)<2:unknown.append('At least two distinct recent frames are needed for temporal comparison.')
    elif positives>=2:support.append(f'Candidate detected in {positives}/{len(rows)} distinct frames in a ten-minute window; persistence alone cannot distinguish smoke from a fixed light or cloud.')
    if len(rows)>=2 and rows[-2]['candidate'] and not rows[-1]['candidate']:against.append('Latest frame falls below threshold after a candidate; this weakens persistence but does not rule out a fire.')
    if len(rows)>=2 and rows[-2]['box'] and rows[-1]['box']:
        a,b=rows[-2],rows[-1]
        change=(b['area']/a['area']-1)*100 if a['area'] else 0
        shift=((b['box'][0]+b['box'][2]-a['box'][0]-a['box'][2])/2,(b['box'][1]+b['box'][3]-a['box'][1]-a['box'][3])/2)
        unknown.append(f'Largest candidate box area changed {change:+.0f}%; image-plane center shifted {shift[0]*100:+.1f}% horizontally / {shift[1]*100:+.1f}% vertically. Boxes may represent different objects; this is not measured plume growth or geographic motion.')
    return {'frames':rows,'support':support,'against':against,'unknown':unknown,'note':'Six distinct frames at most, ten-minute window. Image-plane comparison, no object identity or calibrated fire probability.'}

def packet(report_id, include_image=False, submissions=None):
    from backend.live_camera import monitor, CAMERAS
    r=read(report_id)
    from backend.reporting import HOTSPOTS, DEMO_HOTSPOTS
    observed=datetime.fromisoformat(r['observed_at'].replace('Z','+00:00'))
    matches=[]
    for h in ([] if r.get('reference') else (DEMO_HOTSPOTS if r['demo'] else HOTSPOTS)):
        hours=abs((observed-datetime.fromisoformat(h['observed_at'].replace('Z','+00:00'))).total_seconds())/3600
        km=distance(r,h)
        if hours<=24 and km<=25:matches.append(dict(h,distance_km=round(km,2),time_difference_hours=round(hours,2)))
    r['matches']=matches
    video=r.get('video_evidence')
    stored=r.get('temporal',{'frames':[],'support':[],'against':[],'unknown':[
        'Video sampling covers only selected frames; unsampled moments may contain smoke.'
        if video else 'Single submitted image; temporal behavior is unknown.']})
    support=list(stored['support']);against=list(stored['against']);unknown=list(stored['unknown'])
    if r['finding']['smoke_detected']:
        support.append('Trained YOLO detector found a smoke candidate; score is uncalibrated.')
        if video:support.append(f"Candidate found in {video['frames_flagged']}/{video['frames_analyzed']} sampled video frames; this does not confirm continuous smoke or fire.")
    else:against.append('No smoke above detector threshold in the sampled evidence; false negatives remain possible.')
    if r.get('matches'):support.append(f"{len(r['matches'])} nearby thermal observations match the time/distance filter; these do not prove a common fire.")
    else:unknown.append('No loaded thermal corroboration. Missing detections do not disprove a fire.')
    unknown.extend(['Ignition location and smoke identity are unverified.','Current geographic context describes the observer, not the candidate pixels.'])
    cameras=sorted([dict(c,distance_km=round(distance(r,c),1)) for c in CAMERAS if c['id']!=r.get('provenance',{}).get('id')],key=lambda c:c['distance_km'])
    # Nearby submissions are possible corroboration only. Exclude the same
    # camera source so repeated frames are not presented as independent views.
    nearby_reports=[]
    if not r.get('reference') and not r.get('demo'):
        for other in (submissions if submissions is not None else list_reports()):
            if other['id']==r['id'] or other.get('reference') or other.get('demo'):
                continue
            source_id=(r.get('provenance') or {}).get('id')
            other_source=(other.get('provenance') or {}).get('id')
            if source_id and source_id==other_source:
                continue
            other_time=datetime.fromisoformat(other['observed_at'].replace('Z','+00:00'))
            hours=abs((observed-other_time).total_seconds())/3600
            km=distance(r,other)
            if hours<=24 and km<=25:
                nearby_reports.append({
                    'id':other['id'], 'latitude':other['latitude'], 'longitude':other['longitude'], 'observed_at':other['observed_at'],
                    'distance_km':round(km,1), 'time_difference_hours':round(hours,1),
                    'source':(other.get('provenance') or {}).get('name') or ('Community video' if other.get('video_evidence') else 'Community photo'),
                    'finding':other['finding'], 'status':other['status'],
                })
        nearby_reports.sort(key=lambda item:(item['distance_km'],item['time_difference_hours']))
        nearby_reports=nearby_reports[:5]
        if nearby_reports:
            unknown.append(f'{len(nearby_reports)} other report(s) fall within 25 km / 24 hours; proximity does not establish a shared event.')
    if r.get('reference'):
        cameras=[]
        unknown.append('Reference photo: original capture location/time unknown; test coordinates are excluded from satellite matching.')
    steps=(['Inspect the original photo and possible confounders.','Record whether the detector result agrees with your visual assessment.','Record a human decision; reference coordinates cannot corroborate a real incident.'] if r.get('reference') else (['Review the original clip and sampled frames; smoke may appear between samples.','Inspect another camera or independent report; coverage is not established.','Record a human decision with reasons. No emergency notification is sent.'] if video else ['Inspect successive frames for persistence and cloud/light confounders.','Check a nearby camera; overlapping fields of view are not established.','Load geographic/weather context and import recent FIRMS observations.','Record a human decision with reasons. No automated emergency notification is sent.']))
    video_summary={k:v for k,v in video.items() if k!='frames'}|({'frames':[{k:v for k,v in frame.items() if k!='image'} for frame in video['frames']]} if video else {}) if video else None
    return {'reference':r.get('reference',False),'image':r['image'] if include_image else None,'report_id':r['id'],'demo':r['demo'],'observation':{k:r.get(k) for k in ['latitude','longitude','observed_at','direction','location_role','provenance']},'finding':r['finding'],'thermal_observations':matches,'nearby_reports':nearby_reports,'temporal':stored,'video_evidence':video_summary,'support':support,'against':against,'unknown':unknown,'next_steps':steps,'nearby_cameras':cameras,'review':r.get('review'),'events':r['events'],'fire_probability':None}
