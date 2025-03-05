from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

department_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("Заїзд власний", callback_data='arrival_own')],
    [InlineKeyboardButton("Виїзд власний", callback_data='depart_own')],
    [InlineKeyboardButton("Заїзд чужий", callback_data='arrival_alien')],
    [InlineKeyboardButton("Виїзд чужий", callback_data='depart_alien')]
])

main = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Зробити звіт')]], resize_keyboard=True)
