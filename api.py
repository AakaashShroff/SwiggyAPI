import os
import time
import logging
import traceback
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup

from flask import Flask, request, jsonify

from fuzzywuzzy import fuzz, process

app = Flask(__name__)

PHONE_NUMBER = '1234567890'
SWIGGY_URL = 'https://www.swiggy.com'
LOGIN_TIMEOUT = 60
POLL_INTERVAL = 2
ADDRESS_TO_SELECT = 'Home'

restaurant_dict = {
    "Beijing Bites": ["Chicken Schezwan Fried rice", "Honey Chilli Chicken"],
    "Quattro - The Leela Bhartiya City Bengaluru": ["Paneer Tikka", "Chicken Tikka Pizza"],
    "Chung Wah": ["Spring Rolls", "Chicken Lung Fung Soup"],
    "Pizza Hut": ["Margherita Pizza"],
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

driver = None

def is_logged_in(driver):
    try:
        sign_in_xpath = "//a[text()='Sign in']"
        driver.find_element(By.XPATH, sign_in_xpath)
        logger.info("'Sign in' button is present. User is not logged in.")
        return False
    except NoSuchElementException:
        logger.info("'Sign in' button not found. User is logged in.")
        return True

def manual_login(driver):
    logger.info("Waiting for manual login to complete...")
    elapsed_time = 0
    while elapsed_time < LOGIN_TIMEOUT:
        if is_logged_in(driver):
            logger.info("Manual login detected.")
            return True
        time.sleep(POLL_INTERVAL)
        elapsed_time += POLL_INTERVAL
        logger.debug(f"Waited {elapsed_time} seconds for login.")
    logger.warning("Login timeout reached. User is not logged in.")
    return False

def perform_login(driver):
    try:
        sign_in_xpath = "//a[text()='Sign in']"
        sign_in_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, sign_in_xpath))
        )
        sign_in_button.click()
        logger.info("'Sign in' button clicked.")
        phone_input_xpath = "//input[@id='mobile']"
        phone_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, phone_input_xpath))
        )
        phone_input.clear()
        phone_input.send_keys(PHONE_NUMBER)
        logger.info(f"Entered phone number: {PHONE_NUMBER}")
        submit_button_xpath = "//button[span/text()='CONTINUE']"
        try:
            submit_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
            )
            submit_button.click()
            logger.info("'CONTINUE' button clicked.")
        except TimeoutException:
            logger.warning("'CONTINUE' button not found. Proceeding to wait for manual login.")
        if manual_login(driver):
            logger.info("Login successful.")
            return True
        else:
            logger.error("Login was not successful within the timeout period.")
            return False
    except Exception as e:
        logger.error(f"An error occurred during login: {e}")
        driver.save_screenshot("login_error.png")
        logger.info("Screenshot saved as login_error.png.")
        return False

def select_address(driver):
    try:
        location_input = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.ID, "location"))
        )
        logger.info("Location input found.")
        dropdown_div = location_input.find_element(By.XPATH, "following::div[@style='line-height:0'][1]")
        logger.info("Dropdown div found.")
        dropdown_div.click()
        logger.info("Dropdown arrow clicked.")
        addresses_container_xpath = "//div[contains(text(), 'Saved addresses')]"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, addresses_container_xpath))
        )
        logger.info("Address dropdown is visible.")
        address_xpath = f"//span[contains(text(), '{ADDRESS_TO_SELECT}')]"
        address_element = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, address_xpath))
        )
        address_element.click()
        logger.info(f"Address '{ADDRESS_TO_SELECT}' selected.")
    except Exception as e:
        logger.error("An error occurred while selecting the address:")
        logger.error(traceback.format_exc())
        driver.save_screenshot("address_selection_error.png")
        logger.info("Screenshot saved as address_selection_error.png.")
        raise e
def search_restaurant(driver, dish):
    try:
        search_div_xpath = "//div[contains(text(), 'Search for restaurant, item or more')]"
        search_div = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, search_div_xpath))
        )
        search_div.click()
        logger.info("Search input div clicked.")
        WebDriverWait(driver, 5).until(
            EC.url_contains("/search")
        )
        logger.info("Navigated to search page.")
        search_input_xpath = "//input[@placeholder='Search for restaurants and food']"
        search_input = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, search_input_xpath))
        )
        logger.info("Search input field found.")
        logger.info(f"User entered dish: {dish}")

        all_dishes = []
        for restaurant, dishes in restaurant_dict.items():
            for dish_name in dishes:
                all_dishes.append((dish_name, restaurant))

        dish_names = [d[0] for d in all_dishes]
        matches = process.extractBests(dish, dish_names, scorer=fuzz.token_sort_ratio, score_cutoff=90)
        if not matches:
            logger.error(f"Dish '{dish}' not found in restaurant dictionary.")
            restart_selenium()
            raise Exception(f"Sorry, the dish '{dish}' is not available. Please suggest another dish.")

        best_match = matches[0][0]
        logger.info(f"Best matched dish: {best_match}")
        for dish_name, restaurant in all_dishes:
            if dish_name == best_match:
                restaurant_name = restaurant
                break

        logger.info(f"Found restaurant '{restaurant_name}' for dish '{dish}'.")
        search_input.clear()
        search_input.send_keys(restaurant_name)
        logger.info(f"Entered restaurant name '{restaurant_name}' into search input.")
        autosuggest_xpath = "//div[contains(@class, '_29yzU')]"
        try:
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, autosuggest_xpath))
            )
            logger.info("Autosuggest dropdown is visible.")
            first_suggestion_xpath = "//div[contains(@class, '_29yzU')]//button[@data-testid='autosuggest-item'][1]"
            first_suggestion = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, first_suggestion_xpath))
            )
            first_suggestion.click()
            logger.info("First suggestion clicked.")
        except TimeoutException:
            logger.error(f"Restaurant '{restaurant_name}' is unavailable right now.")
            restart_selenium()
            raise Exception(f"Restaurant '{restaurant_name}' is unavailable right now. Please suggest another dish.")

        results_container_xpath = "//div[contains(@class, 'Search_widgetsV2__27BBR')]"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, results_container_xpath))
        )
        logger.info("Search results are displayed.")
        first_result_xpath = "//div[contains(@class, 'Search_widgetsV2__27BBR')]//a[@data-testid='resturant-card-anchor-container'][1]"
        first_result = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, first_result_xpath))
        )
        first_result.click()
        logger.info("First restaurant item clicked.")
        logger.info("Restaurant page loaded.")
        add_dish_to_cart(driver, best_match)
    except Exception as e:
        logger.error("An error occurred during the search process:")
        logger.error(traceback.format_exc())
        driver.save_screenshot("search_error.png")
        logger.info("Screenshot saved as search_error.png.")
        raise e

def add_dish_to_cart(driver, dish_name):
    try:
        search_button_xpath = "//button[.//div[text()='Search for dishes']]"
        search_button = WebDriverWait(driver, 7).until(
            EC.presence_of_element_located((By.XPATH, search_button_xpath))
        )
        logger.info("Search button found.")
        driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
        time.sleep(0.5)
        try:
            search_button.click()
            logger.info("Clicked the search button on the restaurant page.")
        except Exception as e:
            logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
            driver.execute_script("arguments[0].click();", search_button)
            logger.info("Clicked the search button using JavaScript.")
        search_input_xpath = "//input[@data-cy='menu-search-header']"
        search_input = WebDriverWait(driver, 7).until(
            EC.visibility_of_element_located((By.XPATH, search_input_xpath))
        )
        logger.info("Dish search input field found.")
        search_input.clear()
        search_input.send_keys(dish_name)
        logger.info(f"Entered dish name '{dish_name}' into search input.")
        dish_list_xpath = "//div[@data-testid='normal-dish-item']"
        WebDriverWait(driver, 7).until(
            EC.visibility_of_element_located((By.XPATH, dish_list_xpath))
        )
        logger.info("Dish list is displayed.")
        first_dish_xpath = f"({dish_list_xpath})[1]"
        first_dish = driver.find_element(By.XPATH, first_dish_xpath)
        logger.info("First dish item found.")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_dish)
        time.sleep(0.5)
        minus_button_xpath = ".//button[contains(@class, 'add-button-left-container')]//div[text()='−']"
        add_button_xpath = ".//button[contains(@class, 'add-button-center-container')]"

        def remove_existing_quantities():
            try:
                minus_button = first_dish.find_element(By.XPATH, minus_button_xpath)
                logger.info("Minus button found. Removing existing quantities.")
                max_attempts = 5
                attempts = 0
                while attempts < max_attempts:
                    minus_button.click()
                    logger.info("Clicked the minus button to remove one item.")
                    time.sleep(0.5)
                    try:
                        first_dish.find_element(By.XPATH, add_button_xpath)
                        logger.info("'Add' button is now present.")
                        break
                    except:
                        minus_button = first_dish.find_element(By.XPATH, minus_button_xpath)
                    attempts += 1
                else:
                    logger.warning("Minus button still present after maximum attempts.")
            except:
                logger.info("Minus button not present. No existing quantities to remove.")

        remove_existing_quantities()
        add_button = first_dish.find_element(By.XPATH, add_button_xpath)
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, add_button_xpath))
        )

        def click_add_button():
            try:
                add_button.click()
                logger.info("Add button for the first dish clicked.")
                return True
            except Exception as e:
                logger.warning(f"Normal click on add button failed: {e}. Trying ActionChains click.")
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(add_button).click().perform()
                    logger.info("Clicked the add button using ActionChains.")
                    return True
                except Exception as e:
                    logger.warning(f"ActionChains click failed: {e}. Trying JavaScript click.")
                    try:
                        driver.execute_script("arguments[0].click();", add_button)
                        logger.info("Clicked the add button using JavaScript.")
                        return True
                    except Exception as e:
                        logger.error(f"All methods failed to click the add button: {e}.")
                        return False

        clicked = click_add_button()

        def handle_popups():
            max_attempts = 3
            attempts = 0
            while attempts < max_attempts:
                popups_handled = False

                try:
                    continue_button_xpath = "//button[@data-testid='menu-customize-continue-button']"
                    continue_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, continue_button_xpath))
                    )
                    logger.info("'Continue' pop-up appeared.")
                    driver.execute_script("arguments[0].scrollIntoView(true);", continue_button)
                    time.sleep(0.5)
                    try:
                        continue_button.click()
                        logger.info("Clicked the 'Continue' button on the pop-up.")
                    except Exception as e:
                        logger.warning(f"Click on 'Continue' button failed: {e}. Trying JavaScript click.")
                        driver.execute_script("arguments[0].click();", continue_button)
                        logger.info("Clicked the 'Continue' button using JavaScript.")
                    popups_handled = True
                except TimeoutException:
                    logger.info("No 'Continue' pop-up appeared.")

                try:
                    popup_button_xpath = "//button[contains(@class, 'hoJL8') and text()='Yes, start afresh']"
                    popup_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, popup_button_xpath))
                    )
                    logger.info("'Yes, start afresh' pop-up appeared.")
                    driver.execute_script("arguments[0].scrollIntoView(true);", popup_button)
                    time.sleep(0.5)
                    try:
                        popup_button.click()
                        logger.info("Clicked 'Yes, start afresh' button on the pop-up.")
                    except Exception as e:
                        logger.warning(f"Click on 'Yes, start afresh' button failed: {e}. Trying JavaScript click.")
                        driver.execute_script("arguments[0].click();", popup_button)
                        logger.info("Clicked 'Yes, start afresh' button using JavaScript.")
                    popups_handled = True
                except TimeoutException:
                    logger.info("No 'Yes, start afresh' pop-up appeared.")

                if not popups_handled:
                    logger.info("No pop-ups appeared. Proceeding.")
                    break
                else:
                    time.sleep(0.5)
                attempts += 1

        handle_popups()

        try:
            add_item_to_cart_button_xpath = "//button[@data-cy='customize-footer-add-button']"
            add_item_to_cart_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, add_item_to_cart_button_xpath))
            )
            add_item_to_cart_button.click()
            logger.info("Clicked 'Add Item to cart' button in the pop-up.")
        except TimeoutException:
            logger.info("No 'Add Item to cart' pop-up appeared. Proceeding to the next step.")
        except Exception as e:
            logger.warning(f"Failed to click 'Add Item to cart' button: {e}. Trying JavaScript click.")
            try:
                driver.execute_script("arguments[0].click();", add_item_to_cart_button)
                logger.info("Clicked 'Add Item to cart' button using JavaScript.")
            except Exception as e:
                logger.error(f"All methods failed to click 'Add Item to cart' button: {e}.")

        try:
            modal_xpath = "//div[contains(@class, 'styles_container__')]"
            WebDriverWait(driver, 3).until(
                EC.visibility_of_element_located((By.XPATH, modal_xpath))
            )
            logger.info("Customization modal is displayed.")
            add_item_button_xpath = "//button[normalize-space()='Add Item']"
            add_item_button = driver.find_element(By.XPATH, add_item_button_xpath)
            add_item_button.click()
            logger.info("Add Item button in the modal clicked.")
        except TimeoutException:
            logger.info("No customization modal appeared.")
        except Exception as e:
            logger.warning(f"Failed to handle customization modal: {e}.")

        time.sleep(1)
        logger.info(f"Dish '{dish_name}' added to the cart.")
        checkout(driver)

    except Exception as e:
        logger.error("An error occurred while adding the dish to the cart:")
        logger.error(traceback.format_exc())
        driver.save_screenshot("add_dish_error.png")
        logger.info("Screenshot saved as add_dish_error.png.")
        raise e

def checkout(driver):
    try:
        view_cart_button_xpath = "//button[@id='view-cart-btn']"
        view_cart_button = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, view_cart_button_xpath))
        )
        logger.info("View Cart button found.")
        driver.execute_script("arguments[0].scrollIntoView(true);", view_cart_button)
        time.sleep(0.5)
        try:
            view_cart_button.click()
            logger.info("Clicked the View Cart button.")
        except Exception as e:
            logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
            driver.execute_script("arguments[0].click();", view_cart_button)
            logger.info("Clicked the View Cart button using JavaScript.")
        address_div_xpath = f"//div[@class='PPJbN' and text()='{ADDRESS_TO_SELECT}']/ancestor::div[@class='_3FahR']"
        address_div = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, address_div_xpath))
        )
        logger.info("Address div found.")
        driver.execute_script("arguments[0].scrollIntoView(true);", address_div)
        time.sleep(0.5)
        try:
            address_div.click()
            logger.info("Clicked the address div to select delivery address.")
        except Exception as e:
            logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
            driver.execute_script("arguments[0].click();", address_div)
            logger.info("Clicked the address div using JavaScript.")
        apply_coupon_button_xpath = "//div[@role='button' and @aria-label='Apply Coupon']"
        apply_coupon_button = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, apply_coupon_button_xpath))
        )
        logger.info("Apply Coupon button found.")
        driver.execute_script("arguments[0].scrollIntoView(true);", apply_coupon_button)
        time.sleep(0.5)
        try:
            apply_coupon_button.click()
            logger.info("Clicked the Apply Coupon button.")
        except Exception as e:
            logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
            driver.execute_script("arguments[0].click();", apply_coupon_button)
            logger.info("Clicked the Apply Coupon button using JavaScript.")
        coupon_popup_xpath = "//div[contains(@class, '_2qrkp')]"
        coupon_popup = WebDriverWait(driver, 7).until(
            EC.visibility_of_element_located((By.XPATH, coupon_popup_xpath))
        )
        logger.info("Coupon popup appeared.")
        coupon_popup_element = driver.find_element(By.XPATH, coupon_popup_xpath)
        try:
            last_height = driver.execute_script("return arguments[0].scrollHeight", coupon_popup_element)
            logger.info(f"Initial scroll height: {last_height}")
            while True:
                driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", coupon_popup_element)
                time.sleep(0.5)
                new_height = driver.execute_script("return arguments[0].scrollHeight", coupon_popup_element)
                logger.info(f"New scroll height: {new_height}")
                if new_height == last_height:
                    logger.info("Reached the bottom of the coupon popup.")
                    break
                last_height = new_height
        except Exception as e:
            logger.warning(f"Could not scroll the coupon popup: {e}")
        coupon_popup_html = coupon_popup_element.get_attribute('innerHTML')
        soup = BeautifulSoup(coupon_popup_html, 'html.parser')
        card_keywords = ['card', 'credit', 'debit', 'bank', 'upi', 'payment', 'amazon pay', 'wallet', 'flash', 'cred', 'simpl']
        available_coupons_header = soup.find('h2', text='Available Coupons')
        if available_coupons_header:
            available_coupons_section = available_coupons_header.find_next_sibling('div')
            coupons = available_coupons_section.find_all('div', class_='xKU6G')
            valid_coupons = []
            for coupon in coupons:
                coupon_code_tag = coupon.find('span', class_='_3vb2y')
                if coupon_code_tag:
                    coupon_code = coupon_code_tag.get_text(strip=True)
                else:
                    continue
                description_tag = coupon.find('div', class_='BT4Uo')
                if description_tag:
                    description = description_tag.get_text(strip=True)
                else:
                    description = ''
                terms_tag = coupon.find('div', class_='_3J1AT')
                if terms_tag:
                    terms = terms_tag.get_text(strip=True)
                else:
                    terms = ''
                combined_text = f"{description} {terms}".lower()
                if any(keyword in combined_text for keyword in card_keywords):
                    continue
                valid_coupons.append({
                    'code': coupon_code,
                    'description': description,
                    'terms': terms
                })
            if valid_coupons:
                def extract_discount(coupon):
                    matches = re.findall(r'₹\d+', coupon['description'])
                    if matches:
                        return int(matches[0].replace('₹', ''))
                    else:
                        return 0
                valid_coupons.sort(key=extract_discount, reverse=True)
                coupon_to_apply = valid_coupons[0]['code']
                logger.info(f"Applying coupon: {coupon_to_apply}")
                logger.info(f"Description: {valid_coupons[0]['description']}")
            else:
                logger.info("No valid app-eligible coupons available.")
                coupon_to_apply = None
        else:
            logger.info("Available Coupons section not found.")
            coupon_to_apply = None
        if coupon_to_apply:
            coupon_input_xpath = "//input[@placeholder='Enter coupon code']"
            coupon_input = WebDriverWait(driver, 7).until(
                EC.presence_of_element_located((By.XPATH, coupon_input_xpath))
            )
            logger.info("Coupon input field found.")
            coupon_input.clear()
            coupon_input.send_keys(coupon_to_apply)
            logger.info(f"Entered coupon code: {coupon_to_apply}")
            apply_button_xpath = "//a[text()='APPLY']"
            apply_button = WebDriverWait(driver, 7).until(
                EC.element_to_be_clickable((By.XPATH, apply_button_xpath))
            )
            logger.info("Apply button found.")
            try:
                apply_button.click()
                logger.info("Clicked the Apply button to apply the coupon.")
            except Exception as e:
                logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
                driver.execute_script("arguments[0].click();", apply_button)
                logger.info("Clicked the Apply button using JavaScript.")
        else:
            logger.info("No valid coupon to apply.")
        close_button_xpath = "//span[contains(@class, '_1X6No')]"
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, close_button_xpath))
            )
            close_button.click()
            logger.info("Closed the coupon popup.")
        except Exception as e:
            logger.warning(f"Could not close the coupon popup: {e}")
        try:
            yay_button_xpath = "//button[contains(@class, '_1vTiX') and text()='YAY!']"
            yay_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, yay_button_xpath))
            )
            logger.info("YAY! button found.")
            driver.execute_script("arguments[0].scrollIntoView(true);", yay_button)
            time.sleep(0.5)
            try:
                yay_button.click()
                logger.info("Clicked the YAY! button.")
            except Exception as e:
                logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
                driver.execute_script("arguments[0].click();", yay_button)
                logger.info("Clicked the YAY! button using JavaScript.")
        except TimeoutException:
            logger.info("YAY! button did not appear. Proceeding to 'Proceed to Pay'.")
        proceed_to_pay_button_xpath = "//button[contains(@class, '_4dnMB') and text()='Proceed to Pay']"
        proceed_to_pay_button = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, proceed_to_pay_button_xpath))
        )
        logger.info("Proceed to Pay button found.")
        driver.execute_script("arguments[0].scrollIntoView(true);", proceed_to_pay_button)
        time.sleep(0.5)
        try:
            proceed_to_pay_button.click()
            logger.info("Clicked the Proceed to Pay button.")
        except Exception as e:
            logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
            driver.execute_script("arguments[0].click();", proceed_to_pay_button)
            logger.info("Clicked the Proceed to Pay button using JavaScript.")
        payment_method_div_xpath = "//div[@data-testid='pm_si_container' and .//div[contains(text(), 'Swiggy Money')]]"
        payment_method_div = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, payment_method_div_xpath))
        )
        logger.info("Swiggy Money payment method div found.")
        driver.execute_script("arguments[0].scrollIntoView(true);", payment_method_div)
        time.sleep(0.5)
        try:
            payment_method_div.click()
            logger.info("Clicked the Swiggy Money payment method div.")
        except Exception as e:
            logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
            driver.execute_script("arguments[0].click();", payment_method_div)
            logger.info("Clicked the Swiggy Money payment method div using JavaScript.")
        pay_button_xpath = "//button[@data-testid='pm_si_pay_btn' and contains(text(), 'Pay')]"
        pay_button = WebDriverWait(driver, 7).until(
            EC.element_to_be_clickable((By.XPATH, pay_button_xpath))
        )
        logger.info("'Pay' button found.")
        driver.execute_script("arguments[0].scrollIntoView(true);", pay_button)
        time.sleep(0.5)
        try:
            pay_button.click()
            logger.info("Clicked the 'Pay' button.")
        except Exception as e:
            logger.warning(f"Normal click failed: {e}. Trying JavaScript click.")
            driver.execute_script("arguments[0].click();", pay_button)
            logger.info("Clicked the 'Pay' button using JavaScript.")
        logger.info("Order placed successfully.")
        restart_selenium()
    except Exception as e:
        logger.error("An error occurred during checkout:")
        logger.error(traceback.format_exc())
        driver.save_screenshot("checkout_error.png")
        logger.info("Screenshot saved as checkout_error.png.")
        raise e

def initialize_selenium():
    global driver
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    profile_path = os.path.join(os.getcwd(), 'chrome_profile')
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(SWIGGY_URL)
        logger.info(f"Navigated to {SWIGGY_URL}.")
        time.sleep(2)
        if is_logged_in(driver):
            logger.info("User is already logged in.")
        else:
            logger.info("User is not logged in. Proceeding to login.")
            if perform_login(driver):
                logger.info("Login successful.")
            else:
                logger.error("Failed to log in.")
                return False
        select_address(driver)
        return True
    except Exception as e:
        logger.error(f"An unexpected error occurred during initialization: {e}")
        return False

def restart_selenium():
    global driver
    logger.info("Restarting Selenium WebDriver for the next order.")
    try:
        driver.quit()
        logger.info("Browser closed.")
    except Exception as e:
        logger.warning(f"Error while closing the driver: {e}")
    initialize_selenium()

@app.route('/order', methods=['POST'])
def order_food():
    global driver
    data = request.get_json()
    if not data or 'dish' not in data:
        return jsonify({"error": "Please provide a dish name."}), 400
    dish = data['dish']
    logger.info(f"Received order request for dish: {dish}")
    try:
        search_restaurant(driver, dish)
        return jsonify({"message": f"Order placed for {dish}."}), 200
    except Exception as e:
        logger.error(f"An error occurred while processing the order: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    if initialize_selenium():
        app.run(host='0.0.0.0', port=8000)
    else:
        logger.error("Failed to initialize Selenium WebDriver.")
