import config from '../config.generated';
const TOKEN='universe-mobile-token-v1';
export const getToken=()=>uni.getStorageSync(TOKEN)||'';
export const setToken=value=>value?uni.setStorageSync(TOKEN,value):uni.removeStorageSync(TOKEN);
export function serverBase(){let value=config.apiBase.replace(/\/$/,'');
// #ifdef H5
value='';
// #endif
return value;}
export function webBase(){let value=config.apiBase.replace(/\/$/,'');
// #ifdef H5
value=window.location.origin;
// #endif
return value;}
export async function api(path,data,method=data===undefined?'GET':'POST'){
 const token=getToken(),language=uni.getStorageSync('universe-mobile-language')||'zh';
 const [route,query]=path.split('?');
 const header={'Content-Type':'application/json','X-Campus-Language':language};
 if(token&&path!=='auth/login')header.Authorization='Bearer '+token;
 return new Promise((resolve,reject)=>uni.request({url:serverBase()+'/api/mobile/v1/'+route+'/'+(query?'?'+query:''),method,data,header,timeout:110000,success(res){
 if(res.statusCode>=200&&res.statusCode<300&&typeof res.data==='object')return resolve(res.data);
 if(res.statusCode===401)setToken('');
 const fields=res.data?.fields;const detail=fields?Object.values(fields).flat().map(x=>x.message).join('；'):'';
 reject(Object.assign(new Error(detail||res.data?.error||'服务暂不可用，请稍后重试'),{status:res.statusCode,code:res.data?.code}));},fail(){reject(new Error('连接失败，请检查网络或服务器地址'));}}));}
export function requestKey(){return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{const n=Math.floor(Math.random()*16);return(c==='x'?n:(n&3|8)).toString(16)})}
export function getLocation(){return new Promise((resolve,reject)=>uni.getLocation({type:'wgs84',success:resolve,fail:reject}))}
