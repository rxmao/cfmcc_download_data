import argparse
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import ddddocr
import requests

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def generate_date_range(start_date: date, end_date: date) -> List[date]:
    """生成日期范围列表（包含起始和结束日期）"""
    if start_date > end_date:
        raise ValueError(f"开始日期 {start_date} 不能晚于结束日期 {end_date}")

    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += timedelta(days=1)

    return date_list


class CfmmcClient:
    BASE_URL = "https://investorservice.cfmmc.com/"
    LOGIN_URL = urljoin(BASE_URL, "login.do")
    CUSTOMER_VIEW_URL = urljoin(BASE_URL, "customer/setupViewCustomerDetailFromCompanyAuto.do")
    SET_PARAMETER_URL = urljoin(BASE_URL, "customer/setParameter.do")
    DOWNLOAD_URL = urljoin(BASE_URL, "customer/setupViewCustomerDetailFromCompanyWithExcel.do")
    TOKEN_PATTERN = re.compile(r'name="org\.apache\.struts\.taglib\.html\.TOKEN"\s+value="([^"]+)"')
    CAPTCHA_PATTERN = re.compile(r'src="(/veriCode\.do\?t=[^"]+)"')

    def __init__(
        self,
        user_id: str,
        password: str,
        max_login_attempts: int = 3,
    ) -> None:
        self.session = requests.Session()
        self.user_id = user_id
        self.password = password
        self.ocr = ddddocr.DdddOcr()
        self.max_login_attempts = max_login_attempts

    def login(self) -> None:
        for attempt in range(1, self.max_login_attempts + 1):
            token, captcha_url = self._fetch_login_page()
            captcha_text = self._recognize_captcha(captcha_url)
            logging.info("Attempt %s/%s with captcha %s", attempt, self.max_login_attempts, captcha_text)
            if self._submit_login(token, captcha_text):
                logging.info("CFMMC login succeed.")
                return
            logging.warning("Login attempt %s failed, retrying...", attempt)
        raise RuntimeError("Unable to login CFMMC after multiple attempts.")

    def download_daily_report(self, trade_date: datetime, by_type: str = "trade", output_dir: Optional[Path] = None) -> Path:
        logging.info("=" * 60)
        logging.info("开始下载日期 %s 的报表", trade_date.strftime('%Y-%m-%d'))

        self._ensure_logged_in()
        logging.debug("登录检查完成")

        token = self._fetch_customer_token()
        logging.debug("获取到 TOKEN: %s", token[:20] + "..." if len(token) > 20 else token)

        self._set_parameter(trade_date, by_type, token)
        logging.debug("参数设置完成")
        
        # 等待服务器处理参数设置（模拟人工操作延迟）
        time.sleep(1.5)

        # 添加更详细的请求头，模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': self.CUSTOMER_VIEW_URL,
        }

        logging.debug("发送下载请求到: %s", self.DOWNLOAD_URL)
        logging.debug("当前会话 cookies: %d 个", len(self.session.cookies))

        # stream=True 避免自动解压，获取原始响应
        resp = self.session.get(self.DOWNLOAD_URL, headers=headers, timeout=30)
        resp.raise_for_status()

        # 调试信息：记录响应状态
        logging.info("响应状态: %d | Content-Type: %s | 文件大小: %d 字节",
                     resp.status_code, resp.headers.get('Content-Type', 'unknown'), len(resp.content))
        logging.debug("完整响应头: %s", dict(resp.headers))
        
        # 如果返回空内容，记录可能的原因
        if len(resp.content) == 0:
            logging.warning("服务器返回了空响应。可能原因:")
            logging.warning("  1. 该日期 %s 无交易数据（周末/节假日/历史过久）", trade_date.strftime('%Y-%m-%d'))
            logging.warning("  2. 服务器端反爬虫检测")

        # 检查响应内容是否为空
        if not resp.content or len(resp.content) == 0:
            raise RuntimeError(f"下载的文件内容为空，日期: {trade_date:%Y-%m-%d}，可能该日期无交易数据或触发了反爬虫限制")

        # 检查是否返回了 HTML 页面（而不是 Excel 文件）
        if resp.content.startswith(b'<!DOCTYPE') or resp.content.startswith(b'<html'):
            # 尝试提取错误信息
            content_preview = resp.content[:500].decode('utf-8', errors='ignore')
            logging.error("服务器返回了HTML页面而不是Excel文件。内容预览: %s", content_preview)
            raise RuntimeError(f"服务器返回了网页而不是Excel文件，可能登录已过期或触发了反爬虫机制")

        # 检查是否是有效的 Excel 文件（XLS 文件头应该以 D0CF11E0 开始）
        if len(resp.content) < 8 or not resp.content.startswith(b'\xD0\xCF\x11\xE0'):
            # 记录实际接收到的内容前16字节（十六进制）
            content_hex = resp.content[:16].hex() if resp.content else "empty"
            logging.warning("下载的文件可能不是有效的 Excel 文件，文件大小: %d 字节，文件头: %s",
                          len(resp.content), content_hex)

        # 确定输出目录（在基础目录下创建以用户ID命名的子目录）
        if output_dir is None:
            output_dir = Path(".")

        # 为每个账户创建独立的子目录
        user_dir = output_dir / self.user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        file_path = user_dir / f"cfmmc_{trade_date:%Y%m%d}.xls"
        file_path.write_bytes(resp.content)
        logging.info("Daily report saved to %s (size: %d bytes)", file_path, len(resp.content))
        return file_path

    def _fetch_login_page(self) -> Tuple[str, str]:
        resp = self.session.get(self.BASE_URL, timeout=30)
        resp.raise_for_status()
        token = self._extract_token(resp.text)
        captcha_url = self._extract_captcha_url(resp.text)
        return token, captcha_url

    def _extract_token(self, html: str) -> str:
        match = self.TOKEN_PATTERN.search(html)
        if not match:
            raise RuntimeError("Cannot find Struts TOKEN on login page.")
        return match.group(1)

    def _extract_captcha_url(self, html: str) -> str:
        match = self.CAPTCHA_PATTERN.search(html)
        if not match:
            raise RuntimeError("Cannot find captcha url in login page.")
        return urljoin(self.BASE_URL, match.group(1))

    def _recognize_captcha(self, captcha_url: str) -> str:
        resp = self.session.get(captcha_url, timeout=30)
        resp.raise_for_status()
        return self.ocr.classification(resp.content)

    def _submit_login(self, token: str, vericode: str) -> bool:
        payload = {
            "org.apache.struts.taglib.html.TOKEN": token,
            "showSaveCookies": "",
            "userID": self.user_id,
            "password": self.password,
            "vericode": vericode,
        }
        resp = self.session.post(self.LOGIN_URL, data=payload, timeout=30)
        resp.raise_for_status()
        return "退出系统" in resp.text

    def _ensure_logged_in(self) -> None:
        if self._check_login_status():
            return
        logging.info("Session not authenticated, re-login required.")
        self.login()

    def _check_login_status(self) -> bool:
        resp = self.session.get(self.CUSTOMER_VIEW_URL, timeout=30)
        if "退出系统" not in resp.text:
            return False
        return True

    def _fetch_customer_token(self) -> str:
        resp = self.session.get(self.CUSTOMER_VIEW_URL, timeout=30)
        resp.raise_for_status()
        return self._extract_token(resp.text)

    def _set_parameter(self, trade_date: datetime, by_type: str, token: str) -> None:
        payload = {
            "org.apache.struts.taglib.html.TOKEN": token,
            "tradeDate": trade_date.strftime("%Y-%m-%d"),
            "byType": by_type,
        }
        resp = self.session.post(self.SET_PARAMETER_URL, data=payload, timeout=30)
        resp.raise_for_status()
        if resp.status_code != 200:
            raise RuntimeError("Failed to set parameters for report download.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='CFMMC 期货市场监控中心交易报告下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 下载单个日期的报告（默认保存到 ./data 目录）
  export CFMMC_USER_ID="your_user_id"
  export CFMMC_PASSWORD="your_password"
  python cfmmc_client.py --date 2025-11-21

  # 下载日期区间的报告
  python cfmmc_client.py --start-date 2025-11-01 --end-date 2025-11-10

  # 指定输出目录
  python cfmmc_client.py --date 2025-11-21 --output-dir ./reports

  # 指定报告类型
  python cfmmc_client.py --date 2025-11-21 --type settlement

  # 批量下载并跳过周末
  python cfmmc_client.py --start-date 2025-11-01 --end-date 2025-11-30 --skip-weekends
        """
    )

    parser.add_argument(
        '-u', '--user',
        type=str,
        help='CFMMC 用户 ID (也可通过环境变量 CFMMC_USER_ID 设置)'
    )
    parser.add_argument(
        '-p', '--password',
        type=str,
        help='CFMMC 密码 (也可通过环境变量 CFMMC_PASSWORD 设置)'
    )
    parser.add_argument(
        '-d', '--date',
        type=str,
        help='单个交易日期，格式: YYYY-MM-DD (例如: 2025-11-21)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='开始日期，格式: YYYY-MM-DD (与 --end-date 配合使用下载区间)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='结束日期，格式: YYYY-MM-DD (与 --start-date 配合使用下载区间)'
    )
    parser.add_argument(
        '-t', '--type',
        type=str,
        default='trade',
        choices=['trade', 'settlement'],
        help='报告类型: trade (交易报告) 或 settlement (结算报告)，默认: trade'
    )
    parser.add_argument(
        '--skip-weekends',
        action='store_true',
        help='跳过周末（周六和周日）'
    )
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='遇到错误时继续下载其他日期的报告'
    )
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=3,
        help='最大登录尝试次数，默认: 3'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='批量下载时每次请求之间的延迟（秒），默认: 1.0'
    )
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default='./data',
        help='报告文件保存目录，默认: ./data'
    )

    args = parser.parse_args()

    # 从命令行参数或环境变量获取凭证
    user_id = args.user or os.getenv('CFMMC_USER_ID')
    password = args.password or os.getenv('CFMMC_PASSWORD')

    if not user_id or not password:
        parser.error('必须提供用户 ID 和密码，可通过命令行参数或环境变量 CFMMC_USER_ID 和 CFMMC_PASSWORD 设置')

    # 验证日期参数
    if args.date and (args.start_date or args.end_date):
        parser.error('不能同时使用 --date 和 --start-date/--end-date 参数')

    if not args.date and not (args.start_date and args.end_date):
        parser.error('必须提供 --date 或 --start-date 和 --end-date 参数')

    # 解析日期
    date_list: List[date] = []
    try:
        if args.date:
            # 单个日期
            date_list = [datetime.strptime(args.date, '%Y-%m-%d').date()]
        else:
            # 日期区间
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
            date_list = generate_date_range(start_date, end_date)

            # 跳过周末
            if args.skip_weekends:
                date_list = [d for d in date_list if d.weekday() < 5]  # 0-4 表示周一到周五

    except ValueError as e:
        parser.error(f'无效的日期格式，请使用 YYYY-MM-DD 格式: {e}')

    # 创建客户端并下载报告
    try:
        logging.info('正在初始化 CFMMC 客户端...')
        client = CfmmcClient(
            user_id=user_id,
            password=password,
            max_login_attempts=args.max_attempts
        )

        logging.info('正在登录...')
        client.login()

        # 创建输出目录
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 报告将保存到 output_dir/user_id/ 目录下
        user_output_dir = output_dir / user_id
        logging.info('报告将保存到目录: %s', user_output_dir.absolute())

        report_type_name = '交易' if args.type == 'trade' else '结算'
        total_dates = len(date_list)
        success_count = 0
        failed_count = 0
        failed_dates = []

        logging.info('准备下载 %d 个日期的%s报告...', total_dates, report_type_name)

        for idx, trade_date in enumerate(date_list, 1):
            try:
                logging.info('[%d/%d] 正在下载 %s 的%s报告...', idx, total_dates, trade_date, report_type_name)
                file_path = client.download_daily_report(trade_date, by_type=args.type, output_dir=output_dir)
                logging.info('✓ [%d/%d] 下载完成！文件保存在: %s', idx, total_dates, file_path.absolute())
                success_count += 1

                # 批量下载时添加延迟，避免请求过于频繁
                if total_dates > 1 and idx < total_dates:
                    time.sleep(args.delay)

            except Exception as e:
                failed_count += 1
                failed_dates.append(trade_date)
                logging.error('✗ [%d/%d] %s 下载失败: %s', idx, total_dates, trade_date, str(e))

                if not args.continue_on_error:
                    logging.error('已停止下载。使用 --continue-on-error 参数可在遇到错误时继续下载')
                    raise

        # 输出统计信息
        if total_dates > 1:
            logging.info('')
            logging.info('=' * 60)
            logging.info('下载统计:')
            logging.info('  总数: %d', total_dates)
            logging.info('  成功: %d', success_count)
            logging.info('  失败: %d', failed_count)
            if failed_dates:
                logging.info('  失败日期: %s', ', '.join(str(d) for d in failed_dates))
            logging.info('=' * 60)

    except Exception as e:
        logging.error('✗ 操作失败: %s', str(e))
        raise


if __name__ == "__main__":
    main()
