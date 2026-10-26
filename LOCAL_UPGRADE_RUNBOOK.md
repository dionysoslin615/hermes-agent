# LOCAL_UPGRADE_RUNBOOK.md — Hermes生产升级唯一执行手册

## 1. 权限与唯一真源

本文件只规定可复用的升级流程，不构成安装、升级、源码修改、重启、发布、迁移或删除授权。

优先级：

1. 当前用户明确指令；
2. 最新Hermes官方文档、目标版本CLI与源码；
3. 当前真实进程、服务、配置、数据库和消费者；
4. `LOCAL_PATCHES.md`中的现行本地源码差异；
5. 本Runbook；
6. 历史Session、日志和Receipt，仅作证据。

长期升级治理文件只允许两份：

- `LOCAL_PATCHES.md`：当前Hermes源码差异、回归、必要性和退出条件；
- `LOCAL_UPGRADE_RUNBOOK.md`：本文件，只保存可复用程序。

目标SHA、版本、PID、Profile/Cron/Kanban数量、测试数字、安装generation和故障叙述必须放入当次Cycle Receipt，不得写成本文件中的固定事实。

## 2. 不变量

- 只部署用户授权的官方稳定目标；未发布`main`不能代替稳定版本。
- 升级任务由当前协调者亲自执行，不委派语义判断或生产切换。
- 生产最终只有一个Hermes源码根、一个当前PM环境和一个正式Launcher。
- 所有Profile保持独立Home、凭据、模型、工具、Skill、Session、Cron和平台边界。
- 不因升级修改Profile模型、Provider、推理参数或业务调度语义。
- 官方Skill默认字节不变；只有用户点名授权后，才按当前Hermes官方源码同步。
- 候选构建、测试和浏览器验证不得写生产业务数据库或触发发布、购买、付费调用。
- 禁止隐式下载Playwright、Google Meet runtime、`agent-browser`、PM Chromium和本地Whisper。
- CUDA消费者必须维持获准的统一运行时；按包所有权和真实映射判断，不能按`.so`文件名猜测。
- 升级一旦正式验收，不再回退到旧Hermes版本；后续问题前向修复或进入下一次获准升级。

## 3. 运行时所有权

### 3.1 Python

- Hermes通用Python由PM的per-install `facts.json`选择。
- 外部消费者只能通过稳定解析入口读取当前facts；禁止固定install key、generation、venv目录或旧源码根。
- 依赖只通过Hermes正式manifest、lock、插件/overlay声明进入PM环境；不得对当前generation手工`pip install/uninstall`。
- 每次升级执行`hermes pm doctor`、依赖一致性检查、当前runtime verifier及真实消费者smoke。
- 项目自有`.venv`只允许作为明确登记的网站/项目例外；其服务、依赖和清理与Hermes PM分开。不得把项目venv改成Hermes默认环境，也不得因Hermes升级删除。

### 3.2 Node

- 通用Node在新进程启动时从当前PM facts/PATH解析。
- Cron、Kanban、MCP、Runner和systemd不得固定PM Node版本目录。
- Gateway安装器若在base unit生成版本化Node/npm路径，必须改为facts驱动的稳定selector；同时检查base fragment、全部drop-in、`systemctl show`的有效环境和主进程`/proc/<pid>/environ`。被drop-in覆盖的版本化文本仍算待修复残留，不能只因当前有效PATH正确而忽略。
- PM切换后，已运行进程不会自动换解释器；必须在授权范围内逐个冷启动并从`/proc`回读。

### 3.3 Browser

- Browser Use/Harness只使用受管稳定Chrome selector；任务不得固定浏览器版本目录。
- Browser runtime manifest是引擎路径、版本和SHA-256的唯一集中锁；Verifier必须读取manifest，不能再次写死Chrome、Lightpanda或Harness版本。manifest/facts/Receipt中的受管版本事实与消费者版本pin必须分开判定。
- 每个Worker必须拥有独立进程、OS随机端口、user-data-dir、cache、Harness namespace和清理权。
- 浏览器自动化UA从实际会话/运行时取得；纯HTTP采集器使用集中站点策略，不得在多个脚本散落版本号。
- 验收包括真实导航、DOM操作、下载禁用、退出后端口/进程/Profile/cache零残留。

## 4. 升级前只读基线

每轮先查阅最新官方Updating、Package Management、Profiles、Configuration、Cron、Kanban、Browser、Skills和相关迁移文档，并读取当前命令`--help`。

记录：

- 当前分支、HEAD、上游基线、远程、worktree、stash、tag和工作树；
- 最新稳定release与未发布远程tip，分开记录；
- PM facts、解释器、工具、依赖overlay和declined能力；
- 每个Profile的配置语义、凭据键集合、Gateway、Cron、Kanban、Session和Skill边界；
- systemd、容器、MCP、Browser、WeKnora、OSS、网站和外部Runner消费者；
- 当前业务暂停、锁、Journal、Manifest和不可重放副作用；
- 所有旧源码根、旧generation、固定运行时和版本化Browser引用；
- 家目录及每个Profile递归清理候选，明确排除受保护知识库。

只读调查不得用`pull`、merge、rebase、checkout、安装、重启或删除代替。

## 5. 本地源码差异生命周期

逐项对`LOCAL_PATCHES.md`执行：

1. 在精确目标版本定位owner symbol、调用者、官方测试和替代配置/扩展边界；
2. 机器核对真实diff与Ledger，双向不得缺项；
3. 查当前消费者：开放任务、启用调度器、任务模板、生产Launcher和未来生产者；历史完成/归档记录不算消费者；
4. 分类为`UPSTREAM-ABSORBED`、`EXTERNALIZED`、`NO-CONSUMER`、`ACTIVE-LOCAL-SOURCE`或`FROZEN-TARGET-COMPATIBILITY`；
5. 已吸收、已外置或无消费者的差异和专属测试立即退出；
6. 保留项必须证明：目标版本缺失、无支持的外围替代、存在当前消费者、移除时稳定边界回归失败、实现已最小；
7. 新语义、第九项补丁、无关重构或扩大源码范围必须另行授权。

外围Runner、systemd、runtime selector、Profile Skill、`.env`、依赖清单和验收器不是Hermes官方源码，但仍必须按各自权限和消费者验证。

## 6. 候选与测试

- 候选必须在有界隔离目录从精确目标构建；不得复制旧venv、`node_modules`、浏览器Profile或整个旧源码文件。
- 先用小型harness证明HOME、PATH、Node、Git/gh、Browser、临时目录、socket、子进程和teardown前提正确。
- 每次只运行一个正式全套件；必须保存完整原始日志、环境清单、精确失败node ID和SHA-256。
- 若正式套件使用了错误环境：原始失败保持历史事实，但不得描述为当前产品错误；修正的只能是harness，并仅重跑精确失败node或最小所属模块，禁止为了覆盖记录再次运行整套件。
- 在未修改目标源码的对照树复现，只能排除本地差异，不能自动归因为上游缺陷。
- 所有定向测试必须使用正确PM解释器、隔离HOME和正式工作目录；运行后清除测试进程、端口、临时unit和Profile。

## 7. 配置、Profile和任务面

逐个发现并验证全部正式Profile，不使用固定数量：

- `config check`、工具注册、MCP初始化和必要的无副作用调用；
- Profile Home、模型/Provider/fallback、Skill、凭据键和Session不串用；
- `.env`只存凭据，不保存PATH、Node、浏览器、Modal镜像等运行时选择；
- Cron逐项检查owner、enabled/paused、schedule、delivery、Runner、cwd和运行时解析；
- Kanban逐库执行SQLite检查，核对开放任务、父子依赖、assignee、workspace和运行时字段；
- Cron验收必须分开报告当前定义/Runner错误与`last_error`、`last_failure`等历史证据；历史失败不能冒充当前结构错误，也不能在未真实成功执行时改写为成功。
- Kanban必须动态枚举正式board和游离`kanban.db`，扫描任务、评论、事件、run和附件索引的全部状态；开放任务中的临时路径是执行风险，终态任务中的历史文本只作证据。
- Crawler任务只能指定`crawler`执行，不在Runner/Cron/Kanban中钉模型、Provider或思考强度；
- 不强制触发低频、发布、付费或当前暂停任务来完成升级验收。

### 7.1 官方Skill跨Profile同步与锁定

Profile彼此隔离；升级默认Home或源码，不等于命名Profile中的Bundled Skill已同步。每次升级必须：

1. 用`hermes profile list`发现全部现行Profile，不写死数量；以已选定官方提交中的`skills/`和`optional-skills/`为唯一官方基线。
2. 升级前记录两棵官方源码Skill树、各Profile `.bundled_manifest`和全部已安装Bundled Skill树的SHA-256与权限模式；只临时解锁本次需要更新的官方路径，不解锁自定义或Agent创建Skill。
3. 升级后逐Profile按名称、规范相对路径和完整树哈希与本机官方源码比较。`hermes skills list-modified`只会与该Profile自己的manifest比较，不能证明manifest不是旧版。
4. 对每个未被用户修改但已落后的Bundled Skill，使用官方恢复命令：

   ```bash
   hermes --profile <profile> skills reset <skill> --restore --yes
   ```

   `hermes skills opt-in --sync`只补种缺失项，不能作为既有副本已更新的证明。
5. 只有每个Profile都满足“Bundled全集完整、规范路径正确、树哈希零差异、manifest完全一致、`skills list-modified --json`返回`[]`”才通过。
6. 验证后重新锁定：已安装Bundled Skill及官方源码`skills/`、`optional-skills/`的目录`0555`，普通文件`0444`，原本可执行的脚本`0555`，各Profile `.bundled_manifest`为`0444`；不得因锁定清除脚本的执行位。这是同所有者权限锁，不是immutable保证；以后每次升级都必须显式解锁、同步、校验、再锁定。
7. 锁定后逐Profile运行`config check`和`tools list`。
8. Agent创建Skill与官方Skill分开治理。删除前必须扫描所有Hermes Cron定义及其现行Runner/Prompt，并扫描全部现行看板、全部状态的Kanban任务；仅零引用项可删。删除时同步清理`.usage.json`并失效`.skills_prompt_snapshot.json`，但保留Curator ledger及其仍引用的备份blob作为审计历史。

## 8. WeKnora与外部服务边界

- WeKnora upstream、数据库、Monitor和测试代码遵守其独立授权；Hermes升级不得顺带修改。
- Full与Incremental保持现行授权状态；暂停期间不得以验收为名启动、补跑或触发付费调用。
- Monitor只读，不成为第二写入者。
- 正式WeKnora写入只允许服务自有`data`、受管GPU lock、私有临时目录和声明的Docker卷。
- Full/Incremental systemd必须`ProtectSystem=strict`、`ProtectHome=read-only`、`PrivateTmp=true`，并通过`ReadWritePaths`只放行正式写目录；Controller内部文件沙箱作为第二层。
- 显式设置受管`HOME`、`XDG_CACHE_HOME`和`TMPDIR`，禁止向家目录根部生成`data`、`.duckdb`、缓存或导出。
- 任何外部服务冷启动都必须在单独授权范围内，并回读新PID、加载路径、协议健康和禁止服务仍停用。

## 9. 切换与Gateway

- 切换前冻结新任务准入，记录真实在途工作；未经授权不得终止或重放有外部副作用的业务。
- 默认Gateway重启会终止当前会话，因此必须先建立独立外部one-shot continuation，绑定Cycle状态和回复目标。
- 外部控制器使用`Type=exec`、`Restart=no`；禁止失败后由process manager无脑重入。
- 原子发布正式源码和PM selector后，按真实Gateway拓扑逐个启动；记录旧/新PID、启动时间、cwd、exe、maps和FD。
- 先验证Gateway核心路由，再恢复Cron/Kanban准入；单纯`active (running)`不算验收。

## 10. Git唯一化

最终代码和文档验证后：

- 只保留一个正式本地分支、一个worktree和唯一最终提交；
- 删除本地旧分支、stash、无继续用途的本地tag、reflog和不可达对象；
- 自有Fork只保留正式分支和最终状态，删除旧Fork分支与历史tag；
- 使用`--force-with-lease`等带租约方式发布，随后从远程回读分支和tag；
- 使用`git ls-remote`回读自有Fork的全部branch/tag和官方annotated tag的对象及解引用提交；本地tag只允许保留能在官方origin找到的集合，禁止把官方tag误判为自有Fork残余。
- 官方`origin`保持只读，不删除其分支、tag或祖先历史；
- 不为了“同步”把稳定生产推进到未发布的官方main。

## 11. 递归清理

清理依据只有消费者与恢复责任，不按名称、年龄或“可能以后有用”保留。

每轮递归覆盖家目录、默认Home、全部Profile、Maintenance、Scratch、cache、logs、backups、workspace、artifacts、state snapshot、PM generations、systemd、Docker和Git对象；受保护知识库按用户边界完全排除。

删除：

- 已被最终Receipt取代的中间快照、临时矩阵、候选、旧rollback副本和原始日志；
- 无消费者的备份、测试缓存、下载、空数据库、临时文件、失效脚本和旧runtime；
- credential-bearing `.env`备份在现行配置回读后安全删除，不保留副本；
- 无进程、服务、任务、Session、Runner、恢复合同或冷启动依赖的可再生缓存。
- UV interpreter缓存中指向已删除install/generation的记录、断链editable缓存、浏览器Singleton与旧Profile缓存、死亡Worker outbox、一次性控制器`__pycache__`、无owner的Node编译缓存、零字节包管理锁、已完成delegation/exec/spillover/terminal-output缓存，以及不存在unit对应的孤儿drop-in。

保留：

- 当前业务数据库、知识库、Journal、Manifest、正式状态、在途恢复证据；
- 当前被Runner读取的workspace、ledger和control state；
- 明确登记的项目venv与生产依赖；
- 最终唯一紧凑Receipt。

删除前检查进程`cmdline/cwd/exe/maps/fd`、systemd、Cron、Kanban、Session、配置、Runner和软链；删除后重复同一组检查。不得使用广泛Docker prune或通配符删除替代精确allowlist。

UV清理不能只扫描editable `finder.py`：还必须解析interpreter cache记录、检查editable symlink目标、当前venv内`.pth`/finder及全部install/generation实体；只有失效缓存、旧引用和断链同时为零才可声明“零PM缓存残留”。所有独立审计者退出后，再清理其一次性日志和缓存并复扫；审计仍在运行时不能闭账。

## 12. 完成门槛

只有以下全部同时成立，才能把Cycle写成`UPDATED`：

- 正式HEAD、父基线、版本和唯一生产入口一致，工作树干净；
- `LOCAL_PATCHES.md`与真实diff完全一致，所有保留项有当前消费者；
- Runbook与官方现行行为一致，旧升级指南和引用不存在；
- 全部Profile、Cron、Kanban、Session、MCP和外部消费者通过各自真实入口检查；
- Python、Node和Browser分别证明动态选择及新进程激活边界；
- WeKnora和其他受保护业务保持规定状态，未发生未授权调用；
- 本地Git与自有Fork收敛为唯一正式状态，官方origin未被改写；
- Maintenance和全系统清理完成，二次扫描无无主残留；
- 原始base unit、drop-in、有效systemd环境和进程环境四层均无消费者版本pin；Browser集中manifest与消费者引用分类正确；
- Cron历史失败与当前定义分层记录，Kanban开放任务数及全部board/游离数据库扫描结果写入Receipt；
- 历史测试结果、当前定向结果和未验证项表述准确；
- `state.json`、`result.json`和唯一最终Receipt相互一致并已回读。

计划完成、测试命令退出零、服务存活或发送一条通知，均不能单独代表完成。
