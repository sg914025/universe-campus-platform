import cn.universe.campus.preview.SiteProbe;
import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;
import java.net.InetSocketAddress;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicInteger;

/** Real local HTTP fixtures, never authenticates with a production server. Author: UniVerse Team. */
public class SiteProbeTest {
    static int count;static volatile int mode,roots,foreignRequests;static String base,foreign;
    static void check(boolean ok){if(!ok)throw new AssertionError("case "+(count+1)+" mode "+mode);count++;}
    static void reply(HttpExchange x,int status,String body)throws IOException{
        byte[] bytes=body.getBytes("UTF-8");x.getResponseHeaders().set("Content-Type","text/html; charset=utf-8");x.sendResponseHeaders(status,bytes.length);x.getResponseBody().write(bytes);x.close();
    }
    static void handle(HttpExchange x)throws IOException{
        String path=x.getRequestURI().getPath();boolean cookie="desk_entry=fake-test-only".equals(x.getRequestHeaders().getFirst("Cookie"));
        if(path.equals("/")){roots++;reply(x,200,mode==4?"<title>DeployDesk · 项目部署工作台</title>":"<title>寰校通 UniVerse</title>");return;}
        if(mode==0){reply(x,200,"<title>寰校通 UniVerse</title>");return;}
        if(mode==1){reply(x,403,"Forbidden");return;}
        if(mode==2||mode==4){reply(x,404,"Not found");return;}
        if(mode==3){reply(x,cookie?200:403,cookie?"<title>寰校通 UniVerse</title>":"Forbidden");return;}
        if(mode==5){if(path.equals("/m/")){x.getResponseHeaders().set("Location","/mobile/");reply(x,302,"");}else reply(x,cookie?200:403,"<title>寰校通 UniVerse</title>");return;}
        if(mode==6){x.getResponseHeaders().set("Location",foreign+"/leak/");reply(x,302,"");return;}
        if(mode==7){x.getResponseHeaders().set("Location","/m/");reply(x,302,"");return;}
        if(mode==8){reply(x,503,"Unavailable");return;}
        if(mode==9){reply(x,401,"Login required");return;}
        reply(x,200,"<title>DeployDesk · 项目部署工作台</title>");
    }
    static SiteProbe.Result probe(int value,String cookie){mode=value;roots=0;return SiteProbe.check(base,cookie,"UniVerseTest/1.0");}
    public static void main(String[] args)throws Exception{
        HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0),other=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/",SiteProbeTest::handle);other.createContext("/",x->{foreignRequests++;reply(x,200,"foreign");});server.start();other.start();
        base="http://127.0.0.1:"+server.getAddress().getPort();foreign="http://127.0.0.1:"+other.getAddress().getPort();
        try{
            check(probe(0,"").kind==SiteProbe.Kind.MOBILE);
            check(probe(1,"").kind==SiteProbe.Kind.ACCESS_REQUIRED);check(roots==0);
            check(probe(2,"").kind==SiteProbe.Kind.LEGACY);check(roots==1);
            check(probe(3,"").kind==SiteProbe.Kind.ACCESS_REQUIRED);
            check(probe(3,"desk_entry=fake-test-only").kind==SiteProbe.Kind.MOBILE);
            check(probe(4,"").kind==SiteProbe.Kind.WRONG_SITE);
            check(probe(5,"desk_entry=fake-test-only").kind==SiteProbe.Kind.MOBILE);
            check(probe(6,"desk_entry=fake-test-only").kind==SiteProbe.Kind.NETWORK_ERROR);check(foreignRequests==0);
            check(probe(7,"").kind==SiteProbe.Kind.NETWORK_ERROR);
            SiteProbe.Result down=probe(8,"");check(down.kind==SiteProbe.Kind.HTTP_ERROR&&down.status==503);check(roots==0);
            check(probe(9,"").kind==SiteProbe.Kind.ACCESS_REQUIRED);check(roots==0);
            check(probe(10,"").kind==SiteProbe.Kind.LEGACY);
            System.out.println(count+" HTTP entry, permission and cookie-isolation cases passed.");
        }finally{server.stop(0);other.stop(0);}
    }
}
