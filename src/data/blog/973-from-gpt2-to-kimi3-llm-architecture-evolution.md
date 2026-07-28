---
pubDatetime: 2026-07-28T07:56:44+08:00
title: "从 GPT-2 到 KimiK3：七年 22580 倍的架构演进"
description: "从 GPT-2 的 softmax attention 出发，历经 Linear Attention、DeltaNet、Gated DeltaNet、Kimi Linear，最终到达 KimiK3 的混合架构。七年内模型参数增长 22580 倍，但真正的变化发生在注意力机制如何存储、更新和检索信息的方式上。"
tags: ["llm", "transformer", "attention", "deep-learning", "architecture", "research", "kimi", "gpt"]
slug: "from-gpt2-to-kimi3-llm-architecture-evolution"
ogImage: "../../assets/973/01-cover.png"
source: "https://x.com/waterloo_intern/status/2081762065392541951"
---

22580。这是 2019 年的 GPT-2 模型数量，能完整塞进 2026 年的最新 KimiK3 里。七年，两万两千五百八十倍。但这一切只是「放大」吗？

ali（@waterloo_intern）在 X 上发表了一篇深度 worklog，从 GPT-2 的源码出发，一步步追溯了从标准 softmax attention 到 KimiK3 混合架构的完整技术演进。这不是一篇参数规模的炫耀帖，而是一份关于**注意力机制如何逐步改变模型存储、更新和检索信息方式**的技术路线图。

每一步架构变更都在解决一个具体问题：矩阵乘法太贵、KV 缓存太大、记忆写死了删不掉、跨层信息流太单一。每一个方案都引出了下一个问题，最终堆叠成今天的样子。以下按原文的演进顺序展开。

## GPT-2：一切从 decoder-only 开始

GPT-2 的架构在今天看来朴素得几乎像教科书。decoder-only：token embedding + position embedding，送进 12 层 transformer block，每个 block 里一层 causal self-attention 加一层 MLP，最后过 layer norm 接 lm_head 出 logits。

```python
tok_emb = self.transformer.wte(idx)   # (b, t, n_embd)
pos_emb = self.transformer.wpe(pos)   # (t, n_embd)
x = self.transformer.drop(tok_emb + pos_emb)
for block in self.transformer.h:
    x = block(x)
x = self.transformer.ln_f(x)
logits = self.lm_head(x)
```

每个 block 内部：

```python
class Block(nn.Module):
    def __init__(self, config):
        self.ln_1 = LayerNorm(config.n_embd)
        self.attn = CausalSelfAttention(config)
        self.ln_2 = LayerNorm(config.n_embd)
        self.mlp = MLP(config)

    def forward(self, x):
        x = x + self.attn(self.ln_1(x))
        x = x + self.mlp(self.ln_2(x))
        return x
```

attention 的过程是经典的 Q·Kᵀ·V——query 和 key 点积、除以 sqrt(d)、softmax、乘以 value。GPT-2 的配置很袖珍：`vocab_size=50304`、`n_layer=12`、`n_head=12`、`n_embd=768`。

这里有一个 decoder-only 模型的天然低效点：每次 decode 步骤，模型确实为所有输入位置计算了表示，但只消费最后一个位置的 logits 来预测下一个 token。如果不缓存中间结果，下一个 token 会重复计算前面所有 token 的投影——这就是 KV cache 的由来。它把之前的 key 和 value 向量存下来，避免重复计算，但也会大到成为内存带宽瓶颈。

GPT-2 的总参数量约 1.24 亿。KimiK3 是 2.8 万亿。按参数量算，确实能塞 22580 个 GPT-2。但规模之外，注意力机制本身经历了更根本的变化。

## Linear Attention：打破 O(N²)

Softmax attention 在 Q·K 乘积之后才施加非线性，这让每个 query 和每个 key 形成耦合。标准注意力对序列长度 N 是 O(N²) 的——N 翻倍，计算量翻四倍。

Linear Attention 的思路简单但关键：**把非线性移到 Q·K 乘积之前**。用一个特征映射（比如 ELU+1）分别作用在 Q 和 K 上，使得乘积变得可重新结合：

```python
q = F.elu(q) + 1
k = F.elu(k) + 1
# 原本是 q @ k.T，现在是 (q @ k.T) 但 q 和 k 各自先过了特征映射
```

这个可重排性质意味着不断增长的 K 和 V 向量集合可以被折叠进一个固定尺寸的 D×D 状态矩阵中——就像循环神经网络的隐藏状态，每步只做固定量的计算，而不是重扫全部历史。很多资料把这个描述为「每步 O(N)」，原作者指出这种说法容易误导：系统状态确实随序列长度增长，但每步更新是常数时间。

```python
S = S + k @ v          # 累积状态
o = q @ S              # 检索
```

## DeltaNet：让记忆可以被精确改写

纯粹累加的状态有一个根本局限：后面的信息直接叠加在前面的信息上，无法删改。当序列长度超过存储容量时，模型进入「超容量状态」，需要学会选择性删除。

DeltaNet（Fast Weight Programmers）引入了 delta rule：每次写入前，先用当前 key 读出旧值，计算差值，只写入差异部分：

```python
v_old = k_i @ S                      # 读出旧值
u_i = b_i * (v_i - v_old)            # 计算差异
S = S + k_i.T @ u_i                  # 写入差异
```

`b_i` 是一个可学习的标量（通过 sigmoid 得到 0-1 之间的值），控制每次写入的强度。如果 `b_i` 接近 0，这次输入几乎不会改变状态；如果接近 1，则会尽力把旧关联替换为新值。

但这个公式有个问题：每一步都依赖前一步的状态。原文作者花了七个小时才建立对这部分的可用理解——**delta rule 无法像纯累加版本那样简单地并行化**，因为必须先算 v_old 才能算差异。

解决方案是用广义 Householder 矩阵把 delta 更新重写为一阶线性递推：

```
S_t = S_{t-1}(I − β_t·k_t·k_tᵀ) + β_t·v_t·k_tᵀ
o_t = S_t·q_t
```

这个形式允许分块并行——把序列切成大小为 C 的 chunk，块内做精确的 masked attention（标准 O(N²) 那套），块间用递推状态高效衔接。C=N 时退化为标准注意力，C=1 时退化为普通线性注意力。实践中 C 通常取 64 或 128——刚好匹配 tensor core 的高效粒度。

## Gated DeltaNet：防止状态无限膨胀

DeltaNet 解决了「精确改写」的问题，但没有解决「自然遗忘」。随着时间推移，状态矩阵持续累加信息，即使旧数据不再有用。

Mamba-2 的贡献就是给缓存加了一个衰减门：

```python
cache = alpha * S_old + S_new
```

每一步先把旧状态按比例衰减，再加入新状态。但问题是所有 key-value 关联被同等衰减，不管它们有多重要。更好的方案是对每个关联赋予不同的衰减速率——这就引入了 per-channel 的门控：

```
γʳ/γⁱ 项负责累积衰减。一个在时刻 x 写入、x+t 时读取的 token，其贡献已被 αₓ·αₓ₊₁·…·αₓ₊ₜ 连乘过。
这是前缀和计算的乘法对应物。
```

## Kimi Linear：混合架构的起点

到这里，研究者开始把多种注意力形式混在一个模型里。Kimi Linear 的核心声明是：**在受控对比下，它超过了 full attention**，同时 decode 速度快 6 倍。

它的 KDA（Kimi Delta Attention）更新规则和前面类似，但加入了细粒度的 per-channel 记忆衰减控制——这是论文最重要的贡献。和标准 DeltaNet Transformer 对比，Kimi Linear 引入了三个重大变化：

- **混合系统**：交替插入 Multi-head Latent Attention（MLA）层
- **MoE 替换 MLP**：用 Mixture-of-Experts 替代全连接层
- **DeltaNet 扩容**：通过增加 per-channel scale 参数提升表达能力

这三个变化不是拍脑袋扩参数。增加的容量有明确的数学目的：per-channel scale 让模型对记忆衰减有更精细的控制。放大量在正确的位置、用正确的方式，才有意义。

## KimiK3：23 个 macrocycle 的工程堆叠

KimiK3 的语言主干包含 **23 个四层 macrocycle**。每个 macrocycle 里，三层用 Kimi Delta Attention，第四层用 Multi-head Latent Attention。第一层用 dense FFN，其余所有层用 latent MoE。

具体的新组件：

### Gated MLA

MLA 从输入投影出一个门控信号，通过逐元素乘法决定多少检索到的特征可以进入 residual stream——相当于让模型学会「屏蔽掉」不相关的注意力输出。

### Latent-Space MoE

传统 MoE 用点积相似度把每个 token 路由到一部分专家网络。KimiK3 的 MoE 在压缩的 latent space 中操作，前向传播更快、FLOPs 近乎减半。代价是新激活函数在没有融合 kernel 时比原路径慢将近 3 倍——这是一个持续存在的推理优化挑战。

### SiTU 激活

```python
d = x.shape[-1] // 2
gate = x[..., :d]
up = x[..., d:]
situ_a = beta * tanh(gate / beta) * sigmoid(gate)
return situ_a * up
```

SiTU 把输入劈成两半，一半做门控（tanh + sigmoid），另一半做上投影。`beta` 是可学习参数，控制门控的非线性程度。

### AttnRes：跨层选择性注意力

正常 transformer 里，每层的输入是原始 embedding 加上前面所有层输出的等权和。AttnRes 让每一层**选择性**地关注前面各层的输出——每个块的 query 可以学出自己最需要的表示来自哪一层：

```
h_l = h_1 + Σ f_i(h_i)   →   每层输入 = 嵌入 + 所有前驱层的等权和
```

AttnRes 把层输出的堆叠当成 key-value，让当前层的 query 去检索最相关的历史层表示。KimiK3 在 1-2 层的粒度上应用了这个思想——块级残差注意。

## 贯穿始终的主线

从 GPT-2 到 KimiK3，核心变化不是「扩大参数」。每一步架构变更都改变了以下三件事之一：

1. **存什么**：从 KV cache 到线性状态矩阵到可衰减的状态
2. **怎么更新**：从覆盖到叠加到 delta 差异到门控衰减
3. **怎么检索**：从 Q·Kᵀ 到 chunked 混合到 MLA 跨层选择

22580 倍的增长量确实惊人。但更大的故事是：七年里，我们对「模型应该如何维护和访问内部记忆」这个问题的理解，已经和 GPT-2 时代完全不同了。规模让这一切变得可见，但机制才是让规模变得有意义的东西。

## 参考

- [22580: From GPT2 to Kimi3, Explained](https://x.com/waterloo_intern/status/2081762065392541951) — ali (@waterloo_intern) 原文
- [GPT-2 Paper (Radford et al., 2019)](https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf)
- [Linear Transformers (Katharopoulos et al., 2020)](https://arxiv.org/abs/2006.16236)
- [Fast Weight Programmers / DeltaNet (Schlag et al., 2021)](https://arxiv.org/abs/2102.11174)
- [Mamba-2 (Dao & Gu, 2024)](https://arxiv.org/abs/2405.21060)
- [KimiK3 Technical Report](https://github.com/MoonshotAI/KimiK3)
