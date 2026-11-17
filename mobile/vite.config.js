import {defineConfig} from 'vite';
import uni from '@dcloudio/vite-plugin-uni';
const target=process.env.UNIVERSE_DEV_BACKEND||'http://127.0.0.1:8000';
const paths=['/api','/mobile/bridge','/campus-map','/journey','/guide','/errands','/forum','/booking','/my-services','/static','/media','/campus-media','/login','/accounts'];
export default defineConfig({plugins:[(typeof uni==='function'?uni:uni.default)()],server:{port:5178,strictPort:true,host:'127.0.0.1',proxy:Object.fromEntries(paths.map(path=>[path,{target,changeOrigin:true}]))}});
