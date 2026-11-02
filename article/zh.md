# 深入《植物大战僵尸 2》：从 RSB 资源解包到 RTON 解码与 Rijndael 加密分析

*Ray Tian — University of Waterloo, Honours Mathematics (Co-op)*

*本文讲解《植物大战僵尸 2》资源文件的三个层次(RSB、RTON、Rijndael),从零实现一个小型 RTON 解码器,并在一个真实版本上检验它的容器层。*

## 1. 引言

我初二到初三的时候开始研究《植物大战僵尸 2》中文版的数据文件。当时出了一个新模式"潘妮的追击",我想弄明白游戏是怎样存放关卡数据的,比如一关的出怪这类信息怎么用数据来描述。这份好奇心把我带进了二进制文件格式的世界。

一个 PVZ2 资源文件要经过三层相互独立的处理:

```
RSB 资源包 ──解包──▶ 加密的 RTON ··[解密:本文不涉及]··▶ 二进制 RTON ──解码──▶ 类 JSON 数据
```

解密所需的密钥和解密步骤,本文有意不涉及。

这些格式是由 PVZ2 的修改(mod)社区逐步摸清的,出处见[参考资料](#9-参考资料)。我自己的部分是讲解、一个为学习 RTON 而写的小解码器,以及在真实版本的容器层上验证过的记录。代码在 [GitHub](https://github.com/Jelly-RayTian/pvz2-format-exploration)。

这次分析在本机完成,仅为学习。不公开任何游戏文件、账号或会话令牌,解码器的测试数据全部是合成的,代码见附录。

## 2. 理解 RSB

### 2.1 "资源包"是什么

游戏有成千上万个小资源。在手机上逐个读文件很慢,所以引擎把它们打包成少数大文件。RSB 就是这样的容器。
社区的解包工具先读容器的*索引*,再把每个条目写成独立文件。

### 2.2 RSB 不是 ZIP

两者都是"一个文件装很多文件",但结构不同:

- ZIP 有中央目录,并对每个文件单独压缩。
- 按社区工具 Pvz2Tool 的实现,RSB 有一个由偏移量组成的**定长头部**、一份**文件列表**,以及一张**资源组(RSGP)表**。
  压缩作用于*资源组的某个部分*,而不是逐个文件。

[来源:Pvz2Tool 的 `RsbHeadInfo.kt`、`RsgpHeadInfo.kt`]

### 2.3 头部

所有字段都是 32 位小端整数。Pvz2Tool 读取的 RSB 头部前几项依次是:

| # | 字段 | 含义 |
|---|---|---|
| 0 | magic | `0x72736231`,字节 `31 62 73 72` = ASCII `1bsr` |
| 1 | version | 整数(该工具最高接受 4) |
| 2 | (零) | 必须为 0 |
| 3 | headLength | 头部大小 |
| 4 | fileList_Length | 文件名列表大小 |
| 5 | fileList_BeginOffset | 该列表起始位置 |
| 6–7 | (零) | 必须为 0 |
| 8 | rsgpList_Length | 资源组名列表大小 |
| 9 | rsgpList_BeginOffset | 其起始位置 |
| 10 | rsgp_Number | 资源组数量 |
| 11 | rsgpInfo_BeginOffset | 资源组信息记录起点(每条 `0xCC` 字节) |
| … | composite / autopool / ptx 表 | 更多"数量 + 起始偏移"对 |

要带走的核心思想是 *偏移量 + 长度*:头部不含数据本身,只含**数据在哪**。
解析器需要的一切,都是"跳到某偏移、读已知长度"。

[来源:Pvz2Tool `RsbHeadInfo.kt`。魔数我自己验证过:常量 `1920164401` 按小端转成字节就是 `1bsr`。]

**版本差异是真实存在的。** 同一份源码的注释提到:PTX 信息记录通常是 `0x10` 字节,
而"中文版二代 RSB"是 `0x18`。能解析一个版本的程序可能在另一个版本上失败,
所以我的复现记录必须标明确切版本。

### 2.4 资源组(RSGP)

每条资源组记录指向一个 RSGP 块,它有自己的头部,魔数 `0x72736770`(`70 67 73 72` = ASCII `pgsr`)。
里面有版本、flags、文件偏移,以及两个**部分**,每部分记录 `Offset`、`ZSize`(压缩后大小)和
`Size`(解压后大小),另有自己的文件列表。Pvz2Tool 的 README 说明使用 zlib 压缩与 4K 对齐。

恢复单个文件的流程:

1. 读 RSB 头 → 找到资源组表。
2. 对每个资源组,跳到它的 RSGP 块 → 读各部分的偏移和大小。
3. 若 `ZSize` 与 `Size` 不同,用 zlib 解压。
4. 用该组的文件列表把解压后的区域切成带路径的命名文件。

在本文使用的这个安装包里,RSB 外层还有一层 `.smf` 容器,资源组也没有使用 zlib 压缩,详见第 6 节。

我刻意不声称 `flags` 每一位的含义,因为我没有验证过。

### 2.5 在真实 RSB 上检验布局

上面这些都来自别人的源码。为了看它在真实文件上是否成立,我用一个很短的脚本(附录 D)解析了第 6 节那个 147,292,160 字节的 RSB。结果是:

- 头部写着版本 4、30 个资源组。每条组记录 204(`0xCC`)字节,从偏移 383,936(`0x5DBC0`)开始。`headLength` 是 397,312(`0x61000`)。
- 第一个资源组正好从 `headLength` 开始;每个组都从上一个组结束的地方开始,最后一个组正好在文件末尾结束。所以 `headLength + 各组大小之和 = 397,312 + 146,894,848 = 147,292,160`:头部把整个文件都交代清楚了。解析器可以用它做一个便宜的完整性检查。
- 所有组的偏移和大小都是 4096 的倍数,与 Pvz2Tool README 里说的"4K 对齐"一致。
- 24 个组只用到 `part0`,6 个组只用到 `part1`。我不知道这两个部分在这个版本里各代表什么,所以不做解释。
- 19 个组的第一部分以两个字节 `10 00` 开头:`Packages` 和 18 个 `WorldPackages_*` 组。这就是第 5 节说的加密 RTON 标记。

| 资源组 | 偏移 | 大小 | part0 | part1 |
|---|---:|---:|---:|---:|
| `Credits_1200` | 397,312 | 679,936 | 0 | 675,840 |
| `Credits_Common` | 1,077,248 | 348,160 | 344,064 | 0 |
| `LawnStrings` | 1,425,408 | 3,047,424 | 3,043,328 | 0 |
| `MainMenu_Background_1200` | 4,472,832 | 2,695,168 | 0 | 2,691,072 |
| `MainMenu_Background_Effect_1200` | 7,168,000 | 22,405,120 | 0 | 22,401,024 |
| `MainMenu_Background_Effect_Common` | 29,573,120 | 413,696 | 409,600 | 0 |
| `Packages` | 29,986,816 | 67,760,128 | 67,354,624 | 0 |
| `UI_AlwaysLoaded_Dynamic_1200` | 97,746,944 | 7,471,104 | 0 | 7,467,008 |
| `UI_Card_Plant_BG_1200` | 105,218,048 | 3,743,744 | 0 | 3,739,648 |
| `UI_PVZ1_Temp_1200` | 108,961,792 | 34,975,744 | 0 | 34,971,648 |
| `UI_PVZ1_Temp_Common` | 143,937,536 | 1,945,600 | 1,941,504 | 0 |
| `WorldPackages_beach` | 145,883,136 | 40,960 | 36,864 | 0 |
| `WorldPackages_cowboy` | 145,924,096 | 24,576 | 20,480 | 0 |
| `WorldPackages_dark` | 145,948,672 | 45,056 | 40,960 | 0 |
| `WorldPackages_dino` | 145,993,728 | 49,152 | 45,056 | 0 |
| `WorldPackages_egypt` | 146,042,880 | 20,480 | 16,384 | 0 |
| `WorldPackages_eighties` | 146,063,360 | 40,960 | 36,864 | 0 |
| `WorldPackages_future` | 146,104,320 | 28,672 | 24,576 | 0 |
| `WorldPackages_heian` | 146,132,992 | 28,672 | 24,576 | 0 |
| `WorldPackages_iceage` | 146,161,664 | 36,864 | 32,768 | 0 |
| `WorldPackages_kongfu` | 146,198,528 | 20,480 | 16,384 | 0 |
| `WorldPackages_lostcity` | 146,219,008 | 49,152 | 45,056 | 0 |
| `WorldPackages_mausoleum` | 146,268,160 | 24,576 | 20,480 | 0 |
| `WorldPackages_modern` | 146,292,736 | 36,864 | 32,768 | 0 |
| `WorldPackages_pirate` | 146,329,600 | 28,672 | 24,576 | 0 |
| `WorldPackages_renai` | 146,358,272 | 28,672 | 24,576 | 0 |
| `WorldPackages_skycity` | 146,386,944 | 20,480 | 16,384 | 0 |
| `WorldPackages_steam` | 146,407,424 | 24,576 | 20,480 | 0 |
| `WorldPackages_tutorial` | 146,432,000 | 8,192 | 4,096 | 0 |
| `__MANIFESTGROUP__DYNAMIC` | 146,440,192 | 851,968 | 847,872 | 0 |

## 3. 理解 RTON

RTON 是一种**二进制序列化**格式:对类 JSON 的结构化数据(对象、数组、字符串、数字、布尔值)的紧凑编码。
JSON 把一切写成文本;RTON 把每个值写成*一个字节的类型标记 + 数据*。

### 3.1 布局

```
"RTON"  | 版本 (uint32 小端,通常为 1) | 条目 … | FF | "DONE"
```

### 3.2 类型标记(我实现的子集)

| 标记 | 含义 |
|---|---|
| `00` / `01` | false / true |
| `08` / `0A` | int8 / uint8,1 字节 |
| `10` / `12` | int16 / uint16,2 字节(字节序假定为小端) |
| `20` | int32,4 字节(字节序假定为小端) |
| `21` | int32 零值,无载荷(笔记中标为未确认;暂时支持) |
| `24` | 无符号 varint |
| `25` | 有符号 varint |
| `81` | 字符串:varint 字节长度 + 字节 |
| `90` / `91` | 定义缓存字符串 / 按下标引用缓存 |
| `85` … `FF` | 对象 … 结束 |
| `86 FD` 个数 … `FE` | 数组 |

[来源:h3x4n1um/RETON 格式笔记。笔记本身把其他一些标记(`09`、`0B` 等 zero 变体、RTID `83`)标为不确定,所以我不实现。]

### 3.3 Varint

varint 用尽量少的字节存数字:每字节 7 位有效数据,最高位表示"后面还有字节",低位组在前。

例:`FE 01` → `0x7E + (0x01 << 7)` = 126 + 128 = **254**。

有符号形式把解出的 `n` 映射为:偶数 `n/2`,奇数 `-(n+1)/2`,所以 `25 03` → `n=3` → **−2**。
正负小数都只占很少字节。

### 3.4 字符串缓存

键名如 `"Value"` 第一次出现时用 `90` 写出并存入表;之后只写 `91 下标`。
所以重复键很多的文件很小,也因此解码器必须在读取过程中保持状态。

### 3.5 解析器如何把字节变成 JSON

解析器维护位置 `pos`。循环:读一个字节(标记)→ 标记决定再读几个字节、怎么解释 → 推进 `pos`。
对象和数组是递归:见到 `85` 就调用"读对象",直到 `FF`。结束时 `pos` 必须等于文件长度,
这是一个简单而有效的正确性检查。

### 3.6 逐字节读一个示例 RTON

下面是我用一个小编码器构造的完整 237 字节 RTON。里面的每个值都是编出来的,但结构仿照典型的对象文件:一个版本号,然后是一个由对象组成的数组,对象带有 `uid`、`objclass` 和 `objdata`。每一行都由我写的注释脚本(附录 E)解释。缩进表示嵌套,偏移用十六进制。

```text
0000  52 54 4f 4e                    magic "RTON"
0004  01 00 00 00                    version = 1 (uint32 LE)
0008  90 07 76 65 72 73 69 6f ..+1     key, define cache[0] "version"
0011  24 01                            unsigned varint = 1
0013  90 07 6f 62 6a 65 63 74 ..+1     key, define cache[1] "objects"
001C  86 fd 02                         array start, 2 item(s)
001F  85                                 object start
0020  90 03 75 69 64                       key, define cache[2] "uid"
0025  90 05 31 2e 30 2e 31                 define cache[3] = "1.0.1"
002C  90 08 6f 62 6a 63 6c 61 ..+2         key, define cache[4] "objclass"
0036  90 08 44 65 6d 6f 44 61 ..+2         define cache[5] = "DemoData"
0040  90 07 6f 62 6a 64 61 74 ..+1         key, define cache[6] "objdata"
0049  85                                   object start
004A  90 04 6e 61 6d 65                      key, define cache[7] "name"
0050  90 04 64 65 6d 6f                      define cache[8] = "demo"
0056  90 05 69 74 65 6d 73                   key, define cache[9] "items"
005D  86 fd 00                               array start, 0 item(s)
0060  fe                                     array end
0061  90 04 66 6c 61 67                      key, define cache[10] "flag"
0067  01                                     true
0068  90 05 63 6f 75 6e 74                   key, define cache[11] "count"
006F  24 f4 03                               unsigned varint = 500
0072  90 06 6f 72 69 67 69 6e                key, define cache[12] "origin"
007A  25 95 01                               signed varint = -75
007D  90 04 7a 65 72 6f                      key, define cache[13] "zero"
0083  21                                     int32 zero (no payload) = 0
0084  90 03 62 6f 78                         key, define cache[14] "box"
0089  85                                     object start
008A  90 01 78                                 key, define cache[15] "x"
008D  21                                       int32 zero (no payload) = 0
008E  90 01 79                                 key, define cache[16] "y"
0091  25 95 01                                 signed varint = -75
0094  90 01 77                                 key, define cache[17] "w"
0097  21                                       int32 zero (no payload) = 0
0098  90 01 68                                 key, define cache[18] "h"
009B  24 c8 01                                 unsigned varint = 200
009E  ff                                     object end
009F  ff                                   object end
00A0  ff                                 object end
00A1  85                                 object start
00A2  91 02                                key, recall cache[2] = "uid"
00A4  90 05 31 2e 30 2e 32                 define cache[19] = "1.0.2"
00AB  91 04                                key, recall cache[4] = "objclass"
00AD  91 05                                recall cache[5] = "DemoData"
00AF  91 06                                key, recall cache[6] = "objdata"
00B1  85                                   object start
00B2  91 07                                  key, recall cache[7] = "name"
00B4  90 05 64 65 6d 6f 32                   define cache[20] = "demo2"
00BB  91 09                                  key, recall cache[9] = "items"
00BD  86 fd 02                               array start, 2 item(s)
00C0  24 01                                    unsigned varint = 1
00C2  24 02                                    unsigned varint = 2
00C4  fe                                     array end
00C5  91 0a                                  key, recall cache[10] = "flag"
00C7  00                                     false
00C8  91 0b                                  key, recall cache[11] = "count"
00CA  24 07                                  unsigned varint = 7
00CC  91 0c                                  key, recall cache[12] = "origin"
00CE  21                                     int32 zero (no payload) = 0
00CF  91 0d                                  key, recall cache[13] = "zero"
00D1  21                                     int32 zero (no payload) = 0
00D2  91 0e                                  key, recall cache[14] = "box"
00D4  85                                     object start
00D5  91 0f                                    key, recall cache[15] = "x"
00D7  24 05                                    unsigned varint = 5
00D9  91 10                                    key, recall cache[16] = "y"
00DB  25 01                                    signed varint = -1
00DD  91 11                                    key, recall cache[17] = "w"
00DF  21                                       int32 zero (no payload) = 0
00E0  91 12                                    key, recall cache[18] = "h"
00E2  24 09                                    unsigned varint = 9
00E4  ff                                     object end
00E5  ff                                   object end
00E6  ff                                 object end
00E7  fe                               array end
00E8  ff                             object end
00E9  44 4f 4e 45                    footer "DONE"
```

值得注意的几点:

- 第一个对象用 `90` 定义了 21 个字符串。第二个对象用 `91` 加下标*引用*这些键和重复出现的值 `"DemoData"`,所以短得多。这就是字符串缓存在起作用。
- 空数组就是 `86 FD 00 FE`。
- `zero` 和 `x` 是 `21`:一个字节,没有载荷。
- 负数(例如 `-75`)用 `25` 加一个 varint 存储:`95 01` 是 149,为奇数,所以解码为 -(149 + 1) / 2 = -75。
- 定长整数(`08`、`10`、`20`)出现在我的测试里而不是这个样例里,因为这个样例用的是紧凑的 varint 形式。

## 4. 实现最小 RTON 解码器

**实现方式。** 我在 AI 编程助手(Claude Code)的协助下写了这个解码器,出发点是社区的格式笔记和我早先对这个格式的一些想法,每个函数我都自己过了一遍(见 4.1)。

**设计。** `Reader` 类保存字节和游标 `pos`。每个 `read_*` 方法消耗字节并推进 `pos`;
`read_value` 看标记后分派。对象和数组递归调用 `read_value`,所以嵌套无需特殊处理。
遇到不认识的标记就报错,不去猜。

**先写测试。** `tests/fixtures.py` 里有 12 组手工算出的字节串和期望的 Python 值,逐字节注释。
另有 11 个错误测试:魔数错误、版本错误、缺少尾部、尾部多余字节、字符串被截断、缓存下标错误、
不支持的标记、数组缺少结束符、无限长 varint、嵌套过深、非法 UTF-8。

**结果。** `python -m unittest` 共 14 个测试,全部通过(2026-11-02 运行)。

**范围。** 支持的标记:`00 01 08 0A 10 12 20 21 24 25 81 85 86 90 91`。浮点数、64 位整数、UTF-8 字符串(`82`、`92`、`93`)和 RTID 是接下来要加的。合成测试数据用来对照我对规格的理解;本文不解码真实的游戏文件。

### 4.1 逐函数读解码器

完整代码在附录 A。下面讲每一部分做什么、为什么这样做。

**`Reader`。** 保存 `data`、游标 `pos` 和字符串缓存 `cache`。把 `cache` 放在对象上而不是全局变量里,两次解码就不会互相干扰。

**`read_bytes(n)`。** 唯一接触 `data` 并移动 `pos` 的地方。它先检查 `pos + n` 是否超过长度,所以文件被截断时会抛出 `RtonError("truncated ...")`,而不是悄悄返回更少的字节。其他函数都建立在它之上,所以边界检查只写了一次。

**`read_int(size, signed)`。** 用 `int.from_bytes(..., "little", signed=...)` 转换 `size` 个字节。小端的假设就集中在这一处。

**`read_uvarint()`。** 就是 3.3 节的循环:取低 7 位(`byte & 0x7F`),移到正确位置,最高位为 0(`byte < 0x80`)就停,否则移位加 7。超过 63 位就放弃,这样一个全是 `FF` 的文件不会让它死循环。

**`read_svarint()`。** 先读出无符号 varint `n`,再套用映射:偶数 `n // 2`,奇数 `-(n + 1) // 2`。

**`read_string(tag)`。** 三个标记共用一个函数。`81` 读带长度前缀的字符串;`90` 同样读取,并把结果追加到 `cache`;`91` 读一个下标并返回 `cache[下标]`,下标越界就抛出 `RtonError`。

**`read_value(tag, depth)`。** 一串 `if`,每个支持的标记一个。没列出的标记最后都会 `raise RtonError("unsupported tag ...")`:解码器拒绝猜测。`depth` 一路传下去,嵌套过深的输入会在 64 层停下,而不是耗尽 Python 的栈。

**`read_object` 和 `read_array`。** 它们对每个子元素调用 `read_value`,所以嵌套不需要特殊代码。对象先读键(必须是字符串标记)再读值,直到遇到 `FF`;数组要求 `FD`,读一个个数,读那么多个值,再要求 `FE`。

**`decode(data)`。** 检查魔数和版本,读顶层对象,然后要求出现 `DONE`,并且 `pos` 等于文件长度。最后这一条能抓住末尾多余字节的文件。

最重要的设计选择:每个函数要么返回正确的值,要么抛出错误。没有"尽力而为"的路径,所以错误的标记会表现为带偏移的报错,而不是悄悄变成错误的数据。

## 5. 理解 Rijndael 加密

### 5.1 Rijndael 与 AES

Rijndael 是 Joan Daemen 与 Vincent Rijmen 设计的分组密码家族。AES 是其标准化子集:
分组固定 128 位,密钥 128/192/256 位。Rijndael 本身允许分组为 128、192、256 位,且与密钥长度相互独立。
所以当分组不是 128 位时,"AES"和"Rijndael"不能互换。

### 5.2 这个游戏里的 Rijndael:公开已知的部分

社区研究记录了这个游戏加密 RTON 文件的两个特征:文件以两个标记字节 `10 00` 开头;使用 CBC 模式的 Rijndael,分组为 **192 位(24 字节)**。实际后果是:标准 AES 库的分组固定为 128 位,不能原样用于这类数据,需要支持另一种分组大小的 Rijndael 实现。

### 5.3 密钥和 IV:它们是什么,以及本文不涉及什么

*密钥*是给密码算法设定的秘密参数,Rijndael 接受 128、192 或 256 位的密钥。*IV(初始化向量)*是 CBC 的起始值,大小和分组相同。密钥可以写成原始字节、ASCII 文本或十六进制,把这几种搞混是经典的 bug 来源:32 个 ASCII 字符是 32 字节,而 32 个十六进制字符只有 16 字节。

本文不公开、不推导、也不查找任何密钥,也不演示如何解密任何游戏文件。本文的主题是容器的结构,以及针对格式*解密后*形式的解码器。凡是某一步需要密钥的地方,我只说明需要,然后停下。

### 5.4 这个设计给我们的启示

无论用什么算法,要解密自己数据的客户端应用,总得把密钥放在设备上的某个地方。所以客户端加密只能防止随手查看,并不是强保护,真正重要的东西应该放在服务器端。这是关于系统设计的启示,不是操作指南。

### 5.5 我自己的探索

**我当年做的事(来自记忆)。** 初中时,我在手机上用 MT Manager 打开 APK,浏览里面的内容,并了解到游戏的数据文件是加密的,社区里有工具可以读取它们。这些工具不是我写的。我已经记不清它们的名字和我当时的操作顺序,本文也不会重复其中任何一项。

### 5.6 逐步看 CBC

CBC(密码分组链接)把数据切成与算法分组大小相同的块,这里是 24 字节。解密是这样的:

```text
明文[i] = Decrypt(密钥, 密文[i]) XOR 密文[i-1]      其中 密文[-1] = IV
```

每个块先单独用原始的分组算法解密,再与*前一个密文块*做异或;第一个块的"前一块"就是 IV。实际中有三个有用的推论:

1. **IV 只影响第一个块。** IV 错了只会让第 0 块乱码,后面的块仍然正确,这是区分"IV 错"和"密钥错"的一个好办法。
2. **解密第 i 块只需要两个密文块**,所以很长的输入可以分段处理。
3. **相同的明文块会加密成不同的密文**,因为每块都混入了前一块密文。这就是用 CBC 而不是逐块独立加密(ECB)的原因。

本节讲的是这种模式,不针对任何具体文件。

## 6. 在真实版本上验证容器层

**输入。** 一个中文版 Android APK(`baokai_4.2.7_1885_715_dj2.0-4.0.1.apk`,2,271,163,986 字节,SHA-256 `7c09515d…90a5d7`),2026-11-02 从游戏网站 <https://pvz2.hrgame.com.cn/> 下载,在本机分析。我只看容器层(外层封装、RSB 头部和资源组表),这里不解密也不解码游戏自己的数据。

**一个我没预料到的额外层。** 这个 APK 里的 RSB 不是裸文件:`assets/dynamic.rsb.smf` 以 ASCII 魔数 `RSLB` 开头。它是一个分块容器:32 字节头、若干 36 字节的块记录,然后每块一个原始 LZMA1 流(块大小 32 MiB,LZMA 参数 `lc=3 lp=0 pb=2`)。我是从社区解压器的注释里找到布局的,解压器是自己写的;它输出的正好是头部声明的 147,292,160 字节。所以这个版本的链路是:

```
APK -> .rsb.smf (RSLB, LZMA 分块) -> RSB -> RSGP -> RTON 文件(已加密,本文不涉及)
```

| 步骤 | 在这个 APK 上的结果 |
|---|---|
| 解开 `dynamic.rsb.smf` | 147,292,160 字节,以 `1bsr` 开头,与声明大小一致 |
| 读 RSB 头 | 版本 4,30 个资源组,组记录 `0xCC` 字节,PTX 记录 `0x18` 字节(Pvz2Tool 提到的"二代"变体) |
| 压缩 | 30 个资源组全部 `ZSize == Size`:**这个版本没有用到 zlib**,我完全没有实际测试过 zlib |
| 读一个 RSGP(`WorldPackages_beach`) | 魔数 `pgsr`,版本 4;第一部分以 `10 00` 开头,即加密 RTON 标记 |

**接下来。**
- 读取 RSGP 的文件名表,还原完整路径。
- 给解码器加入浮点数、64 位整数、UTF-8 字符串和 RTID,并配上新的合成测试数据。
- 在资源组有压缩的版本上实际测试 zlib。

### 6.1 RSLB 容器逐字段解读

`.smf` 文件 69,183,497 字节,展开后是 147,292,160 字节。所有数字都是小端。头部:

| 偏移 | 字段 | 这个文件里的值 |
|---|---|---|
| `0x00` | 魔数 | `RSLB` |
| `0x04` | 版本 | 1 |
| `0x08` | 解压后总大小 | 147,292,160 |
| `0x10` | 压缩后大小 | 69,183,465(= 文件大小 − 32) |
| `0x18` | 块大小 | 33,554,432(32 MiB) |
| `0x1C` | 块数量 | 5 |

头部之后是一张 36 字节记录的表,每块一条。这个文件的解码结果:

| 块 | 解压后起点 | 解压后大小 | 数据偏移 | 压缩后大小 | LZMA 字典 |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 33,554,432 | 212 | 10,267,186 | 33,554,432 |
| 1 | 33,554,432 | 33,554,432 | 10,267,398 | 22,168,257 | 33,554,432 |
| 2 | 67,108,864 | 33,554,432 | 32,435,655 | 18,241,763 | 33,554,432 |
| 3 | 100,663,296 | 33,554,432 | 50,677,418 | 14,198,046 | 33,554,432 |
| 4 | 134,217,728 | 13,074,432 | 64,875,464 | 4,308,033 | 13,631,488 |

每块的数据以 5 字节 LZMA 属性(`5D` 加 4 字节字典大小)开头,后面是没有结束标记的原始 LZMA1 流;表里给出了应该解出多少字节。属性字节 `0x5D` = 93,拆开是 `lc = 93 mod 9 = 3`、`lp = (93 div 9) mod 5 = 0`、`pb = 93 div 45 = 2`。

验证都对得上:块 0 的数据从 212 = `0x20` + 5 × 36 开始,紧跟在表后面;每块都从上一块结束的地方开始(212 + 10,267,186 = 10,267,398);五块的解压后大小加起来是 147,292,160;五块压缩后大小加上 212 字节的头部和表,正好等于文件大小。最后一块更短,字典也更小,原因我不清楚。

### 6.2 最先出错的地方

我保留了这些失败,因为它们说明各项检查有什么用。这些脚本是在第 4 节所说的 AI 助手协助下写成并运行的。

1. **一个流还是多个流?** 第一次尝试把 `.smf` 头部之后当作一个 LZMA 流解压。开头很顺利(`1bsr`,说明思路对),但解到约 33.6 MB 就报"Corrupt input data"。容器是按 32 MiB 分块的,修正办法是去读块表。
2. **头部偏移读错。** 第一个端到端脚本从 RSGP 头部的错误位置读取第一部分的偏移,`10 00` 标记检查立刻失败。我改正了偏移,并加了一条断言:RSGP 头部和 RSB 里的组记录必须一致。

这两个问题只靠合成测试都抓不到。

### 6.3 复现容器层的检查

你需要一个你有权使用的游戏安卓 APK 和 Python 3。脚本都在附录里。

1. APK 是 zip 文件。取出 `assets/dynamic.rsb.smf`(`unzip app.apk assets/dynamic.rsb.smf`)。
2. `python3 rslb.py dynamic.rsb.smf dynamic.rsb`(附录 C)。对我分析的那个版本,应得到 147,292,160 字节,以 `1bsr` 开头。其他版本会不同。
3. `python3 rsb_probe.py dynamic.rsb`(附录 D)。应看到版本 4、30 个资源组,第一个是 `Credits_1200`。
4. 或者用 `python3 inspect_build.py app.apk`(附录 F)一次完成第 1 到 3 步以及一致性检查。

如果某一步的数字不一样,请相信你自己的数字,并检查你的版本:这正是记录 APK 的 SHA-256 的意义。

## 7. 收获

这个项目让我对手机应用的安装包有了更整体的理解。这里我分析的是 Android 的 APK:它本质上是一个 zip 包,里面有原生库(`.so`)、`assets` 资源和配置。初三那年我也研究过 iOS 的应用安装包(IPA),了解了苹果代码签名的原理,这不属于本文的实验。

我也第一次比较系统地接触了加密的基本概念:密钥和 IV 的长度、不同分组密码的区别,以及 AES 和 Rijndael 的关系(这里分组大小不是 AES 的那一种,所以标准 AES 库并不适用)。

在方法上,先依据规格写测试再写代码很有用:这些测试数据逼着我在写任何解码器代码之前,先手算出 varint 和字符串缓存是怎么回事。逐字节注释一个样例文件,也让我学会了阅读结构化的二进制数据。

接下来我想把网络协议(HTTP 请求的加密)作为独立的研究,先完成可复现的实验,再另写一篇文章。

## 8. 常见问题与术语表

**RSB 本身加密了吗?** 这个版本没有。去掉 `.smf` 外层之后,RSB 头部能正常解析,各资源组都是未压缩存放的。里面的 RTON 文件带有 `10 00` 标记,说明它们是加密的。

**Rijndael 就是 AES 吗?** AES 是分组固定为 128 位的 Rijndael。这个游戏用的是 192 位分组,所以标准 AES 库并不适用。

**本文演示如何解密游戏数据吗?** 不演示。本文讲容器层,以及针对格式解密后形式的解码器,并用合成样例测试。文中没有密钥,也没有解密步骤。

**这个解码器能处理真实的 PVZ2 文件吗?** 本文没有测试这一点。它在合成样例上处理已有文档的那部分格式。浮点数、64 位整数、UTF-8 字符串和 RTID 都没实现,其他文件用到哪些我也不知道。

**解码器是原创的吗?** 这是我对一个已有文档的格式的实现,在 AI 助手协助下写成,我已读懂。它不是新发现,见第 4 节和参考资料。

**术语表**

- **魔数(magic number)**:文件开头用来标识类型的固定字节(`1bsr`、`pgsr`、`RTON`、`RSLB`)。
- **偏移 / 长度**:数据从哪里开始、占多少字节;几乎所有二进制格式的基础。
- **RSB**:PopCap 的资源包,把很多文件放在若干资源组里。
- **RSGP**:RSB 里的一个资源组。
- **SMF / RSLB**:这个版本里出现的外层封装,把 RSB 存成 LZMA 压缩的分块。
- **RTON**:PopCap 用来存类 JSON 数据的二进制序列化格式。
- **Varint**:变长整数,数值小就占更少字节。
- **分组密码 / 分组大小**:对固定大小的块进行操作的加密算法;Rijndael 允许 128、192 或 256 位。
- **IV(初始化向量)**:CBC 混入第一个块的起始值。
- **CBC**:密码分组链接,每个块都与前一个密文块混合。

## 9. 参考资料

- h3x4n1um,*RETON* — RTON 格式笔记。<https://github.com/h3x4n1um/RETON>
- DreamMoonCai,*Pvz2Tool*(MIT)— RSB/RSGP 头部定义。<https://github.com/DreamMoonCai/Pvz2Tool>
- apples1949,*PvZ2ModdingGuide* — 社区指南。<https://github.com/apples1949/PvZ2ModdingGuide>
- J. Daemen, V. Rijmen,*The Design of Rijndael*(Springer)。
- NIST,FIPS 197,*Advanced Encryption Standard*。
- Python `zlib`、`hashlib` 文档。

## 附录 A:解码器(`mini_rton/decoder.py`)

MIT 许可,版权 2026 Ray Tian。只支持第 4 节列出的标记,其余标记会抛出 `RtonError`。

```python
"""A minimal RTON decoder covering a documented subset of the format.

Format notes: https://github.com/h3x4n1um/RETON (see docs/rton-scope.md).
Supported tags: 00 01 08 0A 10 12 20 24 25 81 85 86(FD..FE) 90 91.
Anything else raises RtonError instead of guessing.
"""

MAGIC = b"RTON"
FOOTER = b"DONE"

TAG_FALSE, TAG_TRUE = 0x00, 0x01
TAG_INT8, TAG_UINT8 = 0x08, 0x0A
TAG_INT16, TAG_UINT16 = 0x10, 0x12
TAG_INT32 = 0x20
TAG_INT32_ZERO = 0x21
TAG_UVARINT, TAG_SVARINT = 0x24, 0x25
TAG_STRING = 0x81
TAG_OBJECT = 0x85
TAG_ARRAY = 0x86
TAG_CACHE_DEFINE, TAG_CACHE_RECALL = 0x90, 0x91
TAG_ARRAY_BEGIN, TAG_ARRAY_END = 0xFD, 0xFE
TAG_OBJECT_END = 0xFF

MAX_DEPTH = 64


class RtonError(ValueError):
    """Raised for malformed or unsupported input."""


class Reader:
    """A cursor over bytes: every read advances `pos`."""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.cache = []  # strings defined by tag 0x90, indexed by 0x91

    def read_bytes(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise RtonError(f"truncated: need {n} bytes at offset {self.pos}")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def read_u8(self):
        return self.read_bytes(1)[0]

    def read_int(self, size, signed):
        return int.from_bytes(self.read_bytes(size), "little", signed=signed)

    def read_uvarint(self):
        """7 payload bits per byte, low group first; high bit = more bytes."""
        result = 0
        shift = 0
        while True:
            byte = self.read_u8()
            result |= (byte & 0x7F) << shift
            if byte < 0x80:
                return result
            shift += 7
            if shift > 63:
                raise RtonError(f"varint too long at offset {self.pos}")

    def read_svarint(self):
        n = self.read_uvarint()
        return n // 2 if n % 2 == 0 else -(n + 1) // 2

    def read_string_body(self):
        length = self.read_uvarint()
        raw = self.read_bytes(length)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RtonError(f"invalid string bytes before offset {self.pos}") from exc

    def read_string(self, tag):
        """Read a string-valued tag (81, 90, 91) whose tag byte is already consumed."""
        if tag == TAG_STRING:
            return self.read_string_body()
        if tag == TAG_CACHE_DEFINE:
            text = self.read_string_body()
            self.cache.append(text)
            return text
        if tag == TAG_CACHE_RECALL:
            index = self.read_uvarint()
            if index >= len(self.cache):
                raise RtonError(f"cache index {index} out of range ({len(self.cache)} entries)")
            return self.cache[index]
        raise RtonError(f"expected string tag, got 0x{tag:02X} at offset {self.pos - 1}")

    def read_value(self, tag, depth):
        if depth > MAX_DEPTH:
            raise RtonError("nesting too deep")
        if tag == TAG_FALSE:
            return False
        if tag == TAG_TRUE:
            return True
        if tag == TAG_INT8:
            return self.read_int(1, True)
        if tag == TAG_UINT8:
            return self.read_int(1, False)
        if tag == TAG_INT16:
            return self.read_int(2, True)
        if tag == TAG_UINT16:
            return self.read_int(2, False)
        if tag == TAG_INT32:
            return self.read_int(4, True)
        if tag == TAG_INT32_ZERO:
            return 0  # no payload; listed as unconfirmed in the format notes
        if tag == TAG_UVARINT:
            return self.read_uvarint()
        if tag == TAG_SVARINT:
            return self.read_svarint()
        if tag in (TAG_STRING, TAG_CACHE_DEFINE, TAG_CACHE_RECALL):
            return self.read_string(tag)
        if tag == TAG_OBJECT:
            return self.read_object(depth + 1)
        if tag == TAG_ARRAY:
            return self.read_array(depth + 1)
        raise RtonError(f"unsupported tag 0x{tag:02X} at offset {self.pos - 1}")

    def read_object(self, depth):
        """Read key/value pairs until FF. The opening 85 is already consumed."""
        result = {}
        while True:
            tag = self.read_u8()
            if tag == TAG_OBJECT_END:
                return result
            key = self.read_string(tag)
            result[key] = self.read_value(self.read_u8(), depth)

    def read_array(self, depth):
        """86 FD <count> <values...> FE. The opening 86 is already consumed."""
        marker = self.read_u8()
        if marker != TAG_ARRAY_BEGIN:
            raise RtonError(f"expected FD after array tag, got 0x{marker:02X}")
        count = self.read_uvarint()
        items = [self.read_value(self.read_u8(), depth) for _ in range(count)]
        end = self.read_u8()
        if end != TAG_ARRAY_END:
            raise RtonError(f"expected FE at array end, got 0x{end:02X}")
        return items


def decode(data):
    """Decode RTON bytes into Python objects (dict at the top level)."""
    reader = Reader(bytes(data))
    if reader.read_bytes(4) != MAGIC:
        raise RtonError("bad magic: not an RTON file")
    version = reader.read_int(4, False)
    if version != 1:
        raise RtonError(f"unsupported version {version}")
    result = reader.read_object(0)
    if reader.read_bytes(4) != FOOTER:
        raise RtonError("missing DONE footer")
    if reader.pos != len(reader.data):
        raise RtonError(f"{len(reader.data) - reader.pos} trailing bytes after footer")
    return result
```


## 附录 B:合成测试数据(`tests/fixtures.py`)

每个字节都有注释,或由一个小编码器生成。错误处理的测试因篇幅省略。

```python
"""Hand-built RTON byte strings, each with its expected decoded value.

Every byte is annotated so you can check it against docs/rton-scope.md.
These are synthetic: they contain no game data.
"""

HEADER = bytes.fromhex("52544F4E" "01000000")  # "RTON" + version 1 (uint32 LE)
FOOTER = bytes.fromhex("444F4E45")              # "DONE"

# name -> (bytes, expected decoded Python value)
FIXTURES = {
    # {}   -- just the end-of-object marker FF
    "empty": (HEADER + bytes.fromhex("FF") + FOOTER, {}),

    # {"a": true, "b": false}
    #   81 01 61   string, 1 byte: "a"      01  true
    #   81 01 62   string, 1 byte: "b"      00  false
    "bools": (
        HEADER + bytes.fromhex("81 01 61 01  81 01 62 00  FF") + FOOTER,
        {"a": True, "b": False},
    ),

    # {"name": "Zombie"}
    #   81 04 6E616D65         "name"
    #   81 06 5A6F6D626965     "Zombie"
    "string": (
        HEADER + bytes.fromhex("81 04 6E616D65  81 06 5A6F6D626965  FF") + FOOTER,
        {"name": "Zombie"},
    ),

    # {"n": -2, "u": 200}
    #   08 FE   int8 0xFE = -2 (two's complement)
    #   0A C8   uint8 0xC8 = 200
    "small_ints": (
        HEADER + bytes.fromhex("81 01 6E 08 FE  81 01 75 0A C8  FF") + FOOTER,
        {"n": -2, "u": 200},
    ),

    # {"a": {"a": 1}}  -- cache define (90) then recall (91 00) inside a nested object
    #   90 01 61  define "a" (index 0)   85  object start
    #   91 00     recall index 0 ("a")   08 01  int8 1
    #   FF FF     inner end, outer end
    "nested_cache_recall": (
        HEADER + bytes.fromhex("90 01 61  85  91 00  08 01  FF  FF") + FOOTER,
        {"a": {"a": 1}},
    ),

    # {"a": [1, 2]}  -- 86 FD <count=2> 08 01 08 02 FE
    "array": (
        HEADER + bytes.fromhex("81 01 61  86 FD 02  08 01  08 02  FE  FF") + FOOTER,
        {"a": [1, 2]},
    ),

    # {"w": -300, "i": 70000}
    #   10 D4 FE  int16 LE: 0xFED4 = -300
    #   20 70 11 01 00  int32 LE: 0x00011170 = 70000
    "wide_ints": (
        HEADER + bytes.fromhex("81 01 77 10 D4 FE  81 01 69 20 70 11 01 00  FF") + FOOTER,
        {"w": -300, "i": 70000},
    ),

    # {"mX": 0, "mY": -150}  -- 21 = int32 zero (no payload);
    # 25 AB 02 -> varint 0x2B + (2 << 7) = 299 (odd) -> -(299+1)/2 = -150
    "int32_zero_and_signed": (
        HEADER + bytes.fromhex("81 02 6D 58 21  81 02 6D 59 25 AB 02  FF") + FOOTER,
        {"mX": 0, "mY": -150},
    ),

    # A made-up sample with the same *shape* as a typical object file: a version, then an array of
    # objects (uid / objclass / objdata). The second object reuses keys and values through the string
    # cache (91). Built with a small encoder; annotated byte by byte in the article (section 3.6).
    "showcase": (
        bytes.fromhex(
            "52 54 4f 4e 01 00 00 00 90 07 76 65 72 73 69 6f 6e 24 01 90 07 6f 62 6a 65 63 74 73 86 fd 02 85"
            "90 03 75 69 64 90 05 31 2e 30 2e 31 90 08 6f 62 6a 63 6c 61 73 73 90 08 44 65 6d 6f 44 61 74 61"
            "90 07 6f 62 6a 64 61 74 61 85 90 04 6e 61 6d 65 90 04 64 65 6d 6f 90 05 69 74 65 6d 73 86 fd 00"
            "fe 90 04 66 6c 61 67 01 90 05 63 6f 75 6e 74 24 f4 03 90 06 6f 72 69 67 69 6e 25 95 01 90 04 7a"
            "65 72 6f 21 90 03 62 6f 78 85 90 01 78 21 90 01 79 25 95 01 90 01 77 21 90 01 68 24 c8 01 ff ff"
            "ff 85 91 02 90 05 31 2e 30 2e 32 91 04 91 05 91 06 85 91 07 90 05 64 65 6d 6f 32 91 09 86 fd 02"
            "24 01 24 02 fe 91 0a 00 91 0b 24 07 91 0c 21 91 0d 21 91 0e 85 91 0f 24 05 91 10 25 01 91 11 21"
            "91 12 24 09 ff ff ff fe ff 44 4f 4e 45"
        ),
        {'version': 1, 'objects': [{'uid': '1.0.1', 'objclass': 'DemoData', 'objdata': {'name': 'demo', 'items': [], 'flag': True, 'count': 500, 'origin': -75, 'zero': 0, 'box': {'x': 0, 'y': -75, 'w': 0, 'h': 200}}}, {'uid': '1.0.2', 'objclass': 'DemoData', 'objdata': {'name': 'demo2', 'items': [1, 2], 'flag': False, 'count': 7, 'origin': 0, 'zero': 0, 'box': {'x': 5, 'y': -1, 'w': 0, 'h': 9}}}]},
    ),

    # --- varint fixtures ---
    # {"Value": 61}: key via cache-define 90, value unsigned varint 24 3D (0x3D = 61)
    "varint_cached_key": (
        HEADER + bytes.fromhex("90 05 56616C7565  24 3D  FF") + FOOTER,
        {"Value": 61},
    ),
    # {"n": -2}: signed varint 25 03 -> n=3 is odd -> -(3+1)/2 = -2
    "signed_varint": (
        HEADER + bytes.fromhex("81 01 6E  25 03  FF") + FOOTER,
        {"n": -2},
    ),
    # {"x": 254}: varint FE 01 -> 0x7E + (1 << 7) = 254
    "varint_two_bytes": (
        HEADER + bytes.fromhex("81 01 78  24 FE 01  FF") + FOOTER,
        {"x": 254},
    ),
}
```


## 附录 C:RSLB(.smf)解压脚本(`rslb.py`)

MIT 许可,版权 2026 Ray Tian。在 AI 助手协助下写成;布局来自参考资料中引用的格式说明。

```python
"""Decompress an RSLB (.smf) container: a header, a block table, then one raw LZMA1 stream per block.

Layout (from the format description in yhzxcv/Z-Editor's RslbDecompressor comments;
this implementation is written independently):
  0x00 "RSLB" | 0x04 u32 version | 0x08 u64 total_uncompressed | 0x10 u64 packed_size
  0x18 u32 block_size | 0x1C u32 block_count | 0x20 block table, 36 bytes each:
    u64 cum_offset, u32 usize, u32 reserved, u64 data_offset, u32 csize (incl. 5-byte props),
    u8 lzma_props, u32 dict_size, 3 pad
  each block at data_offset: 5 bytes (props + dict) then raw LZMA1 data (no end marker).
"""
import lzma
import struct
import sys


def decompress(src_path, dst_path):
    with open(src_path, "rb") as f:
        data = f.read()
    magic, version, total, packed, block_size, count = struct.unpack_from("<4sIQQII", data, 0)
    if magic != b"RSLB":
        raise ValueError("not an RSLB file")
    produced = 0
    with open(dst_path, "wb") as out:
        for i in range(count):
            cum, usize, _res, doff, csize, props, dict_size = struct.unpack_from(
                "<QIIQIBI", data, 0x20 + i * 36)
            if cum != produced:
                raise ValueError(f"block {i}: offset gap")
            lc = props % 9
            lp = (props // 9) % 5
            pb = props // 45
            filters = [{"id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": lc, "lp": lp, "pb": pb}]
            stream = data[doff + 5: doff + csize]
            chunk = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters).decompress(
                stream, max_length=usize)
            if len(chunk) != usize:
                raise ValueError(f"block {i}: got {len(chunk)} bytes, expected {usize}")
            out.write(chunk)
            produced += usize
    if produced != total:
        raise ValueError(f"total {produced} != declared {total}")
    return produced


if __name__ == "__main__":
    print(decompress(sys.argv[1], sys.argv[2]), "bytes written")
```


## 附录 D:RSB 头部与资源组表读取脚本(`rsb_probe.py`)

字段顺序参照 Pvz2Tool(MIT)描述的布局。只读:不提取任何内容。

```python
"""Read an RSB header and its resource-group (RSGP) table.

Field order follows the layout described by Pvz2Tool's RsbHeadInfo / RsbRsgpInfo
(MIT). Written independently; read-only, extracts nothing.
"""
import struct
import sys

HEADER_FIELDS = [
    "magic", "version", "zero0", "headLength", "fileList_Length", "fileList_BeginOffset",
    "zero1", "zero2", "rsgpList_Length", "rsgpList_BeginOffset", "rsgp_Number",
    "rsgpInfo_BeginOffset", "rsgpInfo_EachLength", "composite_Number", "compositeInfo_BeginOffset",
    "compositeInfo_EachLength", "compositeList_Length", "compositeList_BeginOffset",
    "autopool_Number", "autopoolInfo_BeginOffset", "autopoolInfo_EachLength", "ptx_Number",
    "ptxInfo_BeginOffset", "ptxInfo_EachLength", "xmlPart1", "xmlPart2", "xmlPart3",
]

GROUP_FIELDS = ["offset", "size", "pool_index", "flags", "fileOffset", "p0_offset", "p0_zsize",
                "p0_size", "p0_size2", "p1_offset", "p1_zsize", "p1_size"]


def read_header(data):
    vals = struct.unpack_from("<" + "I" * len(HEADER_FIELDS), data, 0)
    h = dict(zip(HEADER_FIELDS, vals))
    if data[:4] != b"1bsr":
        raise ValueError("bad RSB magic")
    return h


def read_groups(data, h):
    groups = []
    base, each = h["rsgpInfo_BeginOffset"], h["rsgpInfo_EachLength"]
    for i in range(h["rsgp_Number"]):
        rec = data[base + i * each: base + (i + 1) * each]
        name = rec[:0x80].split(b"\0", 1)[0].decode("ascii", "replace")
        nums = struct.unpack_from("<" + "I" * len(GROUP_FIELDS), rec, 0x80)
        groups.append({"name": name, **dict(zip(GROUP_FIELDS, nums))})
    return groups


if __name__ == "__main__":
    data = open(sys.argv[1], "rb").read()
    h = read_header(data)
    for k in ("version", "headLength", "rsgp_Number", "rsgpInfo_BeginOffset", "rsgpInfo_EachLength",
              "ptxInfo_EachLength"):
        print(f"{k} = {h[k]} (0x{h[k]:X})")
    print("zero fields ok:", h["zero0"] == h["zero1"] == h["zero2"] == 0)
    for g in read_groups(data, h)[:12]:
        print(g["name"], "off", g["offset"], "size", g["size"], "p0", g["p0_zsize"], "->", g["p0_size"],
              "p1", g["p1_zsize"], "->", g["p1_size"], "flags", g["flags"])
```


## 附录 E:RTON 逐字节注释脚本(`annotate_rton.py`)

使用与解码器相同的标记规则;对任何未加密的 RTON 输出 3.6 节展示的逐字节解读。

```python
"""Print an annotated hex walk-through of an (unencrypted) RTON using the same tag rules as mini_rton.
Prints facts only. Usage: python3 -I annotate_rton.py file.rton"""
import struct, sys

def uvarint(d, p):
    r = s = 0
    while True:
        b = d[p]; p += 1
        r |= (b & 0x7F) << s
        if b < 0x80: return r, p
        s += 7

def walk(d):
    rows = []; cache = []; p = 0
    def row(a, b, text, depth): rows.append((a, d[a:b], '  ' * depth + text))
    row(0, 4, 'magic "RTON"', 0); row(4, 8, 'version = 1 (uint32 LE)', 0); p = 8
    def val(p, depth):
        t = d[p]
        if t in (0, 1): row(p, p+1, 'false' if t == 0 else 'true', depth); return p+1
        if t in (0x08, 0x0A, 0x10, 0x12, 0x20):
            n = {0x08:1,0x0A:1,0x10:2,0x12:2,0x20:4}[t]; sg = t in (0x08,0x10,0x20)
            v = int.from_bytes(d[p+1:p+1+n], 'little', signed=sg)
            row(p, p+1+n, f'fixed int, value {v}', depth); return p+1+n
        if t == 0x21: row(p, p+1, 'int32 zero (no payload) = 0', depth); return p+1
        if t in (0x24, 0x25):
            n, q = uvarint(d, p+1); v = n if t == 0x24 else (n//2 if n % 2 == 0 else -(n+1)//2)
            row(p, q, ('unsigned' if t == 0x24 else 'signed') + f' varint = {v}', depth); return q
        if t == 0x81:
            n, q = uvarint(d, p+1); s = d[q:q+n].decode(); row(p, q+n, f'string "{s}"', depth); return q+n
        if t == 0x90:
            n, q = uvarint(d, p+1); s = d[q:q+n].decode(); cache.append(s)
            row(p, q+n, f'define cache[{len(cache)-1}] = "{s}"', depth); return q+n
        if t == 0x91:
            n, q = uvarint(d, p+1); row(p, q, f'recall cache[{n}] = "{cache[n]}"', depth); return q
        if t == 0x85: row(p, p+1, 'object start', depth); return obj(p+1, depth+1)
        if t == 0x86:
            assert d[p+1] == 0xFD; n, q = uvarint(d, p+2); row(p, q, f'array start, {n} item(s)', depth)
            for _ in range(n): q = val(q, depth+1)
            assert d[q] == 0xFE; row(q, q+1, 'array end', depth); return q+1
        raise ValueError(hex(t))
    def key(p, depth):
        t = d[p]
        if t == 0x81 or t == 0x90:
            n, q = uvarint(d, p+1); s = d[q:q+n].decode()
            if t == 0x90: cache.append(s)
            row(p, q+n, ('key, define cache[%d]' % (len(cache)-1) if t == 0x90 else 'key') + f' "{s}"', depth); return q+n
        n, q = uvarint(d, p+1); row(p, q, f'key, recall cache[{n}] = "{cache[n]}"', depth); return q
    def obj(p, depth):
        while d[p] != 0xFF:
            p = key(p, depth); p = val(p, depth)
        row(p, p+1, 'object end', depth-1); return p+1
    p = obj(p, 1)
    row(p, p+4, 'footer "DONE"', 0)
    assert p + 4 == len(d)
    return rows, cache

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    rows, cache = walk(d)
    def short(b):
        return b.hex(' ') if len(b) <= 8 else b[:8].hex(' ') + f' ..+{len(b) - 8}'
    for a, b, t in rows: print(f'{a:04X}  {short(b):<30} {t}')
    print('CACHE', cache)
```


## 附录 F:容器检查脚本(`inspect_build.py`)

解开 `.smf`,读取 RSB 头部和资源组表,并做一致性检查。它不解密也不解码任何游戏数据。请把 `rslb.py` 和 `rsb_probe.py` 放在它旁边。

```python
"""Container-level inspection of a locally owned APK: unwrap assets/dynamic.rsb.smf, read the RSB header
and group table, and run consistency checks. It does not decrypt or decode any game data and writes
nothing outside a temporary folder.

APK -> assets/dynamic.rsb.smf -> (RSLB / LZMA blocks) -> RSB -> resource groups

Usage:  python3 -I tools/inspect_build.py path/to/game.apk
"""
import os
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rslb  # noqa: E402
from rsb_probe import read_groups, read_header  # noqa: E402


def main(apk):
    with tempfile.TemporaryDirectory() as tmp:
        smf_path, rsb_path = os.path.join(tmp, "x.smf"), os.path.join(tmp, "x.rsb")
        with zipfile.ZipFile(apk) as z:
            open(smf_path, "wb").write(z.read("assets/dynamic.rsb.smf"))
        print("SMF magic:", open(smf_path, "rb").read(4))
        size = rslb.decompress(smf_path, rsb_path)
        data = open(rsb_path, "rb").read()
    h = read_header(data)
    groups = read_groups(data, h)
    print("RSB bytes:", size, "magic:", data[:4], "version:", h["version"], "groups:", h["rsgp_Number"])
    print("first group starts at headLength:", groups[0]["offset"] == h["headLength"])
    print("groups are contiguous:", all(groups[i]["offset"] + groups[i]["size"] == groups[i + 1]["offset"]
                                        for i in range(len(groups) - 1)))
    print("last group ends at end of file:", groups[-1]["offset"] + groups[-1]["size"] == len(data))
    print("all offsets/sizes multiples of 4096:", all(g["offset"] % 4096 == 0 and g["size"] % 4096 == 0 for g in groups))
    print("every group stored uncompressed (ZSize == Size):",
          all(g["p0_zsize"] == g["p0_size"] and g["p1_zsize"] == g["p1_size"] for g in groups))
    for g in groups:
        print(f"  {g['name']:36s} offset={g['offset']:>11,} size={g['size']:>11,}")


if __name__ == "__main__":
    main(sys.argv[1])
```
