# SQCAD Markdown 数学公式 LaTeX 转换规范（v1, 2026-08-17）

目标：仓库内全部 md 文档的数学公式按标准 LaTeX 渲染（GitHub MathJax 兼容）。
**核心纪律：只转换公式语法，绝不改动数字、单位、日期、文件名、结论语句、实验数值、链接、文档结构。**

## 1. 语法形式

| 场景 | 形式 | 示例 |
|---|---|---|
| 行内（句中单符号/短表达式） | `$...$` | `资格证书 $\tau(i,s)$ 定义为` |
| 块级（独立公式行） | `$$...$$` **独占一行**，上下留空行 | `$$\tau(i,s) = V_s^\pi(\operatorname{keep}_i) - V_s^\pi(\operatorname{archive}_i)$$` |
| 表格单元格内 | 只用行内 `$...$`（禁止 `$$`，会破表） | `| $\tau$ | $[L,U]$ |` |

## 2. 本项目符号映射表

| 文本形式（原文） | LaTeX 目标 |
|---|---|
| `τ(i,s) = V_s^π(keep_i) − V_s^π(archive_i)` | `$\tau(i,s) = V_s^\pi(\operatorname{keep}_i) - V_s^\pi(\operatorname{archive}_i)$` |
| `R*(L,U)` | `$R^*(L,U)$` |
| `R*(L,U) = U(−L)/(U−L)` | `$$R^*(L,U) = \frac{U(-L)}{U-L}$$` |
| `min{ R*(L,U), C_defer, C_probe + R*_after }` | `$\min\{R^*(L,U),\ C_{\text{defer}},\ C_{\text{probe}} + R^*_{\text{after}}\}$` |
| `z(i,s,t) = r(i,t) + α·positive(i,s) − β·negative(i,s) − γ·scope_mismatch(i,s) − η·cost(i)` | `$z(i,s,t) = r(i,t) + \alpha\,\mathrm{positive}(i,s) - \beta\,\mathrm{negative}(i,s) - \gamma\,\mathrm{scope\_mismatch}(i,s) - \eta\,\mathrm{cost}(i)$` |
| `a = B · Project(z/T)` | `$a = B \cdot \operatorname{Project}(z/T)$` |
| `Σᵢ aᵢ = B` | `$\sum_i a_i = B$` |
| `Q(i,s) ∈ {point, bound, unresolved, mismatch}` | `$Q(i,s) \in \{\text{point},\ \text{bound},\ \text{unresolved},\ \text{mismatch}\}$` |
| `Θ(T)` | `$\Theta(T)$` |
| `O(1/qρ)` | `$O(1/(q\rho))$` |
| `E[·]` 期望 | `$\mathbb{E}[\cdot]$` |
| `P(·)` / `Pr(·)` 概率 | `$\Pr(\cdot)$`（或 `$P(\cdot)$`） |
| `a/b` 分数 | `$\frac{a}{b}$` |
| `Σ` 求和 | `$\sum$`（带上下限 `$\sum_{t=1}^{H}$`） |
| `√` | `$\sqrt{x}$` |
| `∞` | `$\infty$` |
| 全角 `−`（U+2212）与 `-` | `$-$`（数学模式内用 ASCII 减号） |
| `×` | `$\times$`；`·` | `$\cdot$` |
| `≥ ≤ ≠ ≈ ∈ ∉ ⊂ ⊆ → ↔ ±` | `$\ge$ $\le$ $\ne$ $\approx$ $\in$ $\notin$ $\subset$ $\subseteq$ $\to$ $\leftrightarrow$ $\pm$` |
| 希腊字母 `α β γ δ ε θ λ μ π ρ σ τ φ χ ψ ω Φ Ψ Δ Σ Ω` | `$\alpha$ $\beta$ $\gamma$ $\delta$ $\varepsilon$ $\theta$ $\lambda$ $\mu$ $\pi$ $\rho$ $\sigma$ $\tau$ $\phi$ $\chi$ $\psi$ $\omega$ $\Phi$ $\Psi$ $\Delta$ $\Sigma$ $\Omega$` |
| 上标 `^` / 下标 `_`（如 `V_s^π`、`a_i`、`T-n_early`） | `$V_s^\pi$`、`$a_i$`、`$T-n_{\mathrm{early}}$` |
| `min` `max` `log` `exp` 等函数名 | `$\min$` `$\max$` `$\log$` `$\exp$`（垂直函数名用 `\operatorname{KL}`、`\mathrm{cost}`） |

## 3. 判定规则

1. **凡数学量记号出现即用 `$...$` 包裹**（行内）。包括正文中"资格证书 $\tau(i,s)$"这类指代性提及。
2. **例外**：记号位于代码块（```` ``` ```` 内）且属于真实代码/命令（如 Python 变量 `alpha`、CLI 参数）时不动；位于文件名、路径中不动（如 `Gate-A` 不是公式）。
3. **已有 `$...$` 的内容**：检查闭合与命令合法性，修正明显错误（缺 `$` 闭合、`\operatorname` 缺反斜杠、`\frac` 参数错误），正确部分一律不动。
4. **代码块中的公式**：若代码块（```text / ```plain）内容本身就是公式（非代码），移出代码块转为 `$$...$$` 块级。
5. **表格**：单元格内公式用行内 `$...$`；独立公式行放表格外块级。
6. **文本形式数字序列**（如 `0.0344 → 0.0455`）不是公式，保留原文（`→` 在数字序列中可保留或转 `$\to$`，取上下文判断：若表达数值变化可保留 Unicode 箭头，不强行包裹）。
7. 已有正确的 Unicode 数学符号在 **非公式语境**（如列表符号、口语化表达"α 和 β 两个版本"）→ 包裹为 `$\alpha$`、`$\beta$`（学术化要求）。
8. **空行与间距**：公式两侧的空格/换行保持原有结构；块级公式前后各留一个空行。

## 4. 禁止事项

- 不改数字、符号数值、日期、百分比、置信区间数字。
- 不改结论、判定、实验描述措辞（除公式语法外）。
- 不改标题、列表层级、链接目标、图片引用。
- 不新增/删除段落，不重组表格。
- 不把已有正确 LaTeX 改写成其他形式。
- 中文与 `$` 之间不加多余空格（保持原文空格）。

## 5. 自查清单（完成每份文件后）

- [ ] `$` 数量为偶数（配对闭合）；块级 `$$` 独占一行
- [ ] 表格单元格内无 `$$`
- [ ] 无残留文本公式（`α·positive`、`R*(`、`Σᵢ` 这类未包裹记号）
- [ ] 数字与结论与原文逐字一致
