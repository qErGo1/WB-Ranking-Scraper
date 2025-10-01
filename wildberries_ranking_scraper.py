from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
import time
import random
import re
import sys
import json

MAIN_PRODUCTS_SELECTOR = "div.product-card-list > article.product-card"
RECOMMENDED_SECTION_SELECTOR = "section.j-b-recommended-goods-wrapper"
BRAND_SELECTOR = ".product-card__brand"
NAME_SELECTOR = ".product-card__name"
PRICE_SELECTOR = ".price__lower-price"
PAGINATION_SELECTOR = ".pagination-item"
NEXT_PAGE_SELECTOR = ".pagination-next"

SCROLL_PAUSE_MIN = 1.5
SCROLL_PAUSE_MAX = 3.0
MAX_SCROLLS = 60
SCROLL_INCREMENT = 600
LOAD_TIMEOUT = 40
INITIAL_LOAD_WAIT = 5

ROW_TOLERANCE = 10

def start_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def human_like_scroll(driver, scroll_count):
    if scroll_count < 3:
        scroll_pause = random.uniform(SCROLL_PAUSE_MIN * 1.5, SCROLL_PAUSE_MAX * 1.5)
    else:
        scroll_pause = random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX)
    
    time.sleep(scroll_pause)
    current_position = driver.execute_script("return window.pageYOffset;")
    window_height = driver.execute_script("return window.innerHeight;")
    
    if scroll_count % 3 == 0:
        scroll_to = current_position + window_height
    else:
        scroll_to = current_position + random.randint(SCROLL_INCREMENT, window_height)
    
    driver.execute_script(f"window.scrollTo(0, {scroll_to});")
    return scroll_pause

def is_loading_finished(driver, previous_count, current_count, stable_count, scroll_count):
    if current_count == previous_count:
        return stable_count + 1
    if current_count >= 150:
        return stable_count + 1
    if scroll_count > 40:
        return 3
    return 0

def load_main_products(driver, url, is_first_page=False):
    driver.get(url)
    wait = WebDriverWait(driver, LOAD_TIMEOUT)
    
    if is_first_page:
        time.sleep(INITIAL_LOAD_WAIT)
    
    try:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, MAIN_PRODUCTS_SELECTOR)))
        wait.until(EC.visibility_of_any_elements_located((By.CSS_SELECTOR, MAIN_PRODUCTS_SELECTOR)))
    except TimeoutException:
        print(json.dumps({"type": "warning", "message": "No main products found within timeout period. Continuing anyway."}), flush=True)

    print(json.dumps({"type": "info", "message": "Page loaded. Scrolling to load all main products..."}), flush=True)

    last_count = 0
    stable_count = 0
    max_stable_checks = 2

    for i in range(MAX_SCROLLS):
        pause_time = human_like_scroll(driver, i)
        time.sleep(0.5)
        try:
            main_products = driver.find_elements(By.CSS_SELECTOR, MAIN_PRODUCTS_SELECTOR)
            current_count = len(main_products)
            print(json.dumps({
                "type": "scroll_progress",
                "scroll": i+1,
                "total_scrolls": MAX_SCROLLS,
                "product_count": current_count,
                "pause_time": round(pause_time, 1)
            }), flush=True)
            
            stable_count = is_loading_finished(driver, last_count, current_count, stable_count, i)
            if stable_count >= max_stable_checks:
                print(json.dumps({
                    "type": "info",
                    "message": f"Loading stable for {stable_count} checks. Stopping scroll."
                }), flush=True)
                break
            last_count = current_count
        except Exception as e:
            print(json.dumps({
                "type": "error",
                "message": f"Error during scroll {i+1}: {str(e)}"
            }), flush=True)
            continue

    time.sleep(2)
    try:
        main_products = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, MAIN_PRODUCTS_SELECTOR)))
        print(json.dumps({
            "type": "info",
            "message": f"Final main product count: {len(main_products)}"
        }), flush=True)
        return main_products
    except TimeoutException:
        print(json.dumps({
            "type": "warning",
            "message": "Could not locate main products after final wait. Returning what we can get."
        }), flush=True)
        try:
            main_products = driver.find_elements(By.CSS_SELECTOR, MAIN_PRODUCTS_SELECTOR)
            print(json.dumps({
                "type": "info",
                "message": f"Got {len(main_products)} products despite timeout"
            }), flush=True)
            return main_products
        except:
            return []

def sort_products_grid(products):
    positioned = []
    for idx, p in enumerate(products):
        try:
            loc = p.location
            positioned.append((p, loc['y'], loc['x']))
        except:
            continue
    positioned.sort(key=lambda item: (round(item[1] / ROW_TOLERANCE), item[2]))
    return [p for p, _, _ in positioned]

def parse_price(price_text):
    try:
        numeric_price = int(''.join(filter(str.isdigit, price_text)))
        return numeric_price
    except:
        return None

def parse_product(card):
    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:
        try:
            brand = card.find_element(By.CSS_SELECTOR, BRAND_SELECTOR).text.strip()
            name = card.find_element(By.CSS_SELECTOR, NAME_SELECTOR).text.strip()
            try:
                price_elem = card.find_element(By.CSS_SELECTOR, PRICE_SELECTOR)
                price = price_elem.text.strip() if price_elem else "N/A"
            except NoSuchElementException:
                price = "N/A"
            price_numeric = parse_price(price)
            return brand, name, price, price_numeric
        except StaleElementReferenceException:
            attempts += 1
            time.sleep(0.8)
        except NoSuchElementException:
            return "", "", "N/A", None
        except Exception as e:
            print(json.dumps({
                "type": "error",
                "message": f"Unexpected error parsing product: {str(e)}"
            }), flush=True)
            return "", "", "N/A", None
    return "", "", "N/A", None

def go_to_next_page(driver, current_page):
    try:
        next_button = driver.find_element(By.CSS_SELECTOR, NEXT_PAGE_SELECTOR)
        if next_button.is_enabled():
            next_button.click()
            print(json.dumps({
                "type": "navigation",
                "message": f"Navigating to page {current_page + 1}...",
                "page": current_page + 1
            }), flush=True)
            WebDriverWait(driver, LOAD_TIMEOUT).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, MAIN_PRODUCTS_SELECTOR))
            )
            time.sleep(2)
            return True
    except Exception as e:
        print(json.dumps({
            "type": "warning",
            "message": f"Could not navigate to next page using button: {str(e)}"
        }), flush=True)

    try:
        current_url = driver.current_url
        if 'page=' in current_url:
            next_url = re.sub(r'page=(\d+)', f'page={current_page + 1}', current_url)
        else:
            separator = '&' if '?' in current_url else '?'
            next_url = f"{current_url}{separator}page={current_page + 1}"
        driver.get(next_url)
        print(json.dumps({
            "type": "navigation",
            "message": f"Navigating to page {current_page + 1} via URL...",
            "page": current_page + 1
        }), flush=True)
        WebDriverWait(driver, LOAD_TIMEOUT).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, MAIN_PRODUCTS_SELECTOR))
        )
        time.sleep(2)
        return True
    except Exception as e:
        print(json.dumps({
            "type": "error",
            "message": f"Could not navigate to next page via URL: {str(e)}"
        }), flush=True)
        return False

def clean_text(text):
    if not isinstance(text, str):
        return str(text)
    replacements = {'✓': '[CHECK]', '₽': 'RUB', '\u20bd': 'RUB', '\u2713': '[CHECK]'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            "type": "error",
            "message": "Usage: python wildberries_scraper.py <search_url> <target_brand> <start_page> <end_page>"
        }), flush=True)
        sys.exit(1)

    BASE_URL = sys.argv[1]
    TARGET_BRAND = sys.argv[2]
    start_page = int(sys.argv[3])
    end_page = int(sys.argv[4])
    
    global MAX_PAGES
    MAX_PAGES = end_page - start_page + 1

    print(json.dumps({
        "type": "config",
        "target_brand": clean_text(TARGET_BRAND),
        "search_url": BASE_URL,
        "start_page": start_page,
        "end_page": end_page,
        "pages_to_process": MAX_PAGES
    }), flush=True)

    driver = start_driver()
    all_found_products = []
    total_products_analyzed = 0
    current_page = start_page
    global_position = 0

    try:
        page_count = 0
        while current_page <= end_page:  
            page_count += 1
            is_first_page = (page_count == 1)
            
            print(json.dumps({
                "type": "page_start",
                "page": current_page,
                "end_page": end_page,
                "is_first_page": is_first_page
            }), flush=True)

            page_url = BASE_URL
            if current_page > 1:
                separator = '&' if '?' in BASE_URL else '?'
                page_url = f"{BASE_URL}{separator}page={current_page}"

            main_products = load_main_products(driver, page_url, is_first_page)
            total_products_analyzed += len(main_products)
            print(json.dumps({
                "type": "page_analysis",
                "page": current_page,
                "product_count": len(main_products)
            }), flush=True)

            page_found_products = []
            sorted_main_products = sort_products_grid(main_products)

            for index, card in enumerate(sorted_main_products):
                global_position += 1
                try:
                    brand, name, price, price_numeric = parse_product(card)
                    if brand and brand.lower() == TARGET_BRAND.lower():
                        product_info = {
                            "global_position": global_position,
                            "brand": clean_text(brand),
                            "name": clean_text(name),
                            "price_text": clean_text(price),
                            "price_numeric": price_numeric,
                            "page": current_page
                        }
                        page_found_products.append(product_info)
                        
                        print(json.dumps({
                            "type": "product_found",
                            "product": product_info
                        }), flush=True)
                        
                    if (index + 1) % 15 == 0:
                        print(json.dumps({
                            "type": "progress",
                            "processed": index + 1,
                            "total": len(main_products),
                            "page": current_page
                        }), flush=True)
                except Exception as e:
                    print(json.dumps({
                        "type": "error",
                        "message": f"Error processing product {index + 1} on page {current_page}: {str(e)}"
                    }), flush=True)
                    continue

            all_found_products.extend(page_found_products)

            print(json.dumps({
                "type": "page_complete",
                "page": current_page,
                "products_found": len(page_found_products),
                "products_on_page": len(main_products)
            }), flush=True)

            if current_page < end_page: 
                if not go_to_next_page(driver, current_page):
                    print(json.dumps({
                        "type": "error",
                        "message": "Failed to navigate to next page. Ending pagination."
                    }), flush=True)
                    break
                current_page += 1
                wait_time = random.uniform(3.0, 5.0)
                print(json.dumps({
                    "type": "info",
                    "message": f"Waiting {wait_time:.1f} seconds before next page..."
                }), flush=True)
                time.sleep(wait_time)
            else:
                break

        print(json.dumps({
            "type": "summary",
            "target_brand": clean_text(TARGET_BRAND),
            "pages_processed": current_page - start_page + 1,
            "total_products_analyzed": total_products_analyzed,
            "target_brand_products_found": len(all_found_products)
        }), flush=True)

        if all_found_products:
            print(json.dumps({
                "type": "results_header"
            }), flush=True)
            for product in all_found_products:
                print(json.dumps({
                    "type": "result_item",
                    "product": product
                }), flush=True)
        else:
            print(json.dumps({
                "type": "no_results",
                "message": f"No products found for brand '{clean_text(TARGET_BRAND)}' across {current_page - start_page + 1} pages."
            }), flush=True)

    except Exception as e:
        print(json.dumps({
            "type": "critical_error",
            "message": f"Critical error during execution: {str(e)}"
        }), flush=True)
        import traceback
        traceback.print_exc()

    finally:
        time.sleep(1)
        driver.quit()
        print(json.dumps({
            "type": "info",
            "message": "Driver closed."
        }), flush=True)

if __name__ == "__main__":
    main()