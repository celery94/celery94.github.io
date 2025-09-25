---
pubDatetime: 2025-09-25
title: Mindcraft：用多智能体 LLM 驱动 Minecraft 协作实验平台
description: Mindcraft 通过 Mineflayer 与多家 LLM 服务，把多智能体带入 Minecraft，支持任务评测、代码扩展与 Docker 沙箱。本文梳理核心组件、部署流程、安全要点与常见陷阱，帮助研发团队构建具身智能实验平台。
tags: ["AI", "Agents", "Minecraft", "Node.js", "LLM"]
slug: mindcraft-llm-minecraft-platform
source: https://github.com/mindcraft-bots/mindcraft
draft: false
featured: false

---

## 背景与问题

具身智能与多智能体协作是当前大模型应用的前沿方向，但从零搭建一个可信赖的实验环境成本极高：需要处理 Minecraft 与控制框架之间的联动、调度多家模型 API、还要提供可重复的任务与评价指标。Mindcraft 项目整合 Mineflayer、Node.js 与 Python 任务套件，把 Minecraft 世界变成可编程的具身协作试验场，为研究团队和工程团队提供了测试代理协作、探索行动推理与行为计划的统一基座。

## 核心概念与原理

Mindcraft 的核心由三个层面构成。最底层是 Mineflayer 客户端，它负责与 Minecraft Java 版世界进行实时交互，并通过补丁优化的路径规划执行移动、采集与建造等动作。中间层是 Node.js 控制器，读取 `settings.js` 与 `profiles/*.json` 中定义的代理角色，按配置选择 OpenAI、Gemini、Claude、DeepSeek、Ollama 等多种 LLM API，分别承担对话、代码生成、视觉理解与向量检索任务；通过 `model`、`code_model`、`vision_model` 等字段可以灵活组合不同推理能力。最上层是 MineCollab 任务体系，提供烹饪、建造、合成三大场景，通过 JSON 任务文件预置目标、初始物资、禁用动作和超时阈值，实现可重复的协作评测。

## 实战与代码示例

部署 Mindcraft 需要同时满足游戏与推理两类依赖。首先准备 Minecraft Java Edition（推荐 v1.21.1）并在本地开启局域网世界，同时安装 Node.js ≥ 18 以及至少一个模型供应商的 API Key。克隆仓库后，把 `keys.example.json` 重命名为 `keys.json` 并填入密钥，启动流程如下：

```bash
npm install
node main.js --profiles ./profiles/andy.json
```

配置文件中可以为不同能力指定对应模型，下面示例把对话与代码分别委派给 OpenAI 与 Mistral，并启用本地 Ollama 向量嵌入，用于从经验库检索合适范例：

```json
{
  "model": {
    "api": "openai",
    "model": "gpt-4o-mini",
    "params": { "temperature": 0.7 }
  },
  "code_model": {
    "api": "mistral",
    "model": "mistral-large-latest"
  },
  "embedding": {
    "api": "ollama",
    "model": "embeddinggemma"
  }
}
```

当需要批量评测协作任务时，安装 Python 依赖后即可调用官方脚本，脚本会自动拉起 Minecraft 服务、加载任务定义并统计完成度：

```bash
pip install -r requirements.txt
python tasks/evaluation_script.py \
  --task_path tasks/crafting_tasks/test_tasks/2_agent.json \
  --model gpt-4o-mini \
  --template_profile profiles/tasks/crafting_profile.json
```

## 常见陷阱与最佳实践

Mindcraft 允许代理生成并执行 JavaScript 代码，若启用 `allow_insecure_coding`，务必使用 Docker 容器隔离运行环境，并在 `settings.js` 中把服务器地址改为 `host.docker.internal` 以映射宿主机的 Minecraft 世界。连接错误通常来自游戏未开启 LAN、端口号与配置不一致或客户端版本不匹配，排查顺序应从游戏设置到 `settings.js` 的 `host` 与 `version` 字段。API 密钥无效大多是 `keys.json` 未保存或路径引用错误，可删除 `node_modules` 重新安装确保补丁生效。Mineflayer 的路径规划在复杂地形仍可能卡住，建议通过任务配置限制地形复杂度，或在代理提示中加入纠错步骤以减少重复动作。

## 总结与参考资料

Mindcraft 将多智能体推理、可重现任务与具身交互整合在同一平台，为验证“行动-观察-计划-协作”循环提供了真实世界（Minecraft）级别的实验场。通过合理配置模型组合、隔离执行环境并利用任务套件的评测能力，团队能够在短时间内搭建具身智能的研究与工程原型，并将结果量化为可比较的表现指标。

参考资料：

1. [Mindcraft GitHub 仓库 README](https://github.com/mindcraft-bots/mindcraft)
2. [MineCollab 任务说明文档](https://github.com/mindcraft-bots/mindcraft/blob/main/minecollab.md)
3. [Mindcraft 常见问题解答](https://github.com/mindcraft-bots/mindcraft/blob/main/FAQ.md)
