"""UI vocabulary. Project data and markings use their original identifiers."""
EN = {
    '文件':'File','编辑':'Edit','视图':'View','显示':'View','设置':'Settings','帮助':'Help',
    '信息引导':'Guidance Signs','语言 / Language':'Language / 语言',
    '关闭类型':'Closure Type','关闭道面':'Close Pavement','道面状态':'Pavement Status',
    '临时关闭':'Temporary Closure','永久关闭':'Permanent Closure',
    '新建':'New','打开':'Open','保存':'Save','另存为':'Save As','退出':'Exit',
    '撤销':'Undo','重做':'Redo','删除':'Delete','取消':'Cancel','确定':'OK','应用':'Apply',
    '选择':'Select','连续绘制':'Continuous Drawing','深色模式':'Dark Mode',
    '机场基准点':'Aerodrome Reference Point','自动定位 ARP':'Locate ARP Automatically',
    '机场基准点 / 定位':'Aerodrome Reference Point / Placement','热点工具 / 形状':'Hot Spot Tool / Shape',
    '风向标':'Wind Direction Indicator','热点':'Hot Spot','航图工具':'Chart Tools',
    '航图排版':'Chart Layout','航图配色':'Chart Colours','航图模式 · F8':'Chart Mode · F8',
    '绘制工具':'Drawing Tools','预制绘制':'Preset Tools','场景对象':'Scene Objects',
    '跑道':'Runway','滑行道':'Taxiway','滑行路线':'Taxi Route','机坪':'Apron','机位':'Aircraft Stand',
    '成套机位':'Aircraft Stand Layout','远机位':'Remote Stand','航站楼':'Terminal','航站楼主体':'Terminal Building',
    '指廊':'Concourse','廊桥':'Passenger Boarding Bridge','其他建筑':'Other Buildings',
    '停止道':'Stopway','服务车道':'Service Road','除冰坪':'De-icing Apron',
    '保护区':'Protected Area','关闭区域':'Closed Area','跑道道肩':'Runway Shoulder','滑行道道肩':'Taxiway Shoulder',
    '宽度':'Width','名称':'Name','编号':'Designation','标号':'Label','画布':'Canvas',
    '线条颜色':'Line Colour','道面颜色':'Pavement Colour','道肩':'Shoulder',
    '跑道尺寸单位':'Runway Dimension Unit','跑道道面材质':'Runway Surface Type',
    '航图编号':'Chart Number','机场名称':'Aerodrome Name','机场四字代码':'ICAO Location Indicator',
    '生效日期':'Effective Date','生效编号':'Edition Identifier','署名／制图单位':'Author / Organisation',
    '比例尺':'Scale','比例尺样式':'Scale Style','比例尺单位':'Scale Unit','图例':'Legend',
    '纸张':'Paper Size','纸张方向':'Orientation','纵向':'Portrait','横向':'Landscape',
    '图例排列':'Legend Layout','行数或列数':'Rows or Columns','画面适配':'Map Fit',
    '矩形':'Rectangle','圆角矩形':'Rounded Rectangle','圆形':'Circle','普通多边形':'Polygon',
    '自动圆角多边形':'Rounded Polygon','航图可见对象':'Chart Layers','恢复类型配色':'Reset Layer Colours',
    '删除标识':'Delete Symbol','网格':'Grid','导航窗口':'Navigator','适合画布':'Fit Canvas',
    '制图':'Drawing','属性':'Properties','完成':'Done','线条':'Line','道面':'Pavement',
    '机场数据':'Aerodrome Data','描边':'Outline','对象类型':'Object Type',
    '预览':'Preview','线段':'Line','数字比例':'Representative Fraction','黑白铁道线':'Alternating Scale Bar',
    '选取位置':'Choose Position','节点编辑':'Edit Nodes','设置保存后将于下次启动生效。':'The language setting takes effect on the next launch.',
}
EN.update({
    '审阅':'Review','刷新审阅':'Refresh Review','对象':'Object','导出报告':'Export Report',
    '岔路口引导线':'Junction Guidance Lines','绘图属性':'Drawing Properties','类型':'Type',
    '应用属性  ↵':'Apply Properties  ↵','完成绘制 ↵':'Finish Drawing ↵','聚焦对象':'Focus Object',
    '显示全部转弯':'Show All Turns','隐藏全部转弯':'Hide All Turns','所见即所得机场图编辑':'Aerodrome Chart Editor',
    '绘图操作说明':'Drawing Help','更多工程参数':'More Project Parameters',
    '保存到项目':'Save to Project','合并命名':'Merge Designations','图面与标记牌':'Surface Markings and Signs',
    '显示与操作':'Display and Controls','自动保存工程副本':'Autosave Project Copy',
    '自动保存间隔（分钟）':'Autosave Interval (minutes)','车辆行驶方向':'Vehicle Travel Direction',
    '编辑所选对象属性':'Edit Selected Object Properties','聚焦所选对象':'Focus Selected Object',
    '操作说明':'Instructions','道面材质':'Surface Material','跑道编号':'Runway Designation',
    '临时作业区':'Temporary Work Area','机坪安全线':'Apron Safety Line','中间等待位置':'Intermediate Holding Position',
    '跑道等待位置':'Runway-holding Position','引入线':'Lead-in Line','引出线':'Lead-out Line',
    '增强型中线':'Enhanced Taxiway Centreline','左侧':'Left','右侧':'Right','两侧':'Both Sides',
})
EN.update(dict(line.split('|', 1) for line in """
审阅|Review
最近使用|Recent Projects
导入位图|Import Bitmap
管理位图底图|Manage Background Images
编辑机位相交区域|Edit Stand Overlaps
设置透明度|Set Opacity
批量修改同类参数|Batch Edit Common Parameters
道面宽度|Pavement Width
道肩宽度|Shoulder Width
转弯半径|Turn Radius
转角半径|Corner Radius
线宽|Line Width
字高|Character Height
翼展|Wingspan
飞机长度|Aircraft Length
安全间距|Safety Clearance
引入线类型|Lead-in Line Type
引入线半径|Lead-in Turn Radius
配备廊桥|Include Boarding Bridge
显示安全线|Show Safety Lines
显示边线|Show Edge Markings
显示中线|Show Centreline
参数|Parameters
绘制工具预设|Drawing Tool Presets
工具|Tool
统一道面与道肩颜色|Set Default Pavement and Shoulder Colours
机位相交区域|Stand Overlap Area
完整机场示例|Complete Aerodrome Example
布局|Layout
批量绘制机位|Draw Multiple Stands
机位命名|Stand Designations
OpenGL 画布（重启生效）|OpenGL Canvas (Restart Required)
上移一层|Raise One Layer
下移一层|Lower One Layer
置于顶层|Bring to Front
置于底层|Send to Back
显示对象|Show Object
隐藏对象|Hide Object
对象透明度|Object Opacity
透明度（%）|Opacity (%)
作业区类型|Work Area Type
左侧作业区|Left Work Area
右侧作业区|Right Work Area
原廊桥侧作业区|Boarding Bridge Side Work Area
开启|Enabled
关闭|Disabled
斜线阴影|Hatching
合并机位|Merge Stands
多选|Multiple Selection
真北|True North
磁北|Magnetic North
磁北未设|Magnetic North Not Set
暂无最近项目|No Recent Projects
进近灯光|Approach Lighting
跑道边灯|Runway Edge Lights
跑道入口灯|Runway Threshold Lights
跑道警戒灯|Runway Guard Lights
跑道停止排灯|Runway Stop Bar Lights
中间等待位置灯|Intermediate Holding Position Lights
除冰坪出口灯|De-icing Apron Exit Lights
快速出口滑行道指示灯|Rapid Exit Taxiway Indicator Lights
机位引入线中线灯|Aircraft Stand Lead-in Centreline Lights
进近顺序闪光灯|Sequenced Flashing Approach Lights
机坪泛光灯|Apron Floodlights
跑道末端灯|Runway End Lights
跑道中线灯|Runway Centreline Lights
接地带灯|Touchdown Zone Lights
红色停止排灯|Red Stop Bar Lights
滑行道中线灯|Taxiway Centreline Lights
滑行道边灯|Taxiway Edge Lights
停止排灯|Stop Bar Lights
单个灯具|Single Light Fixture
灯光工具|Lighting Tools
灯光对象|Lighting Objects
跑道号码|Runway Designation Marking
跑道标记|Runway Markings
跑道中线|Runway Centreline
跑道中心圆|Runway Centre Circle
入口条纹|Runway Threshold Stripes
内移入口横线|Displaced Threshold Bar
内移长箭头|Displaced Threshold Arrows
临时入口箭头列|Temporary Threshold Arrows
瞄准点|Aiming Point
接地带基本型|Basic Touchdown Zone Markings
接地带距离编码|Distance-coded Touchdown Zone Markings
跑道边线|Runway Side Stripe
入口前黄色折线|Pre-threshold Yellow Chevrons
入口前不适用铺筑面|Unusable Pre-threshold Pavement
VOR校准圆|VOR Checkpoint Circle
VOR方向校准|VOR Bearing Check
滑行中线|Taxiway Centreline
滑行道标记|Taxiway Markings
掉头坪引导线|Turn Pad Guidance Line
跑道等待 A型|Pattern A Runway-holding Marking
跑道等待 B型|Pattern B Runway-holding Marking
B型跑道等待位置|Pattern B Runway-holding Position
中间等待位置线|Intermediate Holding Position Line
中间等待位置点|Intermediate Holding Position Point
强制指令文字|Mandatory Instruction Marking
禁止进入|No Entry
位置文字|Location Marking
目的地与方向标识|Destination and Direction Markings
最大翼展|Maximum Wingspan
滑行位置识别点|Taxiway Position Identification Point
滑行双边线|Double Taxiway Edge Marking
滑行道道肩条带|Taxiway Shoulder Stripes
机位编号|Stand Designation
机位与推出|Aircraft Stands and Pushback
机位引入线|Aircraft Stand Lead-in Line
机位引出线|Aircraft Stand Lead-out Line
辅助机位引入线|Supplementary Stand Lead-in Line
飞机推出线|Aircraft Pushback Line
推出等待点|Pushback Holding Point
机位安全线|Aircraft Stand Safety Line
机坪安全与设备|Apron Safety and Equipment
安全线交叉区域|Safety Line Overlap Area
翼尖净距双线|Double Wingtip Clearance Lines
轮挡放置区|Chock Storage Area
常规作业等待区|Standard Equipment Staging Area
临时作业等待区|Temporary Equipment Staging Area
廊桥活动区|Boarding Bridge Operating Area
廊桥回位圆|Boarding Bridge Parking Circle
设备摆放区|Equipment Storage Area
服务车道边线|Service Road Edge Line
穿越滑行道交错线|Staggered Taxiway Crossing Marking
行人步道|Pedestrian Walkway
道路等待停止线|Road-holding Stop Line
道路限速|Road Speed Limit
跑道关闭 X|Runway Closure Cross
滑行道关闭 X|Taxiway Closure Cross
喷气尾流警示|Jet Blast Warning
铺筑面长度 m|Pavement Length (m)
道路与限制使用|Roads and Restricted Use
车道分界线|Lane Divider
行车方向箭头|Traffic Direction Arrow
直升机坪|Helipad
操作失败|Operation Failed
文件类型|File Type
保存工程|Save Project
打开工程|Open Project
图框内注记，可输入多行|Chart notes. Multiple lines are supported.
可输入多行频率和字母|Enter frequencies and letters on multiple lines.
Note（图框内）|Note (inside frame)
横向按行|Horizontal Rows
纵向按列|Vertical Columns
缩放以容纳选区|Fit Selection
按纸张比例裁切|Crop to Paper Aspect Ratio
原始比例|Original Aspect Ratio
真北指针及标注|True North Arrow and Label
磁北指针及标注|Magnetic North Arrow and Label
页面适合窗口|Fit Page
重置版面元素位置|Reset Layout Positions
页面浏览导航 · 点击定位|Page Navigator · Click to Reposition
航图导航 · 左键框选，Shift 拖动裁切框|Chart Navigator · Drag to Select; Shift-drag to Move Crop
排版页面 · 滚轮缩放，中键或右键平移，左键拖动版面元素|Layout Preview · Scroll to Zoom, Middle or Right Drag to Pan, Left Drag to Move Items
机场基准点 / 定位|ARP Placement
无|None
""".strip().splitlines()))

EN.update({
    '路线与编号':'Routes and Designations','机场修正':'Aerodrome Corrections',
    '适合窗口':'Fit to Window','变更内容':'Changes','保存文件':'Save File',
    '选择文件夹':'Select Folder','选择颜色':'Select Colour','统一描边':'Global Outlines',
    '彩色分段 · F6':'Colour-coded Segments · F6','航图排版 · F8':'Chart Layout · F8',
    '点击顶点，按 Enter 完成':'Click vertices, then press Enter to finish',
    '点击起点和终点':'Click the start and end points','选择航图对象':'Select Chart Objects',
    '点击放置':'Click to Place','点击放置，可吸附跑道中点':'Click to place, with snapping to the runway midpoint',
    '请先绘制跑道':'Draw a runway first','ARP 已定位于所有跑道端点的几何中心':'ARP placed at the geometric centre of all runway endpoints',
    '左侧标识':'Left-side Symbol','右侧标识':'Right-side Symbol',
})
EN.update(dict(line.split('|',1) for line in '''
编辑远机位引出线顶点|Edit Remote Stand Lead-out Vertices
灯光方案 · 高交通密度|Lighting Configuration · High Traffic Density
点选灯光后在右侧编辑属性，按 F7 返回|Select a light to edit its properties on the right. Press F7 to return.
弯道最大灯间距（m）|Maximum Light Spacing on Curves (m)
灯具数量（0 为按间距）|Number of Fixtures (0 Uses Spacing)
设置警戒灯配套停止排灯|Configure the Stop Bar for the Guard Lights
单击终点完成灯列，Esc 取消|Click the endpoint to finish the light row. Press Esc to cancel.
单个灯列长度不能超过 5000 m|A light row cannot exceed 5,000 m.
机场已停用 · 全部灯光关闭|Aerodrome Inactive · All Lighting Off
跑道关闭 · 相关灯光已关闭|Runway Closed · Associated Lighting Off
设置灯光方案交通密度|Set Traffic Density for Lighting
单击两点布置灯列；滑行道中线灯可沿同一条滑行道绘制|Click two points to place a light row. Taxiway centreline lights can follow a single taxiway.
点选灯组后在右侧编辑属性|Select a light group to edit its properties on the right.
在画布或灯光对象列表中选择灯组。|Select a light group on the canvas or in the lighting object list.
关闭状态生效，灯光已熄灭。|Closure is active. The lights are off.
简易通常 420 m；精密通常 900 m，受限时至少 720 m|Simple: typically 420 m. Precision: typically 900 m, or at least 720 m where constrained.
热点轮廓需要有面积，且边线不能交叉|A hot spot outline must enclose an area without crossing itself.
航图模式 · 点击对象编辑配色，F8 返回|Chart Mode · Select an object to edit its colours. Press F8 to return.
点击高亮的机位相交区，在右侧选择处理方式。按 Esc 退出。|Select a highlighted stand overlap and choose how to handle it on the right. Press Esc to exit.
所选对象没有可批量修改的共同参数。|The selected objects have no common parameters available for batch editing.
OpenGL 画布设置已保存，重启生效。|The OpenGL canvas setting was saved and takes effect after restarting.
此工具没有可预设的绘制参数。|This tool has no drawing parameters that can be saved as presets.
已保存绘制工具预设。|Drawing tool presets saved.
正在撤销并重建机场图|Undoing and rebuilding the aerodrome plan…
正在重做并重建机场图|Redoing and rebuilding the aerodrome plan…
在画布上选择一个高亮区域。|Select a highlighted area on the canvas.
当前没有相交的机位安全线区域。|There are no overlapping stand safety-line areas.
正在切换机场图显示模式|Switching aerodrome display mode…
正在批量更新参数|Updating parameters…
正在重算连接道|Recalculating the connector taxiway…
统一 NO ENTRY 尺寸|Standardise NO ENTRY Marking Dimensions
统一全场 NO ENTRY 尺寸，检查最窄处可用空间|Standardise NO ENTRY markings and check the narrowest available space
统一跑道号强制性标识|Standardise Mandatory Runway Designation Markings
统一跑道编号强制指令标识的尺寸和位置|Standardise dimensions and placement of mandatory runway designation markings
整套机位已移动，回位圆已对准廊桥头部。|Stand layout moved. The bridge parking circle is aligned with the head of the boarding bridge.
目的地与方向标识与标记牌编辑模式·F5|Destination and Direction Signs and Markings · F5
全机场 NO ENTRY 尺寸|Aerodrome-wide NO ENTRY Dimensions
统一 NO ENTRY 尺寸／检查最窄处|Standardise NO ENTRY Dimensions / Check Narrowest Space
统一跑道编号强制指令标识|Standardise Mandatory Runway Designation Markings
整套机位对准廊桥头部|Align the Stand Layout with the Boarding Bridge Head
廊桥回位点 · 固定入口旋转|Boarding Bridge Parking Point · Rotate about Fixed Entry
显示模式：彩色分段 · F6|Display Mode: Colour-coded Segments · F6
显示模式：普通机场图|Display Mode: Standard Aerodrome Plan
正在按道面净宽统一跑道编号标识|Standardising runway designation markings to the clear pavement width…
按指标统一；容纳不下的标志列入审阅|Standardise to the specified dimensions and flag markings that do not fit for review
按最窄处统一；低于标准时列入审阅|Size to the narrowest point and flag below-standard markings for review
机坪绘制：选择两个对角点，右键取消|Draw an apron by selecting opposite corners. Right-click to cancel.
指廊必须向主体外侧挤出|The concourse must extend outward from the terminal footprint.
生成最近相接滑行道的方向信息|Generate direction information for the nearest connecting taxiway
机坪内沿用机坪背景色|Use the apron background colour within the apron
窄道面也在两侧成对绘制（需审阅）|Draw paired markings on both sides of narrow pavements (review required)
瞄准点／接地带整组避让（需审阅）|Shift the aiming point and touchdown zone markings as a group (review required)
已选择连接道，可在右侧修改独立编号或名称|Connector taxiway selected. Edit its designation or name on the right.
请点击可见的直线或转弯引导中线|Click a visible straight or curved guidance centreline.
末端截断：左键确认删除|Trim End: Left-click to confirm removal
主体尺寸必须是大于0的有限数|Building dimensions must be finite and greater than zero.
请重新选择需要改号的子段。|Select the segment to redesignate again.
已吸附廊桥头部；入口固定在原滑行道中线上。|Snapped to the boarding bridge head. The entry remains on the original taxiway centreline.
入口固定，拖动调整机位方向与长度；Shift约束方向。|Drag to change the stand heading and length about its fixed entry. Hold Shift to constrain the heading.
固定入口调整廊桥机位|Adjust Boarding Bridge Stand about Fixed Entry
整套机位对准最近廊桥|Align Stand Layout with Nearest Boarding Bridge
橙色圆点沿绑定中线滑动，停止端保持原位；蓝色点继续编辑分支形状。|Slide the orange point along the linked centreline without moving the stop end. Use the blue point to edit the branch shape.
'''.strip().splitlines()))
EN.update({
    '助航灯光 · F7':'Aeronautical Ground Lighting · F7',
    '入口·滑行中线绑定':'Entry · Linked to Taxiway Centreline',
    '吸附 · 跑道中点':'Snapped · Runway Midpoint',
    '已生成方向标记牌':'Direction Signs Generated',
    '详细信息见 gui_error.log':'See gui_error.log for details',
})
EN['示例工程：ZSQD']='Example Project: ZSQD'
EN.update(dict(row.split('|',1) for row in '''
其他标线|Other Markings
建筑|Buildings
未标注|Unspecified
沥青|Asphalt
混凝土|Concrete
砾石|Gravel
草地|Grass
设备|Equipment
航图信息|Chart Information
热点形状|Hot Spot Shape
Ⅰ类 A 型|Category I, Type A
Ⅰ类 B 型|Category I, Type B
Ⅱ／Ⅲ类|Category II / III
保留手动设置|Keep Manual Settings
停用|Deactivate
删除灯组|Delete Light Group
助航灯光动画|Airfield Lighting Animation
单击画布放置灯具|Click the canvas to place a light fixture
反转|Reverse
发光朝向|Light Direction
同时设置停止排灯|Include a Stop Bar
启用|Enable
总长（m）|Overall Length (m)
恢复自动|Restore Automatic Settings
按标线方向|Follow Marking Direction
播放该灯组动画|Animate This Light Group
灯光动画|Lighting Animation
灯光属性|Lighting Properties
灯光构型|Lighting Configuration
灯间距（m）|Light Spacing (m)
白色|White
简易 A 型|Simple Approach, Type A
简易 B 型|Simple Approach, Type B
红色|Red
绘制助航灯光|Draw Airfield Lighting
绘制状态|Drawing Status
绿色|Green
编辑助航灯光|Edit Airfield Lighting
设置灯光动画|Configure Lighting Animation
进近灯光类型|Approach Lighting Type
选择灯光|Select Lighting
长度范围|Length Range
随跑道等级|Use Runway Category
预设|Preset
颜色|Colour
黄色|Yellow
蓝色|Blue
（停用）| (Inactive)
（关闭）| (Closed)
全场景|Entire Scene
全机场|Entire Aerodrome
基本|General
大尺寸导出|Large Export
宽度（像素）|Width (pixels)
导出|Export
导出中|Exporting
导出准备中|Preparing Export
导出失败|Export Failed
导出审阅|Export Review
导出灯光动画|Export Lighting Animation
导出范围|Export Extent
导出设置|Export Settings
当前视图|Current View
所有模式（ZIP）|All Modes (ZIP)
显示模式|Display Mode
机场项目|Aerodrome Project
状态|Status
规则|Rules
说明|Description
请先选择要导出的对象|Select the objects to export first.
请等待当前导出完成|Wait for the current export to finish.
选中对象|Selected Objects
选择位置并导出|Choose Destination and Export
透明背景|Transparent Background
隐藏导航窗口|Hide Overview
按固定倍率放大标记牌|Enlarge Signs by a Fixed Factor
显示米／英尺比例尺|Show Metre / Foot Scale Bar
正在准备导出快照|Preparing the export snapshot…
输入正整数像素宽度|Enter a positive whole number for the width in pixels.
吸附滑行道中线|Snap to Taxiway Centreline
源滑行道|Source Taxiway
HP 等待点标记牌|HP Holding Point Sign
HP 等待点道面标识|HP Holding Point Marking
中线|Centreline
交叉点起飞标记牌|Intersection Take-off Sign
位置编号|Location Designation
出口方向|Exit Direction
工程网格朝上|Grid North Up
方向标记牌|Direction Sign
显示 FPS 与内存|Show FPS and Memory Use
显示选项|Display Options
标记牌不按比例显示|Display Signs Not to Scale
标记牌放大显示（固定倍数）|Enlarge Signs (Fixed Factor)
标记牌牌面|Sign Panel
标识编辑  F5|Sign and Marking Editing  F5
滑行道或机坪滑行道|Taxiway or Apron Taxiway
点击要追加的分支|Click the branch to add.
牌面编号或组合内容|Sign Designation or Combined Message
生成标记牌|Generate Signs
目的地与方向标识与标记牌|Destination and Direction Markings and Signs
目的地标记牌|Destination Sign
相连跑道与盲降等级|Connected Runway and ILS Category
真北朝上|True North Up
统一启用滑行道黑色描边|Apply Black Outlines to All Taxiway Markings
统一启用跑道黑色描边|Apply Black Outlines to All Runway Markings
编辑文字|Edit Text
编辑标识文字|Edit Marking Text
编辑选中的标识或标记牌文字|Edit Selected Marking or Sign Text
请为每块牌面输入对应的文字|Enter the message for each sign panel.
跑道等待位置标记牌|Runway-holding Position Sign
追加分支|Add Branch
重绑来源|Rebind Source
重选目的地|Reselect Destination
隐藏标记牌|Hide Signs
'''.strip().splitlines()))
ZH = {
    'TEMPORARY':'临时关闭','PERMANENT':'永久关闭',
    'BOTH':'双向','FORWARD':'正向','REVERSE':'反向',
}
import re

DYNAMIC = tuple((re.compile(pattern),translated) for pattern,translated in (
    (r'正在导入“(.+?)”[.。…]*',r'Importing “\1”…'),
    (r'无法更新最近使用记录：\s*(.+)',r'Could not update the list of recent projects: \1'),
    (r'无法保存深色模式设置：\s*(.+)',r'Could not save the dark mode setting: \1'),
    (r'无法保存习惯设置：\s*(.+)',r'Could not save preferences: \1'),
    (r'无法保存预设\s*[:：]?\s*(.+)',r'Could not save the preset: \1'),
    (r'自动保存失败\s*[:：]?\s*(.+)',r'Autosave failed: \1'),
    (r'自动保存副本\s+(.+)',r'Autosaved project copy: \1'),
    (r'已吸附跑道端头 · (.+)',r'Snapped to runway end · \1'),
    (r'批量修改参数（(\d+) 个）',r'Batch Edit Parameters (\1 objects)'),
    (r'已按道面净宽重新计算 (\d+) 个跑道编号强制指令标识[。]?',r'Recalculated \1 mandatory runway designation markings for the clear pavement width.'),
))
language = 'zh_CN'


_qt_translator=None


def install_catalog(app):
    from pathlib import Path
    from PySide6.QtCore import QTranslator

    global _qt_translator
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator.deleteLater()
        _qt_translator=None
    if language!='en':return
    translator=QTranslator(app)
    if translator.load(str(Path(__file__).with_name('AirportCanvas_en.qm'))):
        if app.installTranslator(translator):
            _qt_translator=translator
            return
    translator.deleteLater()


def catalog_text(text):
    if _qt_translator is not None:
        from PySide6.QtCore import QCoreApplication
        result=QCoreApplication.translate('AirportCanvas',text)
        if result!=text:return result
    return EN.get(text,text)


SIDEBAR_PATTERNS=tuple((re.compile(pattern),key) for pattern,key in (
    (r'审阅 · (\d+) 项问题 / (\d+) 项待核','审阅 · %1 项问题 / %2 项待核'),
    (r'([AB])端\s*(瞄准点)距道面边：([\d.]+) m','%1端%2距道面边：%3 m'),
    (r'中心圆外缘半径：([\d.]+) m（随跑道宽度联动）','中心圆外缘半径：%1 m（随跑道宽度联动）'),
    (r'入口条纹：(\d+)条，宽([\d.]+) m，距道面边([\d.]+) m。','入口条纹：%1条，宽%2 m，距道面边%3 m。'),
))


def tr(text, *, enum=False):
    if not isinstance(text,str):return text
    if enum and language=='zh_CN':return ZH.get(text,text)
    if language!='en':return text
    translated=catalog_text(text)
    if translated!=text:return translated
    for pattern,translated in DYNAMIC:
        match=pattern.fullmatch(text)
        if match:return match.expand(translated)
    for pattern,key in SIDEBAR_PATTERNS:
        match=pattern.fullmatch(text)
        if match:
            result=catalog_text(key)
            for n,value in enumerate(match.groups(),1):
                result=result.replace(f'%{n}',catalog_text(value))
            return result
    end=re.fullmatch(r'([AB])端\s*(.+)',text)
    if end:
        side,caption=end.groups()
        translated=catalog_text(caption)
        if translated!=caption:
            return catalog_text('%1端 %2').replace('%1',side).replace('%2',translated)
    stripped=text.strip()
    translated=catalog_text(stripped)
    if translated!=stripped:return text.replace(stripped,translated,1)
    key,sep,shortcut=text.partition('\t')
    if sep and (translated:=catalog_text(key))!=key:return translated+sep+shortcut
    if '\n' in text:return '\n'.join(tr(line) for line in text.split('\n'))
    prefix=text[:len(text)-len(text.lstrip('▸▾▶▼↖↶↷↩ '))]
    if prefix:return prefix+tr(text[len(prefix):]) if text[len(prefix):] else text
    if ' · ' in text:return ' · '.join(tr(part) for part in text.split(' · '))
    caption,sep,suffix=text.rpartition(' [')
    if sep and suffix.endswith(']'):
        translated=catalog_text(caption)
        if translated!=caption:return translated+sep+suffix
    if text.startswith('绘制 '):
        pattern=catalog_text('绘制 %1')
        if pattern!='绘制 %1':return pattern.replace('%1',tr(text[3:]))
    key=text.rstrip('…')
    return catalog_text(key)+text[len(key):]


def install(app):
    from qt_core21 import C,W,application
    class Localizer(C.QObject):
        def widget(self,w):
            for cls,getter,setter in (
                    (W.QAbstractButton,'text','setText'),(W.QLabel,'text','setText'),
                    (W.QGroupBox,'title','setTitle'),(W.QDialog,'windowTitle','setWindowTitle')):
                if isinstance(w,cls):
                    old=getattr(w,getter)()
                    new=tr(old)
                    if new!=old:getattr(w,setter)(new)
            if isinstance(w,(W.QLineEdit,W.QPlainTextEdit,W.QTextEdit)):
                hint=w.placeholderText()
                if hint:w.setPlaceholderText(tr(hint))
            if isinstance(w,W.QMessageBox):
                w.setText(tr(w.text()))
                w.setInformativeText(tr(w.informativeText()))
            if isinstance(w,W.QTabWidget):
                for i in range(w.count()):
                    w.setTabText(i,tr(w.tabText(i)))
            if isinstance(w,(W.QMenu,W.QMenuBar)):
                for action in w.actions():action.setText(tr(action.text()))
            if isinstance(w,W.QWidget):
                tip=w.toolTip()
                if tip:w.setToolTip(tr(tip))

        def eventFilter(self,obj,event):
            if event.type() in (C.QEvent.Type.Show,C.QEvent.Type.Polish,C.QEvent.Type.ActionAdded):
                self.widget(obj)
            return False
    localizer=Localizer(app.q)
    app._interface_localizer=localizer
    application().installEventFilter(localizer)
    for child in app.q.findChildren(W.QWidget):localizer.widget(child)
