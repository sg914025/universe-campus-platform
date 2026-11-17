# 寰校通 Android 体验包 · 1.0.2

作者 / 制作：UniVerse Team

安装 `寰校通UniVerse-安卓体验版-1.0.2.apk`，可以直接覆盖旧版，使用同一个测试签名。

## 手机首次打开

1. App 已配置校园项目地址 `https://47.117.71.139:8080`。
2. 若显示「需要访问验证」，点击 **进入访问验证**。
3. 在 App 内完成 DeployDesk 的正常入口验证或账号登录。验证码、姓名、告知与同意由你本人填写和确认，App 不会自动代填或绕过。
4. 完成后点顶部 **返回校园**，App 会使用同一份 Cookie 会话检查并打开校园项目。
5. 如果当前账号没有项目访问权限，需要由项目管理员按原有规则授权，App 不会关闭访问限制。

不要为了验证先切换到手机浏览器：手机浏览器与 App 的 Cookie 不共享。校园网站自身的账号登录与 DeployDesk 入口验证是两个步骤。入口会话失效时，按上述流程重新验证。

## 此次修复

- 项目入口补齐 `:8080`，并直接使用 HTTPS。此前默认 IP 根目录指向 DeployDesk 管理界面，首页 HTTP 200 不代表校园网站可访问；已更正判断。
- 允许明确配置的校园项目和验证入口在同一个 WebView 中导航，同一站点的 HTTP → HTTPS 升级也会留在 App 中。
- 403/401 显示访问验证指引，不再误报「新版未部署」或盲目跳回管理首页。
- 页面探测使用 App 自己的会话，只向明确的目标发送；拒绝向其他站点转发 Cookie、拒绝降级和无限重定向。
- 仅当页面身份确认是寰校通时，才判定校园服务已连接。旧设置中错误的 IP 根地址会迁移到正确项目地址。

2026-10-22 未登录复测：项目入口 `/`、`/m/` 均返回 Nginx 403；这表明入口验证正在生效，不能据此判断新版 `/m/` 是否部署。未代替用户通过生产验证码、接受告知或登录账户，因此不声称已验收生产登录后的完整流程。

## 更新与构建

这个 APK 使用 Android 系统 WebView 打开共用校园网站。页面和业务随服务器更新；`dist/build/app` 中的 uni-app 原生资源工程也继续保留。它们是不同的构建产物。

默认服务器在 `config/project.json` 的 `androidServerOrigin`，验证入口在 `androidAccessOrigin`。手机右上角「••• → 服务器地址」也可修改项目地址；连接另一个项目时不会把本项目验证入口自动套用过去。

- `07-生成安卓APK.cmd`：只重建安装包。
- `03-一键更新三端.cmd` / `05-仅构建App资源.cmd`：生成 App 资源后，同时重建 APK。
- 版本读取统一配置的 `version`。
- `.tools/android-sdk` 包含 Google 官方构建工具及原始第三方许可。
- 默认复用本机 `JAVA_HOME` 指定的 JDK。换机可用 `JAVA_HOME` 和 `UNIVERSE_ANDROID_SDK` 指定环境。
- 临时编译文件放在 系统临时目录下的 `universe-android-build`，规避旧 aapt 的中文路径问题；可用 `UNIVERSE_ANDROID_BUILD_TEMP` 指定其他纯英文路径。
- `android/signing/universe-test.jks` 是本地测试签名，已加入忽略列表且未打入 APK。保留此密钥可覆盖安装后续同签名测试版；应用商店发布另行准备正式签名。

## 已验证与待真机确认

- 32 项地址和导航边界测试、17 项真实本机 HTTP 夹具测试通过：包括 403 指引、会话回传、正确/错误站点识别、Cookie 不跨站转发、重定向上限。
- Java、DEX、Android 资源编译通过，v1/v2/v3 签名、ZIP 对齐、启动 Activity、包名及文件完整性验证通过。
- 证书署名为UniVerse Team。支持 Android 6.0（API 23）及以上；依赖手机网络、系统 WebView 和受信任证书。
- 尚未在 Android 真机或模拟器上启动此修复版。首次生产入口验证由用户在手机完成。
- 不绕过 TLS 证书校验，不嵌入登录凭据，不修改服务端权限。设备定位由网站发起并经用户同意；网页能力仍受系统 WebView 支持范围影响。

官方参考：[Android WebView](https://developer.android.com/develop/ui/views/layout/webapps/webview)、[APK 签名验证](https://developer.android.com/tools/apksigner)。
