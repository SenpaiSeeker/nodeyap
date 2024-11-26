import os
import asyncio
import aiohttp
import time
from loguru import logger
from fake_useragent import UserAgent

user_agent = UserAgent(os='windows', platforms='pc', browsers='chrome')
DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": [
        "http://52.77.10.116/api/network/ping",
        "http://13.215.134.222/api/network/ping"
    ]
}


proxies_list = []
account_info = {}
browser_id = {
    'ping_count': 0,
    'successful_pings': 0,
    'score': 0,
    'start_time': time.time(),
    'last_ping_status': 'Waiting...',
    'last_ping_time': None
}

def load_token():
    try:
        with open('token.txt', 'r') as file:
            return file.read().strip()
    except Exception as e:
        logger.error(f"Failed to load token: {e}")
        raise SystemExit("Exiting due to failure in loading token")

async def valid_resp(response):
    try:
        resp_json = await response.json()
        if not resp_json or "code" not in resp_json or resp_json["code"] < 0:
            raise ValueError("Invalid response")
        return resp_json
    except Exception as e:
        logger.error(f"Failed to parse or validate response: {e}")
        raise ValueError("Invalid API Response")

async def fetch_proxies(api_url):
    list_proxies = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    proxies = await response.text()).strip()
                    for x in proxies:
                        proxy = f"{x['data'][0]['protocols'][0]}://{x['data'][0]['ip']}:{x['data'][0]['port']}"
                        list_proxies.append(proxy)
                    logger.info(f"Fetched {len(proxies_list)} proxies from API.")
                    return proxies
                else:
                    logger.warning(f"Failed to fetch proxies. Status code: {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")
        return []

def save_proxies(proxy_file, proxies):
    try:
        with open(proxy_file, 'w') as file:
            file.writelines([proxy + '\n' for proxy in proxies])
        logger.info(f"Saved {len(proxies)} proxies to {proxy_file}.")
    except Exception as e:
        logger.error(f"Error saving proxies: {e}")

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = [proxy.strip() for proxy in file if proxy.strip()]
            logger.info(f"Loaded {len(proxies)} proxies.")
            time.sleep(5)
            return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

async def call_api(url, data, proxy, token_info):
    headers = {
        "Authorization": f"Bearer {token_info}",
        "User-Agent": user_agent.random,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    try:
        if proxy in proxies_list:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=data, headers=headers, proxy=proxy
                ) as response:
                    response.raise_for_status()
                    return await valid_resp(response)
    except Exception as e:
        logger.error(f"Error during API call to {url}: {e}")
        raise ValueError(f"Failed API call to {url}")
        proxies_list.remove(proxy)

async def render_profile_info(proxy, token_info):
    global account_info
    try:
        if proxy in proxies_list:
            response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token_info)
            account_info = response["data"]

            if account_info.get("uid"):
                logger.debug(f"Session established for proxy: {proxy}. Starting ping.")
                await start_ping(proxy, token_info)
            else:
                logger.warning(f"No valid UID found for proxy: {proxy}. Skipping.")
                proxies_list.remove(proxy)
    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e}")
        proxies_list.remove(proxy)

async def start_ping(proxy, token_info):
    try:
        if proxy in proxies_list:
            await ping(proxy, token_info)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} was cancelled")
        proxies_list.remove(proxy)
    except Exception as e:
        logger.error(f"Error in start_ping for proxy {proxy}: {e}")
        proxies_list.remove(proxy)

async def ping(proxy, token_info):
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
    token_info = load_token()
    isProxy = input("Auto proxy (y/n): ")
    while True:
        if isProxy != "n":
            proxy_api_url = "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc"
            proxies = await fetch_proxies(proxy_api_url)
            save_proxies('proxies.txt', proxies)

        active_proxies = load_proxies('proxies.txt')
        proxies_list.extend(active_proxies)
        tasks = [render_profile_info(proxy, token_info) for proxy in proxies_list]
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
