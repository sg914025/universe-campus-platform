package cn.universe.campus.preview;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;

/** Checks the intended campus entry without bypassing its access gate. Author: UniVerse Team. */
public final class SiteProbe {
    public enum Kind { MOBILE, LEGACY, ACCESS_REQUIRED, WRONG_SITE, HTTP_ERROR, NETWORK_ERROR }
    public static final class Result {
        public final Kind kind; public final int status; public final String url;
        Result(Kind kind,int status,String url){this.kind=kind;this.status=status;this.url=url;}
    }
    private static final class Response {
        int status;String url,type,body;
    }
    private static boolean campus(Response response){
        String text=response.body.toLowerCase(java.util.Locale.ROOT);
        return response.type.toLowerCase(java.util.Locale.ROOT).contains("text/html") &&
            !text.contains("<title>deploydesk") && (text.contains("寰校通")||text.contains("universe"));
    }
    public static Result check(String origin,String cookie,String userAgent){
        try{
            Response mobile=fetch(origin,origin+"/m/",cookie,userAgent);
            if(mobile.status==401||mobile.status==403)return new Result(Kind.ACCESS_REQUIRED,mobile.status,mobile.url);
            if(mobile.status==200&&campus(mobile))return new Result(Kind.MOBILE,200,mobile.url);
            if(mobile.status!=404&&mobile.status!=200)return new Result(Kind.HTTP_ERROR,mobile.status,mobile.url);
            Response home=fetch(origin,origin+"/",cookie,userAgent);
            if(home.status==401||home.status==403)return new Result(Kind.ACCESS_REQUIRED,home.status,home.url);
            if(home.status!=200)return new Result(Kind.HTTP_ERROR,home.status,home.url);
            return new Result(campus(home)?Kind.LEGACY:Kind.WRONG_SITE,home.status,home.url);
        }catch(Exception ex){return new Result(Kind.NETWORK_ERROR,0,origin);}
    }
    private static Response fetch(String origin,String first,String cookie,String userAgent)throws Exception {
        String current=first;
        for(int hop=0;hop<4;hop++){
            if(!ServerAddress.sameOrigin(origin,current)&&!ServerAddress.httpsUpgrade(origin,current))throw new java.io.IOException("Cross-origin redirect");
            HttpURLConnection connection=(HttpURLConnection)new URL(current).openConnection();
            connection.setConnectTimeout(7000);connection.setReadTimeout(7000);connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("User-Agent",userAgent);connection.setRequestProperty("Accept","text/html");
            if(cookie!=null&&!cookie.isEmpty())connection.setRequestProperty("Cookie",cookie);
            try{
                int status=connection.getResponseCode();
                if(status==301||status==302||status==303||status==307||status==308){
                    String location=connection.getHeaderField("Location");
                    if(location==null)throw new java.io.IOException("Missing redirect location");
                    current=new URI(current).resolve(location).toString();continue;
                }
                Response out=new Response();out.status=status;out.url=current;out.type=connection.getContentType()==null?"":connection.getContentType();out.body="";
                if(status==200){
                    try(InputStream input=connection.getInputStream();ByteArrayOutputStream bytes=new ByteArrayOutputStream()){
                        byte[] buffer=new byte[2048];int count;
                        while(bytes.size()<32768&&(count=input.read(buffer,0,Math.min(buffer.length,32768-bytes.size())))!=-1)bytes.write(buffer,0,count);
                        out.body=new String(bytes.toByteArray(),"UTF-8");
                    }
                }
                return out;
            }finally{connection.disconnect();}
        }
        throw new java.io.IOException("Too many redirects");
    }
}
