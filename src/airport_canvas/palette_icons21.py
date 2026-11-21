"""Consistent Qt palette thumbnails for geometry, markings and sign tools."""
from PIL import Image, ImageDraw, ImageFont

SIZE = (32, 20)
INK = '#32647c'
PAVE = '#566674'
BLUE = '#b9d4e1'
YELLOW = '#ffdc6f'
WHITE = '#f4f8fb'


def structure(key):
    im = Image.new('RGBA',(72,40))
    d = ImageDraw.Draw(im)
    def line(points,color=INK,width=3):
        d.line(points,fill=color,width=width,joint='curve')
    def field(points,fill=PAVE):
        d.polygon(points,fill=fill,outline=INK,width=2)
    def arrow(x,y,color=YELLOW):
        d.polygon([(x-8,y-2),(x-1,y-2),(x-1,y-7),(x+7,y),
                   (x-1,y+7),(x-1,y+2),(x-8,y+2)],fill=color)

    if key in ('RUNWAY','STOPWAY','ROAD'):
        field([(4,5),(68,5),(68,35),(4,35)])
        if key=='STOPWAY':
            for x in (14,28,42,56):
                line([(x-4,29),(x+2,20),(x-4,11)],YELLOW)
        else:
            for x in range(12,62,13):
                line([(x,20),(x+7,20)],WHITE)
            if key=='RUNWAY':
                for y in (11,15,25,29):
                    line([(7,y),(15,y)],WHITE,2)
            else:
                for y in (9,31):
                    line([(7,y),(65,y)],WHITE,2)
    elif key=='TAXIWAY':
        line([(8,30),(27,30),(52,10),(65,10)],PAVE,13)
        line([(8,30),(27,30),(52,10),(65,10)],YELLOW,2)
        line([(28,30),(43,30),(58,35)],PAVE,11)
        line([(28,30),(43,30),(58,35)],YELLOW,2)
    elif key in ('STAND','REMOTE_STAND','AUX_STAND19','HANGAR19'):
        line([(16,5),(16,32),(56,32),(56,5)],INK,2)
        line([(36,36),(36,9)],YELLOW if key!='AUX_STAND19' else '#8c9dab')
        line([(28,14),(44,14)],INK)
        if key=='STAND':
            line([(59,8),(53,8),(46,15)],INK,5)
        elif key=='REMOTE_STAND':
            line([(30,34),(36,28),(42,34)],INK,2)
        elif key=='HANGAR19':
            line([(14,13),(36,3),(58,13)],INK,4)
        else:
            line([(7,35),(23,35)],INK,2)
    elif key.startswith('APRON') or key in ('DEICE10','TURN_PAD'):
        corners = [(6,8),(66,8),(66,34),(6,34)]
        if key in ('APRON','APRON_TRAP20_18'):
            corners = [(11,7),(61,7),(68,34),(4,34)]
        field(corners)
        if key=='DEICE10':
            for pair in ([(36,10),(36,32)],[(25,15),(47,27)],[(25,27),(47,15)]):
                line(pair,WHITE,2)
        elif key=='APRON_CARGO23':
            d.rectangle((23,13,49,30),outline=YELLOW,width=2)
            line([(36,13),(36,30)],YELLOW,2)
        elif key=='APRON_RUNUP23':
            for y in (14,22,29):
                line([(23,y),(48,y)],YELLOW,2)
            arrow(51,22)
        elif key=='TURN_PAD':
            d.arc((19,7,55,34),-100,145,fill=YELLOW,width=3)
            arrow(22,28)
        else:
            line([(12,28),(59,28)],YELLOW,2)
            for x in (23,36,49):
                line([(x,28),(x,15)],YELLOW,2)
    elif key in ('TERMINAL19','OTHER_BUILDING19','PIER19','BRIDGE19','BRIDGES19','NUMBER_BRIDGES19'):
        if key=='OTHER_BUILDING19':
            field([(15,7),(40,7),(40,33),(15,33)],BLUE)
            field([(40,16),(59,16),(59,33),(40,33)],'#e1e9ed')
            for x,y in ((22,13),(32,13),(22,21),(32,21),(48,22)):
                d.rectangle((x,y,x+4,y+4),fill=INK)
        else:
            field([(7,24),(65,24),(65,35),(7,35)],BLUE)
            if key=='TERMINAL19':
                for x in (13,26,39,52):
                    d.rectangle((x,28,x+6,31),fill=INK)
                line([(8,22),(36,8),(65,22)])
            elif key=='PIER19':
                line([(35,26),(35,6)],INK,8)
                line([(28,12),(35,5),(42,12)],YELLOW,2)
            else:
                line([(24,25),(24,9),(50,9)],INK,6)
                if key=='BRIDGES19':
                    line([(48,10),(61,19)],YELLOW)
                    line([(38,11),(47,20)],YELLOW)
                elif key=='NUMBER_BRIDGES19':
                    d.text((52,8),'1',fill=INK,font=ImageFont.load_default(size=14))
                else:
                    line([(49,9),(62,17)],YELLOW)
    elif key in ('PROTECTION','EQUIPMENT','CLOSED_AREA'):
        field([(10,6),(61,6),(61,35),(10,35)],BLUE)
        if key=='CLOSED_AREA':
            line([(24,12),(48,30)],'#ad3849',4)
            line([(24,30),(48,12)],'#ad3849',4)
        elif key=='PROTECTION':
            line([(15,27),(28,10),(40,28),(52,12)],INK,3)
        else:
            d.rectangle((24,12,47,30),outline=INK,width=2)
            line([(24,17),(47,17)])
    elif key in ('MARK:LEAD_IN','MARK:LEAD_OUT','MARK:ALIGNMENT','MARK:AUX_LEAD',
                 'MARK:ROAD_EDGE','MARK:ROAD_DIVIDER','MARK:TWY_CENTER','MARK:RWY_EDGE'):
        field([(5,8),(67,8),(67,32),(5,32)])
        if key in ('MARK:ROAD_EDGE','MARK:RWY_EDGE'):
            line([(11,13),(61,13)],WHITE,2)
            line([(11,27),(61,27)],WHITE,2)
            if key=='MARK:RWY_EDGE':
                for x in (13,30,47):
                    line([(x,20),(x+7,20)],WHITE,2)
        elif key in ('MARK:AUX_LEAD','MARK:ROAD_DIVIDER'):
            for x in (12,26,40,54):
                line([(x,20),(x+6,20)],WHITE if key=='MARK:ROAD_DIVIDER' else YELLOW,2)
        else:
            line([(12,20),(60,20)],YELLOW,2)
            if key=='MARK:LEAD_IN':
                arrow(53,20)
                line([(58,12),(58,28)],WHITE,2)
            elif key=='MARK:LEAD_OUT':
                line([(16,12),(16,28)],WHITE,2)
                arrow(55,20)
            elif key=='MARK:ALIGNMENT':
                line([(36,13),(36,27)],WHITE,2)
    elif key in ('PUSHBACK9','ENHANCED19'):
        line([(13,31),(30,31),(45,15),(60,15)],INK,4)
        if key=='ENHANCED19':
            for x in (13,21,29):
                line([(x,25),(x+4,25)],INK,2)
        else:
            arrow(59,15,INK)
    else:
        return None
    return im


def install(editor):
    from qt_core21 import C,G
    from qt_canvas21 import PhotoImage,getimage

    sections = set()
    for _, heading, content in editor._palette_groups11:
        heading.q.setProperty('acRole','paletteHeading')
        heading.q.setStyleSheet('text-align: left; padding: 6px 8px;')
        sections.add(content)
    for key,button in editor.tool_buttons.items():
        if button.master not in sections:
            continue
        button.q.setProperty('acRole','paletteTool')
        button.q.setStyleSheet('text-align: left; padding: 6px 8px;')
        im = structure(key)
        if im is None:
            im = getimage(editor.tool_icon(key)).convert('RGBA')
            if key.startswith('MARK:'):
                # Preserve the actual marking shape while giving it a common tile.
                mask = Image.new('L',im.size)
                ImageDraw.Draw(mask).rounded_rectangle((0,0,im.width-1,im.height-1),5,fill=255)
                im.putalpha(mask)
        im.thumbnail(SIZE,Image.Resampling.LANCZOS)
        cell = Image.new('RGBA',SIZE)
        cell.alpha_composite(im,((SIZE[0]-im.width)//2,(SIZE[1]-im.height)//2))
        photo = PhotoImage(cell,master=editor)
        button.configure(text=str(button.cget('text')).lstrip(' +'))
        button.q.setIcon(G.QIcon(photo.pixmap))
        button.q.setIconSize(C.QSize(*SIZE))
