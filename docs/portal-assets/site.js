const descriptions=[
['机场几何编辑界面','在画布上编辑机场几何，并在属性面板调整所选对象。','Geometry editor','Edit airport geometry on the canvas and adjust the selected object in the inspector.'],
['F5 标识编辑界面','查看目的地与方向标识，检查交叉口的文字、箭头和标记牌。','F5 sign editor','Inspect destination and direction markings, arrows and signs at intersections.'],
['F6 滑行道分段界面','用彩色分段追踪滑行道及其转弯引导线。','F6 taxiway segments','Trace taxiway segments and their turn guidance lines by color.'],
['F7 助航灯光界面','在深色画布上检查跑道、滑行道和等待位置的灯光。','F7 airfield lighting','Inspect runway, taxiway and holding-position lights on a dark canvas.'],
['F8 航图排版界面','设置航图的图框、图例、比例尺和裁切范围，预览排版结果。','F8 chart layout','Set the frame, legend, scale and crop, then preview the chart layout.']];
const labels=[...document.querySelectorAll('[data-en]')];
const localizedAssets=[...document.querySelectorAll('[data-alt-en]')];
const controls=[...document.querySelectorAll('[data-view]')];
const toggle=document.querySelector('#language');
const preview=document.querySelector('#view-image');
const caption=document.querySelector('#view-caption');
let english=false;
let selected=0;
for(const node of labels) node.dataset.zh=node.textContent;
for(const node of localizedAssets) node.dataset.altZh=node.alt;
function refresh(){
 document.documentElement.lang=english?'en':'zh-CN';
 document.title=english?'Airport Canvas — Aerodrome Editor':'Airport Canvas — 机场绘图编辑器';
 toggle.textContent=english?'中文':'EN';
 toggle.lang=english?'zh-CN':'en';
 toggle.setAttribute('aria-label',english?'切换到中文':'Switch to English');
 for(const node of labels) node.textContent=english?node.dataset.en:node.dataset.zh;
 for(const node of localizedAssets) node.alt=english?node.dataset.altEn:node.dataset.altZh;
 for(const control of controls) control.setAttribute('aria-pressed',String(Number(control.dataset.view)===selected));
 preview.src='./portal-assets/view-'+selected+'.webp';
 preview.alt=descriptions[selected][english?2:0];
 caption.textContent=descriptions[selected][english?3:1];
}
for(const control of controls) control.addEventListener('click',()=>{selected=Number(control.dataset.view);refresh();});
toggle.addEventListener('click',()=>{english=!english;refresh();});
refresh();
