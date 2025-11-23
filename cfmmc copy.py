import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Tuple
from urllib.parse import urljoin

import ddddocr
import requests

logging.basicConfig(level=logging.INFO)


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

    def download_daily_report(self, trade_date: datetime, by_type: str = "trade") -> Path:
        self._ensure_logged_in()
        token = self._fetch_customer_token()
        self._set_parameter(trade_date, by_type, token)
        resp = self.session.get(self.DOWNLOAD_URL, timeout=30)
        resp.raise_for_status()
        file_path = Path(f"cfmmc_{trade_date:%Y%m%d}.xls")
        file_path.write_bytes(resp.content)
        logging.info("Daily report saved to %s", file_path)
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
    user = "007730804792"
    password = "xuhong0413"
    trade_date = date(2025, 11, 21)
    client = CfmmcClient(user_id=user, password=password)
    client.login()
    client.download_daily_report(trade_date)


if __name__ == "__main__":
    main()
