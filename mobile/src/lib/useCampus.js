import {ref,reactive,computed,onMounted,onUnmounted} from 'vue';
import {api,getToken,setToken,requestKey,getLocation,webBase} from './api';
import {translate} from './i18n';
import {onHide,onShow} from '@dcloudio/uni-app';
export function useCampus(){
 const section=ref('home'),drawer=ref(false),modal=ref(''),loading=ref(false),busy=ref(false),online=ref(false),error=ref(''),user=ref(null),language=ref(uni.getStorageSync('universe-mobile-language')||'zh');
 const bootstrap=ref({today:'',kinds:[],buildings:[],slots:[],announcements:[]}),overview=ref({bookings:[],notices:[],unread:0}),weather=ref(null),weatherBusy=ref(false),city=ref(''),cityChoices=ref([]),weatherStatus=ref('');
 const loginForm=reactive({username:'',password:''}),passwordForm=reactive({old_password:'',new_password1:'',new_password2:''});
 const venues=ref([]),bookings=ref([]),filters=reactive({kind:'study',building:'A',day:'',slot:'14',floor:1}),selectedVenue=ref(null),selectedBooking=ref(null);
 const posts=ref([]),postCategory=ref(''),postPage=ref(1),morePosts=ref(false),postForm=reactive({title:'',category:'校园生活',content:''}),postDetail=ref(null);
 const friends=ref([]),people=ref([]),friendQuery=ref(''),peer=ref(null),messages=ref([]),chatText=ref(''),moments=ref([]),momentText=ref(''),errands=ref([]),notices=ref([]);
 const assistant=ref({}),plan=ref(null),conversation=ref([]),message=ref(''),externalAllowed=ref(false),planDay=ref(''),planSlot=ref('14'),assistantDay=ref(''),bookingKey=ref('');
 const health=reactive({part:'head',description:'',duration:'',answers:{},accepted_notice:false,feeling:'mild',request_key:requestKey()}),healthParts=ref([]),healthStep=ref(null),healthReply=ref(''),qrText=ref('');
 const t=text=>translate(text,language.value);
 const title=computed(()=>t(({home:'校园首页',assistant:'办事向导',messages:'消息与好友',me:'我的校园',booking:'场地预约',forum:'校园广场',health:'AI 导诊',errands:'校园跑腿',bookings:'我的预约'})[section.value]||'寰校通'));
 const floors=computed(()=>[...new Set(venues.value.map(x=>x.floor))].sort((a,b)=>a-b));
 const floorVenues=computed(()=>venues.value.filter(x=>x.floor===filters.floor));
 const available=computed(()=>venues.value.filter(x=>x.state==='available').length);
 const mainTabs=[{key:'home',label:'首页',icon:'home'},{key:'assistant',label:'办事',icon:'spark'},{key:'messages',label:'消息',icon:'chat'},{key:'me',label:'我的',icon:'user'}];
 const services=[{key:'booking',label:'场地预约',desc:'留一个专注的位置',icon:'calendar',tone:'sage'},{key:'forum',label:'校园广场',desc:'让相遇从这里开始',icon:'chat',tone:'cream'},{key:'health',label:'AI 导诊',desc:'先整理，再问医生',icon:'health',tone:'blue'},{key:'errands',label:'校园跑腿',desc:'让小事有人帮忙',icon:'box',tone:'pink'}];
 const toast=text=>uni.showToast({title:t(text),icon:'none'});
 function fail(e){error.value=e.message;toast(e.message);if(e.status===401){user.value=null;modal.value='login'}if(e.code==='password_change_required')modal.value='password'}
 async function run(fn){if(busy.value)return;busy.value=true;error.value='';try{return await fn()}catch(e){fail(e)}finally{busy.value=false}}
 function requireLogin(){if(!getToken()){modal.value='login';return false}return true}
 async function refreshOverview(){if(!getToken())return;overview.value=await api('overview');user.value=overview.value.user;plan.value=overview.value.plan}
 async function boot(){loading.value=true;try{bootstrap.value=await api('bootstrap');online.value=true;if(!filters.day){filters.day=bootstrap.value.default_day||bootstrap.value.today;filters.slot=bootstrap.value.default_slot||'14'}assistantDay.value=bootstrap.value.today;planDay.value=bootstrap.value.today;if(getToken()){const who=await api('me');user.value=who.user;if(user.value.must_change_password)modal.value='password';else await refreshOverview()}}catch(e){online.value=false;error.value=e.message;if(e.status===401)user.value=null}finally{loading.value=false}}
 async function go(key){drawer.value=false;if(section.value!==key)uni.pageScrollTo({scrollTop:0,duration:0});section.value=key;error.value='';if(key==='home'){await boot();return}if(!requireLogin())return;loading.value=true;try{
  if(key==='booking')await loadVenues();if(key==='bookings')bookings.value=(await api('bookings')).bookings;
  if(key==='forum'){postPage.value=1;await loadPosts()}
  if(key==='messages'){friends.value=(await api('friends')).friends;moments.value=(await api('moments')).moments;notices.value=(await api('notices')).notices}
  if(key==='assistant'){assistant.value=await api('assistant/state');plan.value=(await api('plans')).plan}
  if(key==='health')healthParts.value=(await api('health/parts')).parts;
  if(key==='errands')errands.value=(await api('errands')).errands;
  if(key==='me')await refreshOverview();
 }catch(e){fail(e)}finally{loading.value=false}}
 async function signIn(){await run(async()=>{const data=await api('auth/login',loginForm);setToken(data.token);user.value=data.user;loginForm.password='';modal.value=data.user.must_change_password?'password':'';if(!data.user.must_change_password){await boot();await go(section.value)}})}
 async function changePassword(){await run(async()=>{const data=await api('auth/password',passwordForm);setToken(data.token);user.value=data.user;Object.keys(passwordForm).forEach(k=>passwordForm[k]='');modal.value='';await boot();await go(section.value);toast('密码已更新')})}
 async function signOut(){await run(async()=>{await api('auth/logout',{});setToken('');user.value=null;overview.value={bookings:[],notices:[],unread:0};plan.value=null;conversation.value=[];messages.value=[];section.value='home';drawer.value=false})}
 async function setLanguage(value){language.value=value;uni.setStorageSync('universe-mobile-language',value);await go(section.value)}
 async function locate(){if(weatherBusy.value)return;weatherBusy.value=true;weatherStatus.value=t('正在获取设备位置…');try{let result;try{const pos=await getLocation();result=await api('weather',{coordinates:{latitude:pos.latitude,longitude:pos.longitude}})}catch{weatherStatus.value=t('正在尝试 IP 定位…');result=await api('weather',{locate:true})}weather.value=result;weatherStatus.value=result.source==='ip'?t('IP 位置可能受网络出口影响'):'';uni.setStorageSync('universe-mobile-weather',result.place)}catch(e){weatherStatus.value=e.message}finally{weatherBusy.value=false}}
 async function searchCity(){if(city.value.trim().length<2)return;await run(async()=>{cityChoices.value=(await api('weather',{query:city.value.trim()})).choices})}
 async function selectCity(place){await run(async()=>{weather.value=await api('weather',{place});uni.setStorageSync('universe-mobile-weather',place);cityChoices.value=[];modal.value='';weatherStatus.value=''})}
 async function loadVenues(){const q=URLSearchParamsCompat({kind:filters.kind,building:filters.building,day:filters.day,slot:filters.slot});venues.value=(await api('venues?'+q)).venues;if(!floors.value.includes(filters.floor))filters.floor=floors.value[0]||1}
 function URLSearchParamsCompat(obj){return Object.entries(obj).map(([k,v])=>encodeURIComponent(k)+'='+encodeURIComponent(v)).join('&')}
 async function chooseFilter(key,value){filters[key]=value;await run(loadVenues)}
 function chooseSeat(v){if(v.state!=='available'){toast('此位置暂不可预约');return}selectedVenue.value=v;bookingKey.value=requestKey();modal.value='reserve'}
 async function reserve(){await run(async()=>{const result=await api('bookings',{venue_id:selectedVenue.value.id,day:filters.day,slot:filters.slot,request_key:bookingKey.value});selectedBooking.value=result.booking;modal.value='receipt';await loadVenues();await refreshOverview()})}
 function confirmAction(content,action){uni.showModal({title:t('请确认'),content:t(content),confirmColor:'#27594a',success:r=>{if(r.confirm)run(action)}})}
 function cancelBooking(row){confirmAction('确定取消这次预约？',async()=>{await api('bookings/'+row.id+'/cancel',{});modal.value='';await go('bookings');await refreshOverview()})}
 async function loadPosts(append=false){const data=await api('posts?'+URLSearchParamsCompat({page:postPage.value,category:postCategory.value}));posts.value=append?[...posts.value,...data.posts]:data.posts;morePosts.value=data.has_more}
 async function filterPosts(category){postCategory.value=category;postPage.value=1;await run(()=>loadPosts())}
 async function nextPosts(){postPage.value++;await run(()=>loadPosts(true))}
 function composePost(forPlan=false){if(!requireLogin())return;postForm.title='';postForm.content='';postForm.category=forPlan?'交友':'校园生活';postForm.service_plan=forPlan?plan.value.id:undefined;postForm.revision=forPlan?plan.value.revision:undefined;modal.value='post'}
 async function publish(){await run(async()=>{await api('posts',{...postForm});modal.value='';toast('发布成功');if(postForm.service_plan)await go('assistant');else await go('forum')})}
 async function searchFriends(){await run(async()=>{people.value=(await api('friends/search?q='+encodeURIComponent(friendQuery.value))).people})}
 async function addFriend(person){await run(async()=>{await api('friends/'+person.id+'/follow',{});person.following=true;toast('已关注，双方互关后即可聊天')})}
 async function chat(person){peer.value=person;messages.value=[];modal.value='chat';await loadMessages()}
 async function loadMessages(){const peerId=peer.value?.id;if(!peerId)return;try{const data=await api('friends/'+peerId+'/messages');if(peer.value?.id!==peerId)return;const previous=new Map(messages.value.map(x=>[x.id,x]));messages.value=data.messages.map(m=>({...m,translation:previous.get(m.id)?.translation,showOriginal:previous.get(m.id)?.showOriginal}));peer.value=data.peer;const friend=friends.value.find(x=>x.id===peerId);if(friend)friend.unread=0;refreshOverview().catch(()=>{});if(data.auto_translate){for(const m of messages.value.filter(x=>!x.mine&&x.content&&!x.translation).slice(-3)){api('messages/'+m.id+'/translation',{}).then(r=>{m.translation=r.text}).catch(()=>{m.translationUnavailable=true})}}}catch(e){fail(e)}}
 async function sendChat(){if(!chatText.value.trim())return;await run(async()=>{await api('friends/'+peer.value.id+'/messages',{content:chatText.value});chatText.value='';await loadMessages()})}
 async function publishMoment(){await run(async()=>{await api('moments',{content:momentText.value});momentText.value='';modal.value='';await go('messages');toast('仅当前好友可见')})}
 async function startShare(row){selectedBooking.value=row;await run(async()=>{friends.value=(await api('friends')).friends;modal.value='share'})}
 async function shareTo(person){await run(async()=>{await api('bookings/'+selectedBooking.value.id+'/share',{friend_id:person.id,revision:plan.value?.revision});modal.value='';toast('办事卡已分享');await refreshOverview();if(section.value==='assistant')await go('assistant')})}
 function adopt(result){assistant.value=result;if(result.plan)plan.value=result.plan;if(result.message)conversation.value.push({role:'assistant',content:result.message});if(result.receipt)refreshOverview()}
 async function sendMessage(value=message.value){if(!requireLogin()||!value.trim())return;const input=value.trim();await run(async()=>{const history=conversation.value.slice(-10);conversation.value.push({role:'user',content:input});message.value='';adopt(await api('assistant/chat',{message:input,channel:'auto',external_allowed:externalAllowed.value,history}))})}
 async function assistantSelect(key,value){await run(async()=>adopt(await api('assistant/chat',{selection:{[key]:value}})))}
 function confirmAssistant(v){confirmAction('确认预约此场地和时段？',async()=>{adopt(await api('assistant/confirm',{draft_key:assistant.value.draft_key,venue_id:v.id}));await refreshOverview()})}
 async function planAction(action){await run(async()=>{const data={id:plan.value.id,revision:plan.value.revision,action};if(action==='time')Object.assign(data,{day:planDay.value,slot:planSlot.value});const result=await api('plans',data);plan.value=result.plan;if(result.assistant)adopt(result.assistant);if(action==='accept'&&plan.value.current==='friends')composePost(true)})}
 async function continuePlan(){if(!plan.value)return;await go('assistant');if(plan.value.current==='help'){await openWeb('/errands/new/');return}if(plan.value.current==='health'){await go('health');return}if(plan.value.current==='friends')composePost(true);else if(plan.value.current==='share'&&plan.value.receipt)await startShare({id:plan.value.receipt.id});else if(plan.value.current==='booking')await planAction('book');else if(plan.value.current==='navigate'&&plan.value.receipt)await navigateBooking({id:plan.value.receipt.id});else if(plan.value.current==='checkin'){selectedBooking.value={id:plan.value.receipt.id};modal.value='checkin'}}
 async function navigateBooking(row){await run(async()=>{const result=await api('bookings/'+row.id+'/navigation');await openWeb(result.url);})}
 async function openWeb(path){if(!path.startsWith('/')||path.startsWith('//'))return;
 let target=path;try{if(getToken())target=(await api('web-ticket',{path})).url}catch(e){fail(e);return}
 // #ifdef H5
 window.location.assign(webBase()+target);
 // #endif
 // #ifndef H5
 uni.navigateTo({url:'/pages/web/index?path='+encodeURIComponent(target)});
 // #endif
 }
 function scan(){uni.scanCode({onlyFromCamera:true,success:r=>{qrText.value=r.result;submitCheckin()},fail:()=>toast('也可以粘贴签到二维码链接')})}
 async function submitCheckin(){await run(async()=>{const match=qrText.value.match(/\/booking\/(\d+)\/checkin\/\?[^#]*scan=([^&#]+)/);if(!match)throw new Error('请使用预约签到二维码');await api('bookings/'+match[1]+'/checkin',{token:decodeURIComponent(match[2])});modal.value='';qrText.value='';toast('签到成功');await go('bookings')})}
 async function readNotice(row){await run(async()=>{await api('notices',{kind:row.kind,id:row.pk});notices.value=notices.value.filter(x=>x!==row);await refreshOverview()})}
 async function followup(answer){if(!answer){health.answers={};health.request_key=requestKey()}if(!health.accepted_notice){toast('请先阅读并同意导诊说明');return}if(answer&&healthStep.value?.question)health.answers[healthStep.value.question.key||healthStep.value.question.id.split(':')[0]]=answer;await run(async()=>{healthStep.value=await api('health/followup',{...health});healthReply.value=''})}
 async function submitHealth(){await run(async()=>{healthStep.value=await api('health/assess',{...health,preview:false});toast('已交给医生核实')})}
 function closeModal(){if(!busy.value){modal.value='';peer.value=null}}
 let visible=true;onShow(()=>{visible=true});onHide(()=>{visible=false});const poller=setInterval(()=>{if(visible&&modal.value==='chat'&&peer.value&&!busy.value)loadMessages()},10000);onUnmounted(()=>clearInterval(poller));
 onMounted(async()=>{await boot();const saved=uni.getStorageSync('universe-mobile-weather');if(saved){try{weather.value=await api('weather',{place:saved})}catch{}}});
 return {section,drawer,modal,loading,busy,online,error,user,language,bootstrap,overview,weather,weatherBusy,city,cityChoices,weatherStatus,loginForm,passwordForm,venues,bookings,filters,selectedVenue,selectedBooking,posts,postCategory,postPage,morePosts,postForm,postDetail,friends,people,friendQuery,peer,messages,chatText,moments,momentText,errands,notices,assistant,plan,conversation,message,externalAllowed,planDay,planSlot,assistantDay,health,healthParts,healthStep,healthReply,qrText,title,floors,floorVenues,available,mainTabs,services,t,toast,boot,go,signIn,changePassword,signOut,setLanguage,locate,searchCity,selectCity,chooseFilter,chooseSeat,reserve,cancelBooking,filterPosts,nextPosts,composePost,publish,searchFriends,addFriend,chat,loadMessages,sendChat,publishMoment,startShare,shareTo,sendMessage,assistantSelect,confirmAssistant,planAction,continuePlan,navigateBooking,openWeb,scan,submitCheckin,readNotice,followup,submitHealth,closeModal};
}
