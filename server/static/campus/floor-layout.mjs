// 校园楼层示意布局；制作：UniVerse Team。位置不代表学校实测数据。
export function floorLayout(resources,outdoor=false){
 const study=resources.length===0||resources.every(r=>r.kind==='study');
 const rows=study?Math.max(1,Math.ceil(resources.length/12)):Math.max(1,Math.ceil(resources.length/3));
 const width=outdoor?76:112,depth=outdoor?72:study?Math.max(94,70+rows*8):Math.max(94,rows*24+26);
 const positions=new Map(resources.map((r,i)=>{if(study){const room=i%4,within=Math.floor(i/4),col=within%3,row=Math.floor(within/3),side=room%2?1:-1,back=room<2?-1:1;return [r.id,{x:side*28+(col-1)*10,z:back*23+(row-(rows-1)/2)*8,room:room+1}];}return [r.id,{x:(i%3-1)*27,z:(Math.floor(i/3)-(rows-1)/2)*24,room:0}];}));
 if(outdoor)resources.forEach(r=>positions.set(r.id,{x:0,z:0,room:0}));
 return {study,width,depth,positions};
}
export function visibleLabels(candidates,width,height){
 const occupied=[];return [...candidates].sort((a,b)=>Number(!!b.selected)-Number(!!a.selected)||Number(!!b.focused)-Number(!!a.focused)||a.order-b.order).filter(c=>{if(c.z< -1||c.z>1||c.x<8||c.y<55||c.x>width-8||c.y>height-25)return false;const rect={l:c.x-c.w/2-3,r:c.x+c.w/2+3,t:c.y-c.h-4,b:c.y+4};if(rect.l<2||rect.r>width-2||occupied.some(o=>rect.l<o.r&&rect.r>o.l&&rect.t<o.b&&rect.b>o.t))return false;occupied.push(rect);return true;}).map(c=>c.order);
}
