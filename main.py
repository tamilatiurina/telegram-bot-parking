import os
from dotenv import load_dotenv
import logging
import gspread
import requests
import time
from concurrent.futures import ThreadPoolExecutor
from aiogram.dispatcher.filters import CommandStart
from gspread.utils import rowcol_to_a1
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
import asyncio
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from datetime import datetime

import keyboard as kb

# Load environment variables from the .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Google Sheets Authorization
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# Load the Google Sheets credentials file from environment
creds_file = os.getenv("CREDS")
creds = Credentials.from_service_account_file(creds_file, scopes=scope)

# Function to refresh credentials if needed
def ensure_credentials_refresh(creds):
    if not creds.valid or creds.expired:
        creds.refresh(Request())
    return creds

# Refresh credentials and authorize gspread
def get_refreshed_sheet(department):
    global creds
    creds = ensure_credentials_refresh(creds)
    client = gspread.authorize(creds)
    #OPEN THE SPREADSHEET(IN THIS CASE IT'S "Заїзд автомобілей")
    spreadsheet = client.open("Заїзд автомобілей")

    # Select the correct sheet based on the department
    if department == 'arrival_own':
        sheet = spreadsheet.get_worksheet(0)  # Sheet1
    elif department == 'depart_own':
        sheet = spreadsheet.get_worksheet(1)  # Sheet2
    elif department == 'arrival_alien':
        sheet = spreadsheet.get_worksheet(2)  # Sheet3
    elif department == 'depart_alien':
        sheet = spreadsheet.get_worksheet(3)  # Sheet4
    else:
        raise ValueError(f"Unknown department: {department}")

    sheet.client.session.timeout = 60  # Set the session timeout
    return sheet

# Initialize bot and dispatcher
API_TOKEN = os.getenv("TOKEN")  # Load the Telegram bot token from environmentgit
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Executor for handling concurrent sheet updates
executor_pool = ThreadPoolExecutor(max_workers=5)

# Define states for FSM
class ReportForm(StatesGroup):
    choosing_department = State()
    waiting_for_tractor = State()
    waiting_for_trailer = State()


# Handle /stop command
@dp.message_handler(commands=['stop'], state='*')
async def stop_reporting(message: types.Message, state: FSMContext):
    await state.finish()  # Reset the state
    await message.reply("Звіт припинено.") #Send message "reporting stopped"


# Handle /start command
@dp.message_handler(lambda message: CommandStart() or message.text == "Зробити звіт")
async def start(message: types.Message):

    #Choose the type of action: arrival of own vehicle, departure of own vehicle,  arrival of alien vehicle, departure of alien vehicle
    await message.answer(
            "Виберіть подію:",
                reply_markup=kb.department_kb
        )

    await ReportForm.choosing_department.set()

# Handle department selection
@dp.callback_query_handler(state=ReportForm.choosing_department)
async def process_department_choice(callback_query: types.CallbackQuery, state: FSMContext):
    department = callback_query.data
    await state.update_data(department=department)
    await bot.answer_callback_query(callback_query.id)
    await get_tractor_number(callback_query.message, state)


async def get_tractor_number(message: types.Message,  state: FSMContext):
    await message.answer("Введіть номер тягача:")
    await ReportForm.waiting_for_tractor.set()


@dp.message_handler(state=ReportForm.waiting_for_tractor)
async def get_trailer_number(message: types.Message,  state: FSMContext):
    await state.update_data(tractor=message.text)
    await message.answer("Введіть номер прицепу:")
    await ReportForm.waiting_for_trailer.set()


def find_last_day_column(sheet, start_col=3, col_offset=4, max_retries=5, base_delay=2):
    """Find the next available column for a new day, shifting by the specified column offset.
    Retries on failure with exponential backoff."""

    retries = 0
    col_index = start_col  # Start with column C (index 3)
    last_filled_column = None  # Track the last column with a date

    while True:
        try:
            while True:
                cell_value = sheet.cell(2, col_index).value  # Check the cell in row 2 for the date
                if cell_value:  # If a date is found, update the last filled column
                    last_filled_column = col_index
                else:
                    # Stop when no date is found, return the last filled column
                    return last_filled_column if last_filled_column else start_col

                col_index += col_offset  # Shift to the next column set (every 4 columns)
        except (gspread.exceptions.APIError, requests.exceptions.RequestException) as e:
            if retries < max_retries:
                # Apply exponential backoff delay
                delay = base_delay * (2 ** retries)
                retries += 1
                logging.warning(f"Retrying to find next day column after {delay} seconds. Error: {e}")
                time.sleep(delay)  # Wait before retrying
            else:
                logging.error(f"Failed to find next day column after {max_retries} attempts. Error: {e}")
                raise



def create_new_table_for_today(sheet, start_col, max_retries=5, base_delay=2):
    """Creates a new table with headers for the current day, horizontally with retry logic."""
    current_date = datetime.now().strftime("%d/%m/%Y")
    updates = [
        {'range': f"{rowcol_to_a1(2, start_col)}", 'values': [[current_date]]},  # Date in row 2, start_col
        {'range': f"{rowcol_to_a1(3, start_col - 1)}", 'values': [["Час"]]},  # Time header in column before start_col
        {'range': f"{rowcol_to_a1(3, start_col)}", 'values': [["Номер тягача"]]},  # Tractor Number in start_col
        {'range': f"{rowcol_to_a1(3, start_col + 1)}", 'values': [["Номер прицепу"]]}  # Trailer Number in start_col + 1
    ]

    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            # Batch update to Google Sheets
            sheet.batch_update(updates)
            logging.info(f"Successfully updated Google Sheets with new table on attempt {attempt + 1}")
            return start_col  # Return the starting column for the day's entries
        except (gspread.exceptions.APIError, requests.exceptions.RequestException) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logging.warning(f"Attempt {attempt + 1}/{max_retries} failed. Retrying in {delay} seconds. Error: {e}")
                time.sleep(delay)  # Wait before retrying
            else:
                logging.error(f"Failed to update Google Sheets after {max_retries} attempts. Error: {e}")
                raise  # Re-raise the error if retries exhausted


def find_next_empty_row(sheet, col_index, start_row=4, max_retries=5, base_delay=2):
    """Finds the next empty row in the given column with retry logic."""
    retries = 0
    current_row = start_row

    while True:
        try:
            # Get the cell value in the current row
            cell_value = sheet.cell(current_row, col_index).value
            if not cell_value:
                return current_row  # Return the current row if empty
            current_row += 1  # Move to the next row if the cell is not empty
        except (gspread.exceptions.APIError, requests.exceptions.RequestException) as e:
            if retries < max_retries:
                delay = base_delay * (2 ** retries)  # Exponential backoff
                retries += 1
                logging.warning(f"Retrying to find empty row after {delay} seconds. Error: {e}")
                time.sleep(delay)
            else:
                logging.error(f"Failed to find empty row after {max_retries} attempts. Error: {e}")
                raise  # Re-raise the exception if the maximum number of retries is reached



@dp.message_handler(state=ReportForm.waiting_for_trailer)
async def process_trailer(message: types.Message, state: FSMContext):
    # Update state with the received notes
    await state.update_data(trailer=message.text)
    global today_column

    user_data = await state.get_data()
    department = user_data.get("department")

    sheet = get_refreshed_sheet(department)

    # Get current date
    current_date = datetime.now().strftime("%d/%m/%Y")
    # Find the next available column for today's table
    last_column = find_last_day_column(sheet)
    # Check if today's table already exists in the calculated column
    current_date_in_sheet = sheet.cell(2, last_column).value
    if current_date_in_sheet != current_date:
        today_column = last_column + 4
        # Create a new table if today's date isn't present
        create_new_table_for_today(sheet, start_col=today_column)
    else:
        today_column = last_column

    # Find the next empty row for today's entries
    next_row_index = find_next_empty_row(sheet, today_column)

    # Immediately send confirmation and show department keyboard for new report
    await message.answer(
        "Виберіть подію:",
        reply_markup=kb.department_kb
    )

    # Finish the FSM context for this report, allowing user to start a new one
    await state.finish()

    # Reset the state for a new report form immediately
    await ReportForm.choosing_department.set()

    # Start asynchronous update of the Google Sheet
    asyncio.create_task(update_sheet_async(sheet, next_row_index, today_column, user_data, max_retries=5, base_delay=2))



async def update_sheet_async(sheet, next_row_index, today_column, user_data, max_retries=5, base_delay=2):
    updates = []

    tractor_number = user_data.get("tractor")
    trailer_number = user_data.get("trailer")

    sheet.update_acell(f"{rowcol_to_a1(next_row_index, today_column - 1)}", datetime.now().strftime("%d/%m/%Y %H:%M"))

    updates.append({'range': f"{rowcol_to_a1(next_row_index, today_column)}", 'values': [[tractor_number]]})
    updates.append({'range': f"{rowcol_to_a1(next_row_index, today_column + 1)}", 'values': [[trailer_number]]})


    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            # Try to perform the batch update
            sheet.batch_update(updates)
            logger.info(f"Successfully updated Google Sheets on attempt {attempt + 1}")
            break  # Exit the retry loop if successful
        except (gspread.exceptions.APIError, requests.exceptions.RequestException) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Failed to update Google Sheets (attempt {attempt + 1}/{max_retries}). Retrying in {delay} seconds. Error: {e}")
                await asyncio.sleep(delay)  # Wait before retrying
            else:
                logger.error(f"Failed to update Google Sheets after {max_retries} attempts. Error: {e}")
                await bot.send_message(user_data['chat_id'], "Помилка при записі звіту. Спробуйте пізніше.")
                return






async def on_startup(dp):
    print("Bot is starting...")

async def on_shutdown(dp):
    print("Bot is shutting down...")

if __name__ == '__main__':
    dp.register_message_handler(stop_reporting, commands=['stop'], state='*')
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)

