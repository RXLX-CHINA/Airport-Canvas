"""Narrow, reversible migration for the Editor10 road-size and pair defaults."""
import copy

def migrate(scene):
    if scene.data['meta'].get('editor11_defaults'):return
    backup={};overrides=scene.data.get('generated_overrides',{});past=scene.past[:];future=scene.future[:]
    with scene.transaction('升级Editor11预制默认值'):
        for aid,a in scene.assets.items():
            p=a['props'];road=scene.assets.get(p.get('road_id'))
            if a['kind']=='MARKING' and road and p.get('mark_type') in ('SPEED','JET_BLAST'):
                lane=road['props']['width']/2
                if p.get('width',0)>lane*.7:
                    backup[aid]=copy.deepcopy(p);p['width']=min(1.5 if p['mark_type']=='SPEED' else .7,lane*.65)
        for aid,a in scene.assets.items():
            if a['kind']!='STAND':continue
            keys=[key for key in overrides if key.startswith('AUTO:'+aid+':') and ':STAND_NUMBER' in key]
            if not keys:continue
            old={key:copy.deepcopy(overrides[key]) for key in keys};source=overrides[keys[0]]
            if a['props'].get('lead_type')=='C':
                for key in keys:overrides[key].get('props',{}).pop('text_rotation_offset',None)
            if 'dx' in source or 'dy' in source:
                for suffix in ('STAND_NUMBER','STAND_NUMBER:1'):
                    key='AUTO:'+aid+':'+suffix;overrides.setdefault(key,{})['dx']=source.get('dx',0);overrides[key]['dy']=source.get('dy',0)
            if old:backup[aid+':number_overrides']=old
        if backup:scene.data['meta']['editor11_legacy_backup']=backup
        scene.data['meta']['editor11_defaults']=True
    scene.past=past;scene.future=future
