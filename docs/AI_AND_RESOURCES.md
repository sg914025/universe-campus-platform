# AI 与第三方资源

## 模型与资料

- Qwen3-4B：由 Qwen 提供的预训练语言模型，项目以 Ollama 的 `qwen3:4b` 调用，现有环境采用 GGUF / Q4_K_M。上游：https://huggingface.co/Qwen/Qwen3-4B 。模型权重不随 Git 仓库分发。
- Ollama：本地模型运行服务。结构化输出说明：https://docs.ollama.com/capabilities/structured-outputs 。
- MedlinePlus / Genetics：NLM 公开健康与遗传病资料，当前摘要集为 1016 + 1305 = 2321 条，导入日期 2026-10-11。来源：https://medlineplus.gov/xml.html 。本地检索采用部位与主题词、别名、标题词匹配排序；没有向量数据库，不将摘要导入称为权重训练。
- 语音：中英日与俄语按现有资源分别使用 GPT-SoVITS / XTTS 相关路径。预生成问候、浏览器语音输入、实时合成分别运行。仓库仅含前端接口及已有音频，未打包语音模型权重和独立引擎环境。

## 组件及素材

Django、uni-app、Vue、Vite、Three.js、PixiJS 及其他组件遵循各自许可证。移动端列表见 `mobile/THIRD_PARTY_NOTICES.md`；服务端静态目录中保留上游许可证、来源及 NOTICE；既有 Live2D 来源见 `server/Live2D模型来源说明.txt`。素材来源声明不把第三方素材改称团队原创，也不对未明确授权的角色素材授予额外使用权。

校园空间为程序化示意；人体外形、内脏与骨骼视图用于部位选择，不处理患者医学影像。项目的工作在校园业务集成、四语交互、结构化追问与服务衔接；本版本使用预训练模型推理和资料检索，未实施医疗专项 LoRA 微调。
