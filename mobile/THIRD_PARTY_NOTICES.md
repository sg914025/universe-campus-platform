# 第三方来源

文档整理：UniVerse Team

项目使用以下开源组件；原创项目署名不覆盖这些组件的作者与许可证。

| 组件 | 上游 | 许可证 |
|---|---|---|
| uni-app / @dcloudio packages | https://github.com/dcloudio/uni-app | Apache-2.0，具体包以其 LICENSE 为准 |
| uni-preset-vue 构建配置参考 | https://github.com/dcloudio/uni-preset-vue | 以上游仓库声明为准 |
| Vue 3 | https://github.com/vuejs/core | MIT |
| Vite | https://github.com/vitejs/vite | MIT |
| Rollup | https://github.com/rollup/rollup | MIT |
| vue-i18n | https://github.com/intlify/vue-i18n | MIT |
| npm CLI（本机安装辅助） | https://github.com/npm/cli | Artistic-2.0 与所含依赖许可证 |
| Django（既有后台） | https://www.djangoproject.com/ | BSD-3-Clause |

锁定版本和完整依赖树见 `package-lock.json`。`node_modules` 及 `.tools/package` 内的许可证文件保留；导出源码时不应改写第三方作者信息。

`src/static/icons` 为本次绘制的几何图标，作者UniVerse Team；没有使用第三方插画或将地图平台截图作为客户端素材。3D 校园地图通过原项目运行，原资产与其来源说明仍在原项目中。

AI 辅助用于代码、布局与界面文案草拟；业务能力和验证范围按验收记录如实说明。

Android 体验包使用 Android 系统 WebView；Google Android SDK 工具与原始许可、NOTICE 保留在 .tools/android-sdk，仅用于构建，不将其作者改为本项目作者。默认复用已安装的 JetBrains Runtime，不把 JBR 放入 APK。原创 Android 容器、脚本及文档作者：UniVerse Team。
