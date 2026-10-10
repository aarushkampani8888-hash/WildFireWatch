from backend.investigation import temporal

def frame(minute, candidate=True, area=.1):
    return {'provider_updated_at':f'2026-10-09T03:{minute:02}:00+00:00', 'finding':{'smoke_detected':candidate,'confidence':.7 if candidate else .1,'boxes':[{'score':.7,'xyxy_normalized':[.1,.1,.1+area,.2]}] if candidate else []}}

def test_distinct_frames_and_clearing_candidate():
    result=temporal([frame(4,False),frame(3),frame(3),frame(2)])
    assert len(result['frames'])==3
    assert result['support'] and result['against']
    assert result['frames'][-1]['candidate'] is False

def test_single_frame_cannot_establish_persistence():
    result=temporal([frame(2),frame(2),{'outcome':'unchanged'},{'outcome':'error'}])
    assert len(result['frames'])==1
    assert not result['support'] and result['unknown']

def test_time_window_and_geometry_not_physical_growth():
    result=temporal([frame(1),frame(20),frame(21,area=.2)])
    assert len(result['frames'])==2
    assert any('not measured plume growth' in s for s in result['unknown'])

def test_packet_contains_sources_and_no_cross_demo_thermal(monkeypatch):
    from backend import investigation as inv, reporting
    r={'image':'data:image/png;base64,AAAA','id':'sample','demo':False,'latitude':39.82,'longitude':-121.44,'observed_at':'2021-07-22T18:30:00Z','finding':{'smoke_detected':True,'confidence':.8,'boxes':[]},'events':[]}
    monkeypatch.setattr(inv,'read',lambda _:r)
    monkeypatch.setattr(reporting,'HOTSPOTS',[])
    result=inv.packet('sample')
    assert result['thermal_observations']==[]
    assert result['fire_probability'] is None
    assert result['next_steps'] and result['unknown'] and result['nearby_cameras']

def test_packet_export_includes_original_image_only_on_request(monkeypatch):
    from backend import investigation as inv, reporting
    r={'image':'data:image/png;base64,AAAA','id':'sample','demo':False,'latitude':39.82,'longitude':-121.44,'observed_at':'2021-07-22T18:30:00Z','finding':{'smoke_detected':False,'confidence':.1,'boxes':[]},'events':[]}
    monkeypatch.setattr(inv,'read',lambda _:r);monkeypatch.setattr(reporting,'HOTSPOTS',[])
    assert inv.packet('sample')['image'] is None
    assert inv.packet('sample',True)['image']==r['image']
