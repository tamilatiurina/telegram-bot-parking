# Vehicle Report Bot for parking

This Telegram bot is designed to streamline vehicle reporting in the parking, logging data directly into a Google Spreadsheet. Users can easily report vehicle arrivals and departures (both own and third-party) with just a few steps via chat.
The bot automatically organizes reports by date and stores tractor number, trailer number and timestamp. Data is reliably written into different sheets within a Google Spreadsheet named “Заїзд автомобілей”.

## Features
1. Interactive FSM (Finite State Machine) flow for collecting data
2. Automatic daily table creation
3. Exponential backoff and retry logic for handling Google Sheets API errors
4. Asynchronous and concurrent data processing

## Prerequisites
1. Python 3.8+
2. Telegram Bot API token: You can create a bot and get an API token from the [BotFather](https://core.telegram.org/bots#botfather).
3. Google Service Account Key: Create a Google service account and download the JSON credentials file to enable Google Sheets API access.
4. Google Sheets Document: Set up a Google Sheet to store the reports.

## Installation

### 1. Clone the Repository:
```bash
git clone https://github.com/tamilatiurina/telegram-bot-parking.git
cd telegram-bot-parking
```
### 2. Install Dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configure Google Sheets:
  1. Create a Google Spreadsheet named “Заїзд автомобілей”.  
  2. Create four sheets inside:  
    Sheet1 – Arrival of own vehicles  
    Sheet2 – Departure of own vehicles  
    Sheet3 – Arrival of third-party vehicles  
    Sheet4 – Departure of third-party vehicles  
  3. Share Google Sheet with the service account email found in the JSON credentials file.

### 4. Set Up Environment Variables (create a .env file with the following environment variables):
```bash
TOKEN=your_telegram_bot_api_token
CREDS=path_to_google_credentials.json
```
### 5. Run the Bot:
```bash
python bot.py
```

## Usage

### Workflow
1. User starts the bot via ```/start```.
2. The bot asks the user to choose a report type (via inline keyboard).  
3. The bot collects tractor number and trailer number. 
4. Data is saved in the correct sheet with date, time and vehicle numbers.  
5. The user can immediately start another report or stop with ```/stop```.

## Contributing
Contributions are welcome! If you find a bug or have a suggestion, feel free to open an issue or submit a pull request.

## License
This project is licensed under the MIT License. See the ```LICENSE``` file for details.