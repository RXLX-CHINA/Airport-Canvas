"""Use installed fonts without assuming every host is Windows."""
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=8)
def font_path(style):
    if style=='stencil':return Path(__file__).with_name('AllertaStencil-Regular.ttf')
    if style=='caac':return Path(__file__).with_name('CAAC_Runway_Code_Font.ttf')
    candidates=([Path('C:/Windows/Fonts/simhei.ttf')] if style=='hei' else [])+[Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    return next((p for p in candidates if p.is_file()),candidates[0])
