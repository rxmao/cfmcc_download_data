# CFMMC 交易报告下载工具

一个用于从中国期货市场监控中心（CFMMC - China Futures Market Monitoring Center）自动下载交易报告的 Python 客户端工具。

## 功能特性

- ✅ 自动登录 CFMMC 投资者服务网站
- ✅ 使用 OCR 技术自动识别验证码
- ✅ 支持下载指定日期的交易报告（Excel 格式）
- ✅ **支持日期区间批量下载**
- ✅ 支持下载交易报告和结算报告
- ✅ **自动跳过周末（可选）**
- ✅ 自动会话管理和重连
- ✅ 支持环境变量和命令行参数配置
- ✅ **批量下载进度跟踪和统计**
- ✅ **错误容错机制（可选择遇错继续）**
- ✅ 详细的日志输出

## 系统要求

- Python 3.7+
- 稳定的网络连接

## 安装步骤

### 1. 克隆仓库

```bash
git clone <repository-url>
cd cfmcc_download_data
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

### 方式一：使用环境变量（推荐）

1. 复制示例配置文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入您的 CFMMC 凭证：
```bash
CFMMC_USER_ID=your_user_id_here
CFMMC_PASSWORD=your_password_here
```

3. 在使用前加载环境变量：
```bash
# Linux/macOS
export $(cat .env | xargs)

# 或者使用 source（如果安装了 dotenv）
source .env
```

### 方式二：使用命令行参数

直接在命令行中指定用户 ID 和密码（不推荐用于生产环境）。

## 使用方法

### 基本用法

使用环境变量：
```bash
# 设置环境变量
export CFMMC_USER_ID="your_user_id"
export CFMMC_PASSWORD="your_password"

# 下载指定日期的交易报告（默认保存到 ./data 目录）
python cfmmc_client.py --date 2025-11-21
```

使用命令行参数：
```bash
python cfmmc_client.py --user your_user_id --password your_password --date 2025-11-21
```

### 高级用法

#### 1. 下载日期区间的报告

批量下载多天的报告：
```bash
# 下载 2025-11-01 到 2025-11-10 之间所有日期的报告
python cfmmc_client.py --start-date 2025-11-01 --end-date 2025-11-10

# 跳过周末（周六和周日）
python cfmmc_client.py --start-date 2025-11-01 --end-date 2025-11-30 --skip-weekends

# 遇到错误时继续下载其他日期
python cfmmc_client.py --start-date 2025-11-01 --end-date 2025-11-10 --continue-on-error
```

#### 2. 指定输出目录

```bash
# 保存到自定义目录
python cfmmc_client.py --date 2025-11-21 --output-dir ./reports

# 默认保存到 ./data 目录
python cfmmc_client.py --date 2025-11-21
```

#### 3. 下载结算报告

```bash
python cfmmc_client.py --date 2025-11-21 --type settlement
```

#### 4. 调整批量下载参数

```bash
# 自定义请求延迟（避免请求过于频繁）
python cfmmc_client.py --start-date 2025-11-01 --end-date 2025-11-10 --delay 2.0

# 增加登录重试次数
python cfmmc_client.py --date 2025-11-21 --max-attempts 5
```

#### 5. 查看帮助信息

```bash
python cfmmc_client.py --help
```

### 命令行参数说明

| 参数 | 简写 | 说明 | 必需 | 默认值 |
|------|------|------|------|--------|
| `--user` | `-u` | CFMMC 用户 ID | 否* | - |
| `--password` | `-p` | CFMMC 密码 | 否* | - |
| `--date` | `-d` | 单个交易日期 (YYYY-MM-DD) | 否** | - |
| `--start-date` | - | 开始日期 (YYYY-MM-DD) | 否** | - |
| `--end-date` | - | 结束日期 (YYYY-MM-DD) | 否** | - |
| `--type` | `-t` | 报告类型 (trade/settlement) | 否 | trade |
| `--output-dir` | `-o` | 报告保存目录 | 否 | ./data |
| `--skip-weekends` | - | 跳过周末 | 否 | false |
| `--continue-on-error` | - | 遇错继续下载 | 否 | false |
| `--max-attempts` | - | 最大登录尝试次数 | 否 | 3 |
| `--delay` | - | 批量下载请求延迟（秒） | 否 | 1.0 |

\* 必须通过命令行参数或环境变量提供
\*\* 必须提供 `--date` 或 `--start-date` 和 `--end-date` 组合

## 项目结构

```
cfmcc_download_data/
├── cfmmc_client.py      # 主程序文件
├── requirements.txt      # Python 依赖列表
├── .env.example         # 环境变量配置示例
├── .gitignore           # Git 忽略文件配置
├── README.md            # 项目说明文档
└── LICENSE              # 开源许可证
```

## 代码结构

### CfmmcClient 类

主要客户端类，提供以下功能：

#### 初始化参数
- `user_id`: CFMMC 用户 ID
- `password`: CFMMC 密码
- `max_login_attempts`: 最大登录尝试次数（默认：3）

#### 主要方法

- `login()`: 登录 CFMMC 系统
- `download_daily_report(trade_date, by_type)`: 下载指定日期的报告
  - `trade_date`: 交易日期（datetime.date 对象）
  - `by_type`: 报告类型，可选 "trade"（交易）或 "settlement"（结算）

#### 私有方法

- `_fetch_login_page()`: 获取登录页面
- `_extract_token()`: 提取 Struts Token
- `_extract_captcha_url()`: 提取验证码 URL
- `_recognize_captcha()`: 使用 OCR 识别验证码
- `_submit_login()`: 提交登录表单
- `_ensure_logged_in()`: 确保已登录
- `_check_login_status()`: 检查登录状态
- `_fetch_customer_token()`: 获取客户页面 Token
- `_set_parameter()`: 设置下载参数

## 依赖说明

- `requests`: HTTP 客户端库，用于网络请求
- `ddddocr`: OCR 识别库，用于自动识别验证码

## 安全建议

1. ⚠️ **不要将凭证信息提交到 Git 仓库**
   - `.env` 文件已在 `.gitignore` 中排除
   - 仅提供 `.env.example` 作为配置模板

2. ⚠️ **使用环境变量而非硬编码**
   - 推荐使用环境变量或配置文件管理凭证
   - 避免在代码中硬编码敏感信息

3. ⚠️ **保护下载的报告文件**
   - 下载的 Excel 文件包含敏感的交易信息
   - 请妥善保管，避免泄露

4. ⚠️ **定期更新依赖**
   - 定期检查并更新依赖库以修复安全漏洞

## 故障排除

### 登录失败

1. **验证码识别错误**
   - OCR 识别可能不是 100% 准确
   - 程序会自动重试（默认 3 次）
   - 可通过 `--max-attempts` 增加重试次数

2. **凭证错误**
   - 检查用户 ID 和密码是否正确
   - 确认账号未被锁定

3. **网络问题**
   - 检查网络连接
   - 确认可以访问 https://investorservice.cfmmc.com/

### 下载失败

1. **日期无效**
   - 确保日期格式正确：YYYY-MM-DD
   - 确保是交易日（非周末和节假日）

2. **会话过期**
   - 程序会自动检测并重新登录

## 技术细节

### 工作原理

1. **登录流程**：
   - 访问登录页面获取 Struts Token 和验证码
   - 使用 ddddocr 进行验证码 OCR 识别
   - 提交登录表单（包含用户 ID、密码、验证码和 Token）
   - 验证登录是否成功（检查页面是否包含"退出系统"）

2. **下载流程**：
   - 确保会话已登录
   - 获取客户详情页面的 Token
   - 设置下载参数（日期、报告类型）
   - 下载 Excel 文件并保存到本地

3. **会话管理**：
   - 使用 `requests.Session()` 维护 Cookie
   - 自动检测会话状态
   - 会话失效时自动重新登录

### API 端点

- 基础 URL: `https://investorservice.cfmmc.com/`
- 登录: `/login.do`
- 客户视图: `/customer/setupViewCustomerDetailFromCompanyAuto.do`
- 设置参数: `/customer/setParameter.do`
- 下载报告: `/customer/setupViewCustomerDetailFromCompanyWithExcel.do`
- 验证码: `/veriCode.do`

## 注意事项

1. 本工具仅供学习和个人使用
2. 请遵守 CFMMC 网站的使用条款
3. 不要过于频繁地请求，以免对服务器造成压力
4. 妥善保管您的账号凭证和下载的数据

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 免责声明

本工具仅用于技术学习和研究目的。使用本工具产生的任何后果由使用者自行承担。作者不对因使用本工具造成的任何直接或间接损失负责。

---

**关键词**: CFMMC, 期货, 交易报告, 自动下载, Python, OCR, 验证码识别
