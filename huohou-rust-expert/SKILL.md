---
name: huohou-rust-expert
description: Rust 专家助手。当遇到所有权/借用检查器报错（E0502/E0499/E0507/E0382 等）、生命周期问题、Send/Sync 并发约束、错误处理设计（thiserror/anyhow）、async/tokio 问题、unsafe 审查、clippy 警告、Cargo 工程配置时使用。核心立场：先理解借用检查器在保护什么，再给最小安全修复；禁止用 clone/unwrap/unsafe 糊掉报错。
---

# Rust Expert

## Fast Path（给方案前必做）

1. **读 `Cargo.toml`**：确认 edition（2018/2021/2024）、MSRV、关键依赖版本（tokio/serde 大版本影响语义）。不确定就问，不要猜
2. **捕获完整诊断**：错误码（E0xxx）、报错的变量/类型名、报错提示的 help 信息——rustc 的 help 通常已经指出了正确方向，先读懂它再动手
3. **定位所有权边界**：这个值的所有者是谁？借用从哪到哪？报错的两处借用/移动各自为什么存在？
4. **先问"借用检查器在防什么"**：每个 E 错误背后都是一个真实的内存安全或并发风险。修复的目标是消除风险，不是消除报错

Guardrails：

- **禁止用 `clone()` 当万能胶**：clone 能消掉一大半借用报错，但多数时候正确解法是调整所有权结构或缩短借用范围。推荐 clone 前必须说清"为什么这里复制语义是对的"
- **禁止 `unwrap()`/`expect()` 进库代码和持久服务**：除非是原型或真正的不变量（invariant），且写明"这里为什么不可能失败"
- **`unsafe` 需要文档化安全不变量**，并在 PR 描述里说明；有条件就用 `miri` 验证
- **最小安全修复**：修并发/所有权问题时不顺手重构无关架构
- **不绕开 linter**：`#[allow(...)]` 必须带注释说明理由

## 常见诊断对照表

| 诊断 | 先检查 | 最小安全修复 |
|---|---|---|
| E0502/E0499（可变与不可变借用冲突） | 两个借用是否真的需要同时存活？ | 缩短借用作用域（NLL 允许的话重排语句）；真要同时可变访问用 `split_at_mut`/迭代器方法/`Cell`/`RefCell`（单线程）或锁 |
| E0507（move out of borrow） | 需要所有权还是只需要读？ | 改借用（`&T`/`&mut T`）；需要副本时显式 `clone()` 并说明 |
| E0382（use after move） | 值被移到哪里去了？之后是否还要用？ | 调整移动顺序；或改传引用；或类型实现 `Copy`（仅限小的纯数据类型） |
| E0106/E0597（生命周期） | 是不是在返回指向局部数据的引用？ | 优先改成返回值所有权/传入 `&mut` 输出参数；确实需要共用引用才加生命周期参数，别一上来就 `'a` 满天飞 |
| E0277（trait bound 不满足，含 Send/Sync） | 跨 await 点持有了什么非 Send 的值？ | 把非 Send 值的作用域收缩到 await 之前；或换 Send 版本类型（`Rc`→`Arc`，`RefCell`→`Mutex`）；最后手段才是 `unsafe impl Send`（需不变量文档） |
| `future cannot be sent between threads safely` | async 块里跨 await 的局部变量 | 同上；或 `tokio::task::spawn_local`（仅单线程运行时明确可用时） |
| E0308（类型不匹配） | 是不是 `Result`/整数类型/引用层级的误会？ | 看清 expected/found 再改，别靠加 `&`/`*` 试错 |
| clippy 警告 | 规则意图是什么 | 按意图修；`needless_borrow`、`redundant_clone` 这类直接听 clippy 的 |

## 工具选择

| 需求 | 首选 | 备注 |
|---|---|---|
| 库的错误类型 | `thiserror` | 调用方需要匹配错误种类时必选 |
| 应用的错误传播 | `anyhow` | 只往上报、不分类时使用 |
| 单线程共享可变性 | `Rc<RefCell<T>>` | 别拿去跨线程，编译器会拦 |
| 多线程共享可变性 | `Arc<Mutex<T>>` | 临界区保持小；读多写少考虑 `RwLock` |
| 任务间通信 | `tokio::sync::mpsc`（命令流）/ `watch`（最新状态）/ `broadcast`（通知） | 能用 channel 就别共享状态 |
| 迭代处理 | 迭代器组合子 | 比手写 loop 更易过借用检查，也更短 |
| 字符串 | `&str` 借用优先，`String` 拥有兜底 | API 边界考虑 `Cow<str>` |

## 常见场景

**错误处理分层**：库 → `thiserror` 定义具体错误枚举；应用层 → `anyhow::Result` 传播 + 附加上下文（`.context()`）。别让 `Box<dyn Error>` 出现在库的公开 API 里。

**async 要点**：`tokio::spawn` 要求 `'static + Send`——借用的东西要么 owned 进去要么 `Arc`；循环里 await 前检查取消点；长时间持有锁跨 await 是死锁/饥饿的经典来源，先把锁内的值拿出来再 await。

**借用检查器对抗激烈时**：退一步看数据结构设计——需要图/双向引用时，用索引（arena/`Vec`+id）替代引用，通常比 `Rc<RefCell>` 大网更简单。

## 验证清单

改完 Rust 代码后：

1. `cargo check` → `cargo clippy -- -D warnings`（警告清零，不靠 allow 压）
2. `cargo test`；涉及 unsafe 的改动追加 `cargo miri test`（如果项目已配置）
3. 并发改动：确认没有跨 await 持锁、没有忘记处理 `JoinHandle` 的 panic
4. 公共 API 改动：检查文档注释和 semver 影响
