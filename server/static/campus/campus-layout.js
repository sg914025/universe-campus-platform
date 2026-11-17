// Approximate layout drawn from the user reference, not surveyed coordinates.
export const places=[
 {id:'dorm',name:'北区学生生活区',kind:'life',x:-68,z:-111,w:17,d:36,h:17,parts:[[-27,0],[0,0],[27,0]],node:'north',description:'北侧生活组团，参考图中学生公寓区域。'},
 {id:'dining3',name:'三期食堂',kind:'life',x:-42,z:-73,w:31,d:20,h:11,node:'north',description:'生活区南侧的食堂与公共活动空间。'},
 {id:'parcel',name:'校园驿站',kind:'life',x:-87,z:-61,w:17,d:12,h:6,node:'westnorth',description:'生活区附近的快递服务示意点。'},
 {id:'teachA',building:'A',name:'教学组团 A',kind:'study',x:-30,z:-25,w:16,d:29,h:17,parts:[[-14,0],[14,0]],node:'central',description:'主干道西侧的教学组团，建筑位置与形态为近似示意。'},
 {id:'teachB',building:'B',name:'教学组团 B',kind:'study',x:-48,z:13,w:16,d:28,h:15,parts:[[-15,0],[15,0]],node:'library',description:'图书馆北侧教学空间，可通过平台了解学习服务。'},
 {id:'library',building:'library',name:'图书馆',kind:'study',x:-68,z:49,w:34,d:25,h:15,node:'library',description:'校园中西部的学习地标，连接自习室预约服务。'},
 {id:'dining2',name:'B2 食堂',kind:'life',x:14,z:67,w:25,d:17,h:9,node:'east',description:'靠近主干道的食堂示意建筑。'},
 {id:'gym',name:'体育馆',kind:'sport',x:-70,z:106,w:37,d:25,h:13,node:'sports',description:'可进入体育馆内部，查看乒乓球台、篮球场和其他室内运动资源。'},
 {id:'courts',name:'室外足球场',kind:'sport',x:-113,z:105,w:26,d:40,h:1,node:'sports',description:'体育馆西侧的室外足球场，可查看所选时段的场地预约状态。'},
 {id:'teachC',building:'C',name:'C 区',kind:'study',x:-10,z:111,w:15,d:25,h:14,parts:[[-13,0],[13,0]],node:'south',description:'南部教学区域，按参考地图布局重构。'},
 {id:'continuing',building:'C',name:'C 区',kind:'study',x:39,z:121,w:22,d:23,h:13,node:'south',description:'主干道南侧的学习服务区域示意。'},
 {id:'health',name:'校内医院',kind:'health',x:58,z:-9,w:33,d:27,h:19,node:'hospital',description:'校园医疗服务示意建筑；就医请以校方实际位置和安排为准。'}
];
export const nodes={gate:[6,143],south:[-6,127],sports:[-67,128],library:[-49,56],central:[-18,7],east:[10,50],north:[-32,-48],westnorth:[-89,-44],hospital:[34,2]};
export const edges=[['gate','south'],['south','sports'],['sports','library'],['library','central'],['central','north'],['north','westnorth'],['central','east'],['east','south'],['east','hospital']];
export function routeTo(destination){if(!nodes[destination])return [];const distance={gate:0},previous={},pending=new Set(Object.keys(nodes));while(pending.size){let point=null;for(const n of pending)if(distance[n]!==undefined&&(point===null||distance[n]<distance[point]))point=n;if(point===null)break;pending.delete(point);if(point===destination)break;for(const edge of edges){const n=edge[0]===point?edge[1]:edge[1]===point?edge[0]:null;if(!n||!pending.has(n))continue;const a=nodes[point],b=nodes[n],next=distance[point]+Math.hypot(a[0]-b[0],a[1]-b[1]);if(distance[n]===undefined||next<distance[n]){distance[n]=next;previous[n]=point;}}}if(distance[destination]===undefined)return [];const result=[destination];while(result[0]!=='gate')result.unshift(previous[result[0]]);return result.map(n=>nodes[n]);}
