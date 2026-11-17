package cn.universe.campus.preview;

import java.net.URI;

/** Origin validation shared with command-line tests. Author: UniVerse Team. */
public final class ServerAddress {
    private ServerAddress() {}
    public static String normalize(String input) {
        String value=input==null?"":input.trim();
        if (value.isEmpty()) throw new IllegalArgumentException("请输入服务器地址");
        if (!value.contains("://")) value="http://"+value;
        try {
            URI uri=new URI(value);
            String scheme=uri.getScheme().toLowerCase();
            if ((!scheme.equals("http")&&!scheme.equals("https")) || uri.getHost()==null ||
                uri.getRawUserInfo()!=null || uri.getRawQuery()!=null || uri.getRawFragment()!=null ||
                (uri.getRawPath()!=null&&!uri.getRawPath().isEmpty()&&!uri.getRawPath().equals("/")) ||
                uri.getPort()>65535 || uri.getPort()==0) throw new IllegalArgumentException();
            if (uri.getHost().equals("127.0.0.1")||uri.getHost().equalsIgnoreCase("localhost")||
                uri.getHost().equals("[::1]")) throw new IllegalArgumentException();
            return new URI(scheme,null,uri.getHost().toLowerCase(),uri.getPort(),null,null,null).toString();
        } catch(Exception ex) { throw new IllegalArgumentException("请填写手机可访问的 http(s) 服务器地址，不含路径、密码或参数"); }
    }
    public static boolean sameOrigin(String origin,String url) {
        try {
            URI a=new URI(origin),b=new URI(url);
            return b.getRawUserInfo()==null && a.getScheme().equalsIgnoreCase(b.getScheme()) &&
                a.getHost().equalsIgnoreCase(b.getHost()) && port(a)==port(b);
        } catch(Exception ex) { return false; }
    }
    public static boolean httpsUpgrade(String origin,String url) {
        try {
            URI a=new URI(origin),b=new URI(url);
            return "http".equalsIgnoreCase(a.getScheme()) && "https".equalsIgnoreCase(b.getScheme()) &&
                b.getRawUserInfo()==null && a.getHost().equalsIgnoreCase(b.getHost()) &&
                ((port(a)==80&&port(b)==443)||(a.getPort()>0&&a.getPort()==b.getPort()));
        }catch(Exception ex){return false;}
    }
    public static boolean internalNavigation(String project,String gateway,String url) {
        return sameOrigin(project,url)||httpsUpgrade(project,url)||
            (gateway!=null&&!gateway.isEmpty()&&sameOrigin(gateway,url));
    }
    public static String originOf(String url) {
        try{URI u=new URI(url);return new URI(u.getScheme(),null,u.getHost(),u.getPort(),null,null,null).toString();}
        catch(Exception ex){throw new IllegalArgumentException("Invalid URL");}
    }
    private static int port(URI uri) { return uri.getPort()!=-1?uri.getPort():("https".equalsIgnoreCase(uri.getScheme())?443:80); }
}
