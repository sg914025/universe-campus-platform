import cn.universe.campus.preview.ServerAddress;

/** Security and phone-connectivity regression cases. Author: UniVerse Team. */
public class ServerAddressTest {
    static int count;
    static void check(boolean pass){if(!pass)throw new AssertionError("case "+(count+1));count++;}
    static void rejects(String input){try{ServerAddress.normalize(input);throw new AssertionError("accepted "+input);}catch(IllegalArgumentException good){count++;}}
    public static void main(String[] args){
        check(ServerAddress.normalize("47.117.71.139").equals("http://47.117.71.139"));
        check(ServerAddress.normalize(" https://example.org/ ").equals("https://example.org"));
        check(ServerAddress.normalize("http://192.168.1.2:8000").equals("http://192.168.1.2:8000"));
        for(String bad:new String[]{"", "javascript:alert(1)","file:///sdcard/key","https://user:password@example.org","https://example.org/m/","https://example.org?token=x","https://example.org#token","127.0.0.1:8000","localhost:8000","http://[::1]","https://bad host","http://example.org:99999"})rejects(bad);
        check(ServerAddress.sameOrigin("https://example.org","https://example.org/m/"));
        check(ServerAddress.sameOrigin("https://example.org","https://example.org:443/m/"));
        check(!ServerAddress.sameOrigin("https://example.org","http://example.org/m/"));
        check(!ServerAddress.sameOrigin("https://example.org","https://example.org.evil.test/"));
        check(!ServerAddress.sameOrigin("https://example.org","https://example.org:8443/"));
        check(!ServerAddress.sameOrigin("https://example.org","https://x@example.org/"));
        check(!ServerAddress.sameOrigin("https://example.org","javascript:alert(1)"));
        check(ServerAddress.httpsUpgrade("http://47.117.71.139","https://47.117.71.139/"));
        check(ServerAddress.httpsUpgrade("http://47.117.71.139:8080","https://47.117.71.139:8080/m/"));
        check(!ServerAddress.httpsUpgrade("http://47.117.71.139:8080","https://47.117.71.139:8443/"));
        check(!ServerAddress.httpsUpgrade("https://47.117.71.139:8080","http://47.117.71.139:8080/"));
        check(!ServerAddress.httpsUpgrade("http://47.117.71.139","https://47.117.71.139.evil.test/"));
        check(!ServerAddress.httpsUpgrade("http://47.117.71.139","https://evil@47.117.71.139/"));
        check(ServerAddress.internalNavigation("https://47.117.71.139:8080","https://47.117.71.139","https://47.117.71.139/"));
        check(ServerAddress.internalNavigation("https://47.117.71.139:8080","https://47.117.71.139","https://47.117.71.139:8080/login/"));
        check(!ServerAddress.internalNavigation("https://47.117.71.139:8080","https://47.117.71.139","https://47.117.71.139:8443/"));
        check(!ServerAddress.internalNavigation("https://47.117.71.139:8080","","https://47.117.71.139/"));
        System.out.println(count+" URL and origin safety cases passed.");
    }
}
