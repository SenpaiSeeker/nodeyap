import asyncio
import aiohttp
import cloudscraper
import json
import time
from loguru import logger
import requests

PING_INTERVAL = 130
RETRIES = 60
MAX_PROXY_PER_TOKEN = 999  # Setiap token hanya bisa menggunakan maksimal 10 proxy

DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": [
        "http://13.215.134.222/api/network/ping",
        "http://52.77.10.116/api/network/ping"
    ]
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

# Fungsi untuk mendapatkan daftar proxy dari API
async def fetch_proxies(api_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    proxies = (await response.text()).strip().splitlines()
                    logger.info(f"Fetched {len(proxies)} proxies from API.")
                    return proxies
                else:
                    logger.warning(f"Failed to fetch proxies. Status code: {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")
        return []

# Fungsi untuk menyimpan proxy ke file
def save_proxies(proxy_file, proxies):
    try:
        with open(proxy_file, 'w') as file:
            file.writelines([proxy + '\n' for proxy in proxies])
        logger.info(f"Saved {len(proxies)} proxies to {proxy_file}.")
    except Exception as e:
        logger.error(f"Error saving proxies: {e}")

# Class untuk menyimpan informasi akun
class AccountInfo:
    def __init__(self, token, proxy_list):
        self.token = token
        self.proxy_list = proxy_list  # List of proxies assigned to this account
        self.active_proxies = proxy_list[:MAX_PROXY_PER_TOKEN]  # Keep only 10 proxies
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
        self.account_data = {}
        self.retries = 0
        self.last_ping_status = 'Waiting...'
        self.browser_id = {
            'ping_count': 0,
            'successful_pings': 0,
            'score': 0,
            'start_time': time.time(),
            'last_ping_time': None
        }

    def reset(self):
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
        self.account_data = {}
        self.retries = 0

    def remove_failed_proxy(self, failed_proxy):
        if failed_proxy in self.active_proxies:
            self.active_proxies.remove(failed_proxy)
            logger.info(f"Removed failed proxy {failed_proxy} from active proxies.")
            return True
        return False

    def add_new_proxy(self, new_proxy):
        if len(self.active_proxies) < MAX_PROXY_PER_TOKEN:
            self.active_proxies.append(new_proxy)
            logger.info(f"Added new proxy {new_proxy} to active proxies.")
            return True
        return False

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

async def load_tokens():
    try:
        with open('token.txt', 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")

async def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

# Fungsi untuk memanggil API
async def call_api(url, data, account_info):
    headers = {
        "Authorization": f"Bearer {account_info.token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    try:
        proxy = account_info.active_proxies[0] if account_info.active_proxies else None
        proxy_config = {
            "http": proxy,
            "https": proxy
        } if proxy else None

        response = scraper.post(url, json=data, headers=headers, proxies=proxy_config, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error during API call for token {account_info.token} with proxy {proxy}: {e}")
        raise ValueError(f"Failed API call to {url}")

    return response.json()

# Fungsi utama untuk memproses akun
async def process_account(account_info):
    try:
        await render_profile_info(account_info)
    except Exception as e:
        logger.error(f"Error processing account {account_info.token}: {e}")

# Fungsi untuk memulai profil
async def render_profile_info(account_info):
    try:
        response = await call_api(DOMAIN_API["SESSION"], {}, account_info)
        if response.get("code") == 0:
            account_info.account_data = response["data"]
            if account_info.account_data.get("uid"):
                await start_ping(account_info)
            else:
                handle_logout(account_info)
        else:
            handle_logout(account_info)
    except Exception as e:
        logger.error(f"Error in render_profile_info: {e}")

# Fungsi utama
async def main():
    isProxy = input("Auto proxy (y/n): ")
    if isProxy.lower() != "n":
        proxy_api_url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text"
        proxies = await fetch_proxies(proxy_api_url)
        save_proxies('proxies.txt', proxies)

    tokens = await load_tokens()
    all_proxies = await load_proxies('proxies.txt')

    tasks = []
    for token in tokens:
        proxies_for_token = all_proxies[:MAX_PROXY_PER_TOKEN]
        account_info = AccountInfo(token, proxies_for_token)
        tasks.append(process_account(account_info))

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
