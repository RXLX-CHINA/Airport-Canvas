"""PAPI plan symbols and illustrative on-slope light indications."""
import math

import scene_geometry as g


def rows(scene):
    for runway in scene.assets.values():
        if runway['kind']!='RUNWAY':continue
        props=runway['props']
        for end,settings in props.get('papi',{}).items():
            side=settings.get('side','off')
            if side=='off':continue
            axis=runway['points'] if end=='a' else runway['points'][::-1]
            length=g.length(axis)
            if length<=0:continue
            station=min(length,max(0.,settings.get('station',300.)))
            point,u=g.at(axis,station)
            normal=(-u[1],u[0])
            for sign in ((1,-1) if side=='both' else (1,) if side=='left' else (-1,)):
                offset=props['width']/2+max(1.,settings.get('offset',15.))
                lamps=[tuple(point[k]+sign*normal[k]*(offset+9*i) for k in (0,1)) for i in range(4)]
                yield runway,end,lamps,(-u[0],-u[1])


def plan_items(scene):
    for runway,_,lamps,approach in rows(scene):
        first,last=lamps[0],lamps[-1]
        length=g.length((first,last))
        along=tuple((b-a)/length for a,b in zip(first,last))
        radius=1.5
        corners=((length,1,0),(0,1,90),(0,-1,180),(length,-1,270))
        outline=[]
        for x,y,angle in corners:
            for step in range(7):
                theta=math.radians(angle+15*step)
                u=x+radius*math.cos(theta)
                v=y+radius*math.sin(theta)
                outline.append(tuple(first[k]+u*along[k]+v*approach[k] for k in (0,1)))
        yield dict(type='polygon',oid=runway['id'],points=outline,fill='#85898d')
        for x,y in lamps:
            yield dict(type='polygon',oid=runway['id'],points=[(x-1,y-1),(x+1,y-1),(x+1,y+1),(x-1,y+1)],
                       fill='#e85750',stroke='#ffffff',width=.2)
