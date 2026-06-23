import telebot
import time
import schedule
import threading
import asyncio
import re  
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = '8934351450:AAGNVgSQ7rfBz509T5QWAGVdLH0tMSpm3KM'
YOUR_CHAT_ID = '1035397514' 

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# List of Pincodes to track (Delhi and Ghaziabad)
TRACKED_PINCODES = ["110001", "110092", "201001", "201010"] 
PRODUCT_URL = "https://shop.amul.com/en/product/amul-high-protein-plain-lassi-200-ml-or-pack-of-30"

async def _async_check_amul(pincode):
    """
    The "Human Fingers" Strategy.
    Runs invisibly (headless=True) to type the pincode, click the autocomplete dropdown, 
    and read the actual screen UI to bypass API restrictions.
    """
    PRODUCT_PAGE = "https://shop.amul.com/en/product/amul-high-protein-plain-lassi-200-ml-or-pack-of-30"
    
    try:
        async with async_playwright() as p:
            # Running completely invisibly in the background now!
            browser = await p.chromium.launch(headless=True) 
            
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Step 1: Open the page
            await page.goto(PRODUCT_PAGE, wait_until="domcontentloaded", timeout=45000)
            
            # Step 2: Wait for Amul's popup
            await page.wait_for_timeout(3000) 
            
            # Find the input box
            pincode_input = page.get_by_placeholder(re.compile("pincode", re.IGNORECASE)).first
            
            if await pincode_input.is_visible():
                print(f"[{pincode}] Popup found! Typing sequentially...")
                await pincode_input.press_sequentially(pincode, delay=150)
                
                print(f"[{pincode}] Waiting for the autocomplete dropdown to appear...")
                await page.wait_for_timeout(1500) 
                
                try:
                    dropdown_item = page.get_by_text(pincode, exact=True).last
                    await dropdown_item.click(timeout=3000)
                    print(f"[{pincode}] Successfully clicked the dropdown menu!")
                except Exception as e:
                    print(f"[{pincode}] Click failed, trying keyboard fallback...")
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                
                # Wait 5 seconds for the actual stock page to load
                await page.wait_for_timeout(5000) 
            else:
                print(f"[{pincode}] No popup appeared. Checking screen anyway...")
            
            # Step 3: Now read the screen!
            content = await page.content()
            content_lower = content.lower()
            
            await browser.close()
            
            out_of_stock_phrases = ["out of stock", "sold out", "currently unavailable", "not available", "we are currently not serviceable"]
            in_stock_phrases = ["add to cart", "buy now"]
            
            if any(phrase in content_lower for phrase in out_of_stock_phrases):
                return False
            elif any(phrase in content_lower for phrase in in_stock_phrases):
                return True
            else:
                print(f"Could not find stock status text for {pincode}.")
                return False
                
    except Exception as e:
        print(f"Error checking pincode {pincode}: {e}")
        return False

def check_amul_availability(pincode):
    return asyncio.run(_async_check_amul(pincode))

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🥛 Welcome to the Amul Lassi Tracker!\nSend me a Delhi or Ghaziabad pincode (e.g., 201001) to check availability.")

@bot.message_handler(func=lambda message: True)
def handle_pincode(message):
    pincode = message.text.strip()
    if len(pincode) == 6 and pincode.isdigit():
        bot.reply_to(message, f"Checking stock for {pincode}...")
        is_available = check_amul_availability(pincode)
        if is_available:
            bot.reply_to(message, f"✅ GOOD NEWS! Amul Protein Lassi is in stock at {pincode}.\nBuy here: {PRODUCT_URL}")
        else:
            bot.reply_to(message, f"❌ Out of stock at {pincode}. I'll keep an eye out!")
    else:
        bot.reply_to(message, "Please enter a valid 6-digit pincode.")

def auto_check_job():
    print("Running background check for tracked pincodes...")
    for pin in TRACKED_PINCODES:
        if check_amul_availability(pin):
            bot.send_message(YOUR_CHAT_ID, f"🚨 RESTOCK ALERT 🚨\nProtein Lassi is now available at {pin}!\nLink: {PRODUCT_URL}")
        time.sleep(2)

def run_scheduler():
    schedule.every(30).minutes.do(auto_check_job)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("Bot is running...")
    threading.Thread(target=run_scheduler, daemon=True).start()
    bot.infinity_polling()
