"""Explicit, atomic import adapters; keep legacy scripts available unchanged."""
import json
import math
from pathlib import Path
from airport_scene import PATH_KINDS
import scene_geometry as g

def import_legacy(scene,path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    created=[];notes=[]
    if not isinstance(data,dict):raise ValueError('Configuration must be a JSON object')
    with scene.transaction('导入旧版参数'):
        if all(key in data for key in ('length','width','level','ma')):
            from runway import Runway
            import inspect
            keys=set(inspect.signature(Runway).parameters)
            unknown=set(data)-keys-{'bg','stopwaybg'}
            if unknown:raise ValueError('Unknown runway keys: '+','.join(sorted(unknown)))
            r=Runway(**{k:v for k,v in data.items() if k in keys})
            # Screen rotation in old renderer is converted explicitly to local north/east.
            heading=(r.large_heading+180)%360
            points=g.line([0,0],r.length,heading)
            aid=scene.create_asset('RUNWAY',f'{r.designator_small:02}{r.suffix_small} / {r.designator_large:02}{r.suffix_large}',points,
                width=r.width,shoulder=r.shoulder,code_number=r.fa_indicator_I,maxspan=r.maxspan,
                label_a=f'{r.designator_small:02}{r.suffix_small}',label_b=f'{r.designator_large:02}{r.suffix_large}',
                level_a=r.level,level_b=r.level,displaced_a=r.ld,displaced_b=r.hd,lda_a=r.ald_small,lda_b=r.ald_large,
                legacy_parameters=data,source_note='旧版导入；朝向为本地设计，不是已核实的真实地理方位。')
            created.append(aid)
            notes.append('完整旧参数保存在资产 legacy_parameters 中；物理A端绑定小号端，后续号码变化不交换端点。')
            if r.lturnover or r.hturnover or r.shouldermark:notes.append('旧掉头坪/道肩示意参数已保留，但不作为统一场景已核验设施生成。')
        elif all(key in data for key in ('direction','length','width')):
            from taxiway import Taxiway,TaxiwayDraw
            root=Taxiway.from_dict(data);records=TaxiwayDraw(root).layout();mapping={}
            for i,record in enumerate(records):
                obj=record['taxiway'];points=[[x,-y] for x,y in record['points']]
                aid=scene.create_asset('TAXIWAY',f'导入滑行道 {i+1}',points,width=obj.width,code_number=obj.code_number,
                    min_radius=obj.turn_radius,legacy_screen_direction=obj.direction,
                    legacy_source=data if i==0 else None,source_note='原direction为屏幕角，已显式转换Y轴。')
                created.append(aid);mapping[id(obj)]=aid
            def link(parent):
                for c in parent.children:
                    child=c['taxiway'];parent_id=mapping[id(parent)];child_id=mapping[id(child)]
                    # The legacy child already contains the curve. Connect at its coincident beginning;
                    # retain an explicit topological zero-distance attachment rather than invent a loop.
                    s=parent.resolve_position(c['position'])
                    mid=scene.connect(dict(asset=parent_id,station=s,direction=1),dict(asset=child_id,station=0.,direction=1),
                        'TAXIWAY_JOIN',parent_id+' / '+child_id,width=child.width,bidirectional=True,handle=1)
                    scene.movements[mid]['source_note']='旧树附着点：零长度拓扑连接，曲线已在子路段内。'
                    scene.movements[mid]['legacy_attachment']=True
                    link(child)
            link(root);notes.append('已将旧children展开为路线资产和显式连接，原曲线及原参数保留。')
        else:raise ValueError('Unrecognized legacy JSON. Use Open Scene for .airport.json files.')
    return dict(asset_ids=created,message='\n'.join(notes))
