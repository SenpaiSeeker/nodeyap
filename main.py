import asyncio
import aiohttp
import json
import time
import uuid
from loguru import logger

PING_INTERVAL = 130
RETRIES = 60
MAX_PROXY_PER_TOKEN = 10  # Setiap token hanya bisa menggunakan maksimal 10 proxy

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

async def fetch_proxies(api_url):
    """Fetch proxies asynchronously from a URL."""
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


def save_proxies(proxy_file, proxies):
    """Save proxies to a file."""
    try:
        with open(proxy_file, 'w') as file:
            file.writelines([proxy + '\n' for proxy in proxies])
        logger.info(f"Saved {len(proxies)} proxies to {proxy_file}.")
    except Exception as e:
        logger.error(f"Error saving proxies: {e}")


class AccountInfo:
    def __init__(self, token, proxy_list):
        self.token = token
        self.proxy_list = proxy_list
        self.active_proxies = proxy_list[:MAX_PROXY_PER_TOKEN]
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


async def call_api(session, url, data, account_info, proxy):
    """Make an API call with the given proxy."""
    headers = {
        "Authorization": f"Bearer {account_info.token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://app.nodepay.ai/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://app.nodepay.ai",
    }

    proxy_url = f"http://{proxy}" if proxy else None
    try:
        async with session.post(
            url, json=data, headers=headers, proxy=proxy_url, timeout=10
        ) as response:
            response.raise_for_status()
            return await response.json()
    except Exception as e:
        logger.error(f"Error during API call for token {account_info.token} with proxy {proxy}: {e}")
        raise


async def render_profile_info(session, account_info):
    """Fetch profile info and start the ping process."""
    try:
        response = await call_api(session, DOMAIN_API["SESSION"], {}, account_info, account_info.active_proxies[0])
        if response.get("code") == 0:
            account_info.account_data = response["data"]
            if account_info.account_data.get("uid"):
                await start_ping(session, account_info)
            else:
                handle_logout(account_info)
        else:
            handle_logout(account_info)
    except Exception as e:
        logger.error(f"Error in render_profile_info for token {account_info.token}: {e}")


async def start_ping(session, account_info):
    """Ping continuously with the given account."""
    try:
        logger.info(f"Starting ping for token {account_info.token}")
        await ping(session, account_info)
        while True:
            await asyncio.sleep(PING_INTERVAL)
            await ping(session, account_info)
    except asyncio.CancelledError:
        logger.info(f"Ping task cancelled for token {account_info.token}")
    except Exception as e:
        logger.error(f"Error in start_ping for token {account_info.token}: {e}")


async def ping(session, account_info):
    """Ping all available endpoints."""
    for url in DOMAIN_API["PING"]:
        try:
            data = {
                "id": account_info.account_data.get("uid"),
                "browser_id": account_info.browser_id,
                "timestamp": int(time.time())
            }
            response = await call_api(session, url, data, account_info, account_info.active_proxies[0])
            if response["code"] == 0:
                logger.info(f"Token {account_info.token}: Ping successful.")
                account_info.status_connect = CONNECTION_STATES["CONNECTED"]
                return
            else:
                logger.warning(f"Token {account_info.token}: Ping failed. Response: {response}")
        except Exception as e:
            logger.error(f"Token {account_info.token}: Ping error: {e}")
    account_info.status_connect = CONNECTION_STATES["DISCONNECTED"]


def handle_logout(account_info):
    """Handle logout logic."""
    account_info.reset()
    logger.info(f"Logged out for token {account_info.token}")


async def main():
    isProxy = input("Auto proxy (y/n): ")
    if isProxy != "n":
        proxy_api_url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text"
        proxies = await fetch_proxies(proxy_api_url)
        save_proxies('proxies.txt', proxies)

    tokens = []
    try:
        with open("token.txt", "r") as f:
            tokens = f.read().splitlines()
    except Exception as e:
        logger.error("Failed to load tokens: {e}")
        return

    proxies = []
    try:
        with open("proxies.txt", "r") as f:
            proxies = f.read().splitlines()
    except Exception as e:
        logger.error("Failed to load proxies: {e}")
        return

    async with aiohttp.ClientSession() as session:
        tasks = []
        for token in tokens:
            account_info = AccountInfo(token, proxies[:MAX_PROXY_PER_TOKEN])
            tasks.append(render_profile_info(session, account_info))
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
