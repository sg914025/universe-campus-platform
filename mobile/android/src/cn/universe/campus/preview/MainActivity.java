package cn.universe.campus.preview;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.inputmethod.InputMethodManager;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import java.net.HttpURLConnection;
import java.net.URL;

/** Small Android host for the existing shared UI; all business data stays on Django. Author: UniVerse Team. */
public class MainActivity extends Activity {
    private static final int GREEN=0xff285b4a, BACKGROUND=0xfff7f8f2, MUTED=0xff7c8c80;
    private WebView web;
    private ProgressBar progress;
    private TextView subtitle, message;
    private LinearLayout overlay;
    private SharedPreferences preferences;
    private String origin, entry;
    private int generation;
    private ValueCallback<Uri[]> fileCallback;
    private GeolocationPermissions.Callback locationCallback;
    private String locationOrigin;
    private boolean fallbackAttempted;
    private Button accessButton,returnButton;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        preferences=getSharedPreferences("universe_connection",MODE_PRIVATE);
        String saved=preferences.getString("origin",BuildConfig.DEFAULT_ORIGIN);
        if(preferences.getInt("connection_schema",0)<2&&
            (saved.equals("http://47.117.71.139")||saved.equals("https://47.117.71.139"))){
            saved=BuildConfig.DEFAULT_ORIGIN;preferences.edit().putString("origin",saved).apply();
        }
        preferences.edit().putInt("connection_schema",2).apply();
        try { origin=ServerAddress.normalize(saved); }
        catch(IllegalArgumentException ex) { origin=BuildConfig.DEFAULT_ORIGIN; }
        entry=origin+"/m/";
        createLayout();
        configureWeb();
        if(state!=null&&web.restoreState(state)!=null&&ServerAddress.sameOrigin(origin,web.getUrl())) {
            overlay.setVisibility(View.GONE);
        } else connect();
    }

    private int dp(int value) { return Math.round(getResources().getDisplayMetrics().density*value); }
    private TextView label(String text,int size,int color,boolean bold) {
        TextView view=new TextView(this); view.setText(text); view.setTextSize(size); view.setTextColor(color);
        if(bold) view.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return view;
    }
    private Button button(String text,View.OnClickListener listener) {
        Button view=new Button(this); view.setText(text); view.setAllCaps(false); view.setTextColor(GREEN);
        view.setTextSize(14); view.setOnClickListener(listener); return view;
    }
    private void createLayout() {
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(BACKGROUND);
        root.setOnApplyWindowInsetsListener((view,insets)->{
            if(Build.VERSION.SDK_INT>=30){
                android.graphics.Insets edge=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());
                view.setPadding(edge.left,edge.top,edge.right,edge.bottom);
            } else view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        if(Build.VERSION.SDK_INT>=30) getWindow().setDecorFitsSystemWindows(false);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|(Build.VERSION.SDK_INT>=26?View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR:0));
        LinearLayout bar=new LinearLayout(this); bar.setGravity(Gravity.CENTER_VERTICAL); bar.setPadding(dp(12),0,dp(4),0);
        TextView star=label("✳",26,GREEN,true); star.setGravity(Gravity.CENTER); star.setContentDescription("返回校园首页"); star.setOnClickListener(v->connect());
        bar.addView(star,new LinearLayout.LayoutParams(dp(38),dp(48)));
        LinearLayout title=new LinearLayout(this); title.setOrientation(LinearLayout.VERTICAL); title.setPadding(dp(6),0,0,0);
        title.addView(label("寰校通 UniVerse",15,GREEN,true)); subtitle=label("正在连接校园",10,MUTED,false); subtitle.setSingleLine(true); title.addView(subtitle);
        bar.addView(title,new LinearLayout.LayoutParams(0,dp(42),1));
        returnButton=button("返回校园",v->connect());returnButton.setTextSize(12);returnButton.setMinWidth(0);returnButton.setMinimumWidth(0);returnButton.setVisibility(View.GONE);
        bar.addView(returnButton,new LinearLayout.LayoutParams(dp(84),dp(48)));
        Button menu=button("•••",v->showMenu()); menu.setContentDescription("连接设置与刷新"); menu.setMinWidth(0); menu.setMinimumWidth(0);
        bar.addView(menu,new LinearLayout.LayoutParams(dp(52),dp(48))); root.addView(bar,new LinearLayout.LayoutParams(-1,dp(54)));
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal); progress.setMax(100); root.addView(progress,new LinearLayout.LayoutParams(-1,dp(2)));
        FrameLayout body=new FrameLayout(this); web=new WebView(this); web.setBackgroundColor(BACKGROUND); body.addView(web,new FrameLayout.LayoutParams(-1,-1));
        overlay=new LinearLayout(this); overlay.setOrientation(LinearLayout.VERTICAL); overlay.setGravity(Gravity.CENTER); overlay.setBackgroundColor(BACKGROUND); overlay.setPadding(dp(28),dp(24),dp(28),dp(24));
        TextView logo=label("✳",64,GREEN,true); overlay.addView(logo); TextView welcome=label("你的校园，随时相连。",23,GREEN,true); welcome.setGravity(Gravity.CENTER); overlay.addView(welcome);
        message=label("正在连接公网校园服务…",14,MUTED,false); message.setGravity(Gravity.CENTER); message.setPadding(0,dp(18),0,dp(24)); overlay.addView(message);
        accessButton=button("进入访问验证",v->openAccessGate());accessButton.setVisibility(View.GONE);overlay.addView(accessButton,new LinearLayout.LayoutParams(-1,dp(52)));
        overlay.addView(button("重新连接",v->connect()),new LinearLayout.LayoutParams(-1,dp(52)));
        overlay.addView(button("服务器设置",v->showSettings()),new LinearLayout.LayoutParams(-1,dp(52)));
        TextView byline=label("UNIVERSE · 安卓体验版\n制作：UniVerse Team",11,MUTED,false); byline.setGravity(Gravity.CENTER); byline.setPadding(0,dp(40),0,0); overlay.addView(byline);
        body.addView(overlay,new FrameLayout.LayoutParams(-1,-1)); root.addView(body,new LinearLayout.LayoutParams(-1,0,1)); setContentView(root); root.requestApplyInsets();
    }
    private void configureWeb() {
        WebSettings settings=web.getSettings(); settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setUseWideViewPort(true); settings.setLoadWithOverviewMode(true); settings.setTextZoom(100);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(false); settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true); settings.setGeolocationEnabled(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(false); settings.setSupportMultipleWindows(false);
        settings.setUserAgentString(settings.getUserAgentString()+" UniVerseAndroid/"+BuildConfig.VERSION_NAME);
        if(Build.VERSION.SDK_INT>=26) settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptCookie(true); CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return navigate(request.getUrl().toString(),request.isForMainFrame());}
            @Override public boolean shouldOverrideUrlLoading(WebView view,String url){return navigate(url,true);}
            @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap icon){progress.setVisibility(View.VISIBLE);returnButton.setVisibility(ServerAddress.sameOrigin(accessOrigin(),url)?View.VISIBLE:View.GONE);}
            @Override public void onPageFinished(WebView view,String url){progress.setVisibility(View.GONE);CookieManager.getInstance().flush();}
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){
                if(request.isForMainFrame()) showError("暂时连接不上校园服务。\n请检查手机网络，或在设置中确认服务器地址。");
            }
            @Override public void onReceivedHttpError(WebView view,WebResourceRequest request,WebResourceResponse response){
                if(request.isForMainFrame()&&response.getStatusCode()>=400){
                    if((response.getStatusCode()==401||response.getStatusCode()==403)&&ServerAddress.sameOrigin(origin,request.getUrl().toString())){showAccessRequired();}
                    else if(response.getStatusCode()==404&&request.getUrl().getPath().equals("/m/")&&!fallbackAttempted){showError("移动版路径发生变化。\n请点击重新连接，重新检查校园入口。");}
                    else if(response.getStatusCode()>=500)showError("校园服务器暂时繁忙（"+response.getStatusCode()+"）。\n稍后可点击重新连接。");
                }
            }
            @Override public void onReceivedSslError(WebView view,android.webkit.SslErrorHandler handler,android.net.http.SslError error){
                handler.cancel();showError("服务器证书验证未通过。\n请检查手机日期或联系管理员更新证书。");
            }
            // Default TLS errors are cancelled by WebViewClient. Never bypass certificate validation.
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onProgressChanged(WebView view,int value){progress.setProgress(value);if(value==100)progress.setVisibility(View.GONE);}
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(!ServerAddress.sameOrigin(origin,view.getUrl()))return false;
                if(fileCallback!=null)fileCallback.onReceiveValue(null); fileCallback=callback;
                Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.addCategory(Intent.CATEGORY_OPENABLE);picker.setType("*/*");
                picker.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                try{startActivityForResult(Intent.createChooser(picker,"选择要上传的文件"),30);}catch(Exception ex){fileCallback.onReceiveValue(null);fileCallback=null;}
                return true;
            }
            @Override public void onGeolocationPermissionsShowPrompt(String requested,GeolocationPermissions.Callback callback){
                if(!ServerAddress.sameOrigin(origin,requested)||!ServerAddress.sameOrigin(origin,web.getUrl())){callback.invoke(requested,false,false);return;}
                new AlertDialog.Builder(MainActivity.this).setTitle("使用设备位置").setMessage("仅在你查询天气时，允许校园网站获取位置？")
                    .setNegativeButton("暂不允许",(dialog,which)->callback.invoke(requested,false,false))
                    .setOnCancelListener(dialog->callback.invoke(requested,false,false))
                    .setPositiveButton("允许本次",(dialog,which)->{
                        if(checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED){callback.invoke(requested,true,false);}
                        else {locationOrigin=requested;locationCallback=callback;requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION},31);}
                    }).show();
            }
        });
        web.setDownloadListener((url,userAgent,contentDisposition,mimetype,length)->external(url));
    }
    private boolean navigate(String url,boolean mainFrame){
        if(ServerAddress.internalNavigation(origin,accessOrigin(),url))return false;
        if(mainFrame)external(url);return true;
    }
    private void external(String url){
        try{Uri uri=Uri.parse(url);String scheme=uri.getScheme();if(!"https".equals(scheme)&&!"http".equals(scheme)&&!"tel".equals(scheme)&&!"mailto".equals(scheme))return;
            startActivity(new Intent(Intent.ACTION_VIEW,uri));
        }catch(Exception ex){Toast.makeText(this,"没有可打开此链接的应用",Toast.LENGTH_SHORT).show();}
    }
    private void connect(){
        if(ServerAddress.httpsUpgrade(origin,BuildConfig.DEFAULT_ORIGIN)){origin=BuildConfig.DEFAULT_ORIGIN;preferences.edit().putString("origin",origin).apply();}
        int current=++generation;fallbackAttempted=false;web.stopLoading();accessButton.setVisibility(View.GONE);returnButton.setVisibility(View.GONE);
        overlay.setVisibility(View.VISIBLE);message.setText("正在连接校园项目…");subtitle.setText(origin);
        final String project=origin,cookies=CookieManager.getInstance().getCookie(origin+"/m/"),userAgent=web.getSettings().getUserAgentString();
        new Thread(()->{
            final SiteProbe.Result result=SiteProbe.check(project,cookies,userAgent);
            runOnUiThread(()->{
                if(isFinishing()||isDestroyed()||current!=generation)return;
                switch(result.kind){
                    case MOBILE:case LEGACY:
                        if(ServerAddress.httpsUpgrade(origin,result.url)){origin=ServerAddress.originOf(result.url);preferences.edit().putString("origin",origin).apply();}
                        loadEntry(result.kind==SiteProbe.Kind.MOBILE,result.url);break;
                    case ACCESS_REQUIRED:showAccessRequired();break;
                    case WRONG_SITE:showError("这个地址没有返回寰校通页面。\n请在服务器设置中填写校园项目完整地址（包括端口）。");break;
                    case HTTP_ERROR:showError("校园服务暂不可用（HTTP "+result.status+"）。\n请稍后重试或检查项目部署。");break;
                    default:showError("暂时连接不上校园服务。\n请检查手机网络、服务器地址与证书状态。");
                }
            });
        },"universe-connect").start();
    }
    private void loadEntry(boolean mobile,String url){
        fallbackAttempted=!mobile;entry=url;subtitle.setText(mobile?"移动版 · 公网已连接":"校园网站 · 新移动版待部署");
        overlay.setVisibility(View.GONE);web.loadUrl(entry);
        if(!mobile)Toast.makeText(this,"新移动版尚未部署，先打开现有校园网站",Toast.LENGTH_LONG).show();
    }
    private String accessOrigin(){return ServerAddress.sameOrigin(origin,BuildConfig.DEFAULT_ORIGIN)?BuildConfig.ACCESS_ORIGIN:"";}
    private void showAccessRequired(){
        String gate=accessOrigin();showError(gate.isEmpty()?"网站要求访问验证或当前账号没有权限（403）。\n请先通过该站点的正常入口。":"校园项目需要先通过 DeployDesk 入口验证。\n\n点击下方按钮，在 App 内完成验证或登录，再点顶部「返回校园」。\n\n手机浏览器的登录状态不会自动带入 App。");
        subtitle.setText("需要访问验证");accessButton.setVisibility(gate.isEmpty()?View.GONE:View.VISIBLE);
    }
    private void openAccessGate(){String gate=accessOrigin();if(gate.isEmpty())return;generation++;web.stopLoading();overlay.setVisibility(View.GONE);returnButton.setVisibility(View.VISIBLE);subtitle.setText("完成入口验证后，点「返回校园」");web.loadUrl(gate+"/");}
    private void showError(String text){progress.setVisibility(View.GONE);accessButton.setVisibility(View.GONE);message.setText(text);subtitle.setText("连接未完成");overlay.setVisibility(View.VISIBLE);}
    private void showMenu(){
        new AlertDialog.Builder(this).setTitle("寰校通 UniVerse").setItems(new String[]{"校园首页 / 检查新版","刷新当前页面","服务器地址","在浏览器中打开","关于安卓体验版"},(dialog,which)->{
            switch(which){case 0:connect();break;case 1:overlay.setVisibility(View.GONE);web.reload();break;case 2:showSettings();break;case 3:external(web.getUrl()!=null?web.getUrl():entry);break;default:new AlertDialog.Builder(this).setTitle("寰校通 UniVerse "+BuildConfig.VERSION_NAME).setMessage("制作：UniVerse Team\n\n本体验包使用 Android WebView 打开同一套校园服务。业务数据和网页更新跟随服务器。\n\n服务器："+origin+"\n\n尚未进行 Android 真机验收。网页扫码可用时依浏览器能力；保留签到链接与手动选城入口。").setPositiveButton("知道了",null).show();}
        }).show();
    }
    private void showSettings(){
        LinearLayout content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(dp(24),dp(10),dp(24),0);
        TextView help=label("填写手机可访问的公网地址。只填域名或 IP，优先使用 HTTPS。",14,MUTED,false);content.addView(help);
        EditText input=new EditText(this);input.setSingleLine(true);input.setText(origin);input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);content.addView(input);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("服务器地址").setView(content).setNegativeButton("取消",null).setPositiveButton("保存并连接",null).create();
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            try{String value=ServerAddress.normalize(input.getText().toString());origin=value;preferences.edit().putString("origin",value).apply();
                ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(input.getWindowToken(),0);dialog.dismiss();web.clearHistory();connect();
            }catch(IllegalArgumentException ex){input.setError(ex.getMessage());}
        }));dialog.show();
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==31&&locationCallback!=null){boolean allow=false;for(int result:results)allow|=result==PackageManager.PERMISSION_GRANTED;
            locationCallback.invoke(locationOrigin,allow&&ServerAddress.sameOrigin(origin,locationOrigin),false);locationCallback=null;}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);if(request==30&&fileCallback!=null){
            Uri[] uris=null;if(result==RESULT_OK&&data!=null){if(data.getClipData()!=null){uris=new Uri[data.getClipData().getItemCount()];for(int i=0;i<uris.length;i++)uris[i]=data.getClipData().getItemAt(i).getUri();}else if(data.getData()!=null)uris=new Uri[]{data.getData()};}
            fileCallback.onReceiveValue(uris);fileCallback=null;
        }
    }
    @Override public void onBackPressed(){if(overlay.getVisibility()!=View.VISIBLE&&web.canGoBack())web.goBack();else new AlertDialog.Builder(this).setMessage("退出寰校通？").setNegativeButton("继续使用",null).setPositiveButton("退出",(d,w)->finish()).show();}
    @Override protected void onSaveInstanceState(Bundle state){web.saveState(state);super.onSaveInstanceState(state);}
    @Override protected void onPause(){super.onPause();web.onPause();CookieManager.getInstance().flush();}
    @Override protected void onResume(){super.onResume();if(web!=null)web.onResume();}
    @Override protected void onDestroy(){generation++;if(fileCallback!=null)fileCallback.onReceiveValue(null);if(locationCallback!=null)locationCallback.invoke(locationOrigin,false,false);web.stopLoading();web.destroy();super.onDestroy();}
}
