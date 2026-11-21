"""Editor 8 uses the shared, corrected marking geometry for canvas and export."""
from pathlib import Path
from airport_scene import AirportScene
from editor7_gui import Editor7

class Editor8(Editor7):
    def __init__(self,scene=None):
        if scene is None:scene=AirportScene.load(Path(__file__).with_name('example_editor8.airport.json'))
        super().__init__(scene)
    def update_title(self):
        super().update_title();self.title(self.title().replace('7.0','8.0'))

def main():
    app=Editor8();app.mainloop()

if __name__=='__main__':main()
