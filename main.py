import os 
import asyncio
import aiohttp
import time
from loguru import logger
from cloudscraper import create_scraper

# URL API dan Konstanta
DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": [
        "http://52.77.10.116/api/network/ping",
        "http://13.215.134.222/api/network/ping",
    ]
}

# Variabel global
account_info = {}
browser_id = {
    'ping_count': 0,
    'successful_pings': 0,
    'score': 0,
    'start_time': time.time(),
    'last_ping_status': 'Waiting...',
    'last_ping_time': None
}

# Fungsi utilitas
def load_token():
    """Memuat token dari file."""
    try:
        with open('token.txt', 'r') as file:
            return file.read().strip()
    except Exception as e:
        logger.error(f"Failed to load token: {e}")
        raise SystemExit("Exiting due to failure in loading token")

async def valid_resp(response):
    """Memvalidasi respons API."""
    try:
        resp_json = await response.json()
        if not resp_json or "code" not in resp_json or resp_json["code"] < 0:
            raise ValueError("Invalid response")
        return resp_json
    except Exception as e:
        logger.error(f"Failed to parse or validate response: {e}")
        raise ValueError("Invalid API Response")

async def fetch_proxies(api_url):
    """Mengambil daftar proxy dari API."""
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
    """Menyimpan proxy ke file."""
    try:
        #os.system(f"rm -rf {proxy_file}")
        with open(proxy_file, 'w') as file:
            file.writelines([proxy + '\n' for proxy in proxies])
        logger.info(f"Saved {len(proxies)} proxies to {proxy_file}.")
    except Exception as e:
        logger.error(f"Error saving proxies: {e}")

def load_proxies(proxy_file):
    """Memuat daftar proxies dari file."""
    try:
        with open(proxy_file, 'r') as file:
            proxies = [proxy.strip() for proxy in file if proxy.strip()]
            logger.info(f"Loaded {len(proxies)} proxies.")
            return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

async def call_api(url, data, proxy, token_info):
    """Melakukan panggilan API menggunakan aiohttp."""
    headers = {
        "Authorization": f"Bearer {token_info}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=data, headers=headers, proxy=proxy
            ) as response:
                response.raise_for_status()
                return await valid_resp(response)
    except Exception as e:
        logger.error(f"Error during API call to {url}: {e}")
        raise ValueError(f"Failed API call to {url}")

async def render_profile_info(proxy, token_info):
    """Mengambil informasi profil dan memulai ping."""
    global account_info
    try:
        #logger.info(f"Initializing session for proxy: {proxy}")
        response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token_info)
        account_info = response["data"]

        if account_info.get("uid"):
            logger.info(f"Session established for proxy: {proxy}. Starting ping.")
            await start_ping(proxy, token_info)
        else:
            logger.warning(f"No valid UID found for proxy: {proxy}. Skipping.")
    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e}")
        return proxy  # Mengembalikan proxy yang gagal

async def start_ping(proxy, token_info):
    """Memulai proses ping berkala."""
    try:
        while True:
            await ping(proxy, token_info)
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping for proxy {proxy}: {e}")

async def ping(proxy, token_info):
    """Mengirim ping ke URL tertentu."""
    for url in DOMAIN_API["PING"]:
        try:
            data = {
                "id": account_info.get("uid"),
                "browser_id": browser_id,
                "timestamp": int(time.time())
            }
            response = await call_api(url, data, proxy, token_info)
            if response["code"] == 0:
                logger.info(f"Ping successful via proxy {proxy} using URL {url}.")
        except Exception as e:
            logger.error(f"Ping failed via proxy {proxy} using URL {url}: {e}")

async def main():
    """Fungsi utama untuk menjalankan semua tugas."""
    token_info = load_token()
    proxy_api_url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text"
    isProxy = input("Auto proxy (y/n): ")

    if isProxy != "n":
        proxies = await fetch_proxies(proxy_api_url)
        save_proxies('proxies.txt', proxies)
    active_proxies = load_proxies('proxies.txt')
    tasks = [render_profile_info(proxy, token_info) for proxy in active_proxies]
    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
