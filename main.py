import asyncio
import requests
import cloudscraper
import time
from loguru import logger

# URL API dan Konstanta
DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": [
        "http://13.215.134.222/api/network/ping",
        "http://52.77.10.116/api/network/ping"
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

def valid_resp(resp):
    """Memvalidasi respons API."""
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

# Inisialisasi token dan scraper
token_info = load_token()
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

# Fungsi API
def call_api(url, data, proxy):
    """Melakukan panggilan API."""
    headers = {
        "Authorization": f"Bearer {token_info}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    try:
        response = scraper.post(url, json=data, headers=headers, proxies={"http": proxy, "https": proxy})
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error during API call to {url}: {e}")
        raise ValueError(f"Failed API call to {url}")

    return valid_resp(response.json())

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

def fetch_and_save_proxies(proxy_file):
    """Mengambil proxy dari API dan menyimpannya ke file."""
    api_url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text"
    
    try:
        response = requests.get(api_url, stream=True)

        if response.status_code == 200:
            proxies = response.text.strip().splitlines()

            if proxies:
                with open(proxy_file, 'w') as file:
                    file.writelines([proxy + '\n' for proxy in proxies])
                logger.info(f"Fetched and saved {len(proxies)} proxies to {proxy_file}.")
            else:
                logger.warning("No proxies found from the API.")
        else:
            logger.warning(f"Failed to fetch proxies. Status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")

# Fungsi utama
async def render_profile_info(proxy):
    """Mengambil informasi profil dan memulai ping."""
    global account_info
    try:
        logger.info(f"Initializing session for proxy: {proxy}")
        response = call_api(DOMAIN_API["SESSION"], {}, proxy)
        valid_resp(response)
        account_info = response["data"]

        if account_info.get("uid"):
            logger.info(f"Session established for proxy: {proxy}. Starting ping.")
            await start_ping(proxy)
        else:
            logger.warning(f"No valid UID found for proxy: {proxy}. Skipping.")
    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e}")
        return proxy  # Mengembalikan proxy yang gagal

async def start_ping(proxy):
    """Memulai proses ping berkala."""
    try:
        while True:
            await ping(proxy)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping for proxy {proxy}: {e}")

async def ping(proxy):
    """Mengirim ping ke URL tertentu."""
    for url in DOMAIN_API["PING"]:
        try:
            data = {
                "id": account_info.get("uid"),
                "browser_id": browser_id,
                "timestamp": int(time.time())
            }
            response = call_api(url, data, proxy)
            if response["code"] == 0:
                logger.info(f"Ping successful via proxy {proxy} using URL {url}.")
        except Exception as e:
            logger.error(f"Ping failed via proxy {proxy} using URL {url}: {e}")
    logger.warning(f"All ping attempts failed for proxy {proxy}.")

async def main():
    """Fungsi utama untuk menjalankan semua tugas."""
    proxy_file = 'proxies.txt'

    while True:
        fetch_and_save_proxies(proxy_file)
        active_proxies = load_proxies(proxy_file)

        taks = [asyncio.create_task(render_profile_info(proxy)) for proxy in active_proxies]
        await asyncio.gather(*taks)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
