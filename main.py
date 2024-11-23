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
        "http://13.215.134.222/api/network/ping",
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

async def call_api(url, data, proxy, token_info):
    headers = {
        "Authorization": f"Bearer {token_info}",
        "User-Agent": user_agent.random,
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
    global account_info
    try:
        response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token_info)
        account_info = response["data"]

        if account_info.get("uid"):
            logger.debug(f"Session established for proxy: {proxy}. Starting ping.")
            await start_ping(proxy, token_info)
        else:
            proxies_list.remove(proxy)
            logger.warning(f"No valid UID found for proxy: {proxy}. Skipping proxies_count {len(proxies_list)}.")
    except Exception as e:
        proxies_list.remove(proxy)
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e} proxies_count {len(proxies_list)}.")

async def start_ping(proxy, token_info):
    try:
        while True:
            await ping(proxy, token_info)
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        proxies_list.remove(proxy)
        logger.error(f"Error in start_ping for proxy {proxy}: {e} proxies_count {len(proxies_list)}.")

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
                logger.info(f"Ping successful via proxy {proxy} using URL {url} proxies_count {len(proxies_list)}.")
        except Exception as e:
            proxies_list.remove(proxy)
            logger.error(f"Ping failed via proxy {proxy} proxies_count {len(proxies_list)}. using URL {url}: {e}")

async def main():
    token_info = load_token()
    proxy_api_url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text"
   
    proxies = await fetch_proxies(proxy_api_url)
    proxies_list.extend(proxies)
    
    tasks = [render_profile_info(proxy, token_info) for proxy in proxies_list]
    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
