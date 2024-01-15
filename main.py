import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton,BotCommand
from aiogram.utils.callback_answer import CallbackAnswer
import pyodbc
import json
import aiocron
# from aiogram_broadcaster import TextBroadcaster

with open('config.json', 'r', encoding='utf-8') as f: #открыли файл с данными
    config = json.load(f)
conn = pyodbc.connect('DRIVER={ODBC Driver 11 for SQL Server};SERVER='+config["DATABASE"]["HOST"]
                        +';DATABASE='+config["DATABASE"]["DB"]+';UID='+config["DATABASE"]["USERNAME"]
                        +';PWD='+config["DATABASE"]["PASSWORD"])
cursor = conn.cursor()

cb_inline = CallbackAnswer("post", 'action', "data")

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)
# Объект бота
bot = Bot(token=config['BOT_TOKEN']['KEY'])
# Диспетчер
dp = Dispatcher()
# Хэндлер на команду /start


async def get_list_abit():
    cursor.execute('exec pps_get_chat_id')
    lst_abit =[str(ab[0])  for ab in cursor.fetchall()]
    return lst_abit


# 0 10 1 * *

async def send_broadcast():
    abit = get_list_abit()
    print('Выполнен')
    print(abit)
    for ab in abit:
        await bot.send_message(ab,"Открыт новый опрос!!")

@aiocron.crontab('* * * * *')
async def scheduled_message():
    await send_broadcast()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    tg_id = message.from_user.id
    token_student = message.text.split()[-1]
    tg_name = message.from_user.username
    chat_id = message.chat.id
    await message.answer(f'Добро пожаловать, {tg_name}! Здесь вы сможете оценивать преподавателей в течение всего семестра. Благодаря вашей оценке, мы сможем сразу обратить внимание на возможную проблему и исправить её, чтобы ваше обучение проходило комфортно. Давайте вместе сделаем наш институт лучше!')
    if token_student !='/start':
        cursor.execute(f"exec PPS_Bot_add_tg_id_by_token '{token_student}', {tg_id}, '{tg_name}', {chat_id}")
        try:
            if cursor.fetchone()[0] == 'Токена нет':
                await message.answer("Спасибо, что заинтересовались нашим опросом, но он только для студентов ВВГУ. Будем рады видеть вас в нашем институте!")
        except pyodbc.ProgrammingError:
            cursor.commit()
            await  message.answer("Для того чтобы проголосовать напиши /vote")
    else:
        try:
            if cursor.execute(f'exec verification_by_tg_id {tg_id}').fetchone()[0]==tg_id:
                await  message.answer("Для того чтобы проголосовать напиши /vote")
        except:
            await message.answer("Спасибо, что заинтересовались нашим опросом, но он только для студентов ВВГУ. Будем рады видеть вас в нашем институте!")

@dp.message(Command('vote'))
async def cmd_vote(message: types.Message):
    global dict_prepod
    global tg_id
    tg_id = message.from_user.id
    if int(cursor.execute(f'exec PPS_bot_check_tg {tg_id}').fetchone()[0])==1:
        if int(cursor.execute(f'exec PPS_bot_check_is_passed {tg_id}').fetchone()[0])==0:
            cursor.execute(f'exec get_sub_by_id_PPS {tg_id}')
            dict_prepod={}
            for row in cursor.fetchall():
                lecture_practice = ''
                if 'Занятие Лекционное' in row[2]:
                    lecture_practice+='Лекция/'
                if 'Занятие Практическое' in row[2]:
                    lecture_practice+='Практика/'
                if 'Занятие Лабораторное' in row[2]:
                    lecture_practice+='Лабораторная'
                if lecture_practice[-1]=='/':
                    lecture_practice=lecture_practice[:-1]
                dict_prepod[(row[0],row[1])] = f"""{lecture_practice}: {row[3]}"""
            lst_but = []
            for key,value in dict_prepod.items():
                lst_but.append([InlineKeyboardButton(text=value,callback_data=str(key))])
            inline_kb1 = InlineKeyboardMarkup(inline_keyboard=lst_but)

            await message.answer( "Кто из преподавателей произвёл на вас наиболее положительное впечатление? (Выберите одного преподавателя).",reply_markup=inline_kb1)
        else:
            await message.answer('Извините, но вы уже проголосовали в этом месяце, следующий опрос будет в начале следующего!')
    else:
        await message.answer("Спасибо, что заинтересовались нашим опросом, но он только для студентов ВВГУ. Будем рады видеть вас в нашем институте!\nЕсли вы являетесь студентом, то для первого голосования нужно зайти через ЛК.")


        
@dp.callback_query(lambda c: tuple(map(int,c.data.replace(',','').replace("'",'').replace('(','').replace(')','').split())) in list(dict_prepod.keys()))
async def send_random_value(call: types.CallbackQuery):
    answer = tuple(map(int,call.data.replace(',','').replace("'",'').replace('(','').replace(')','').split()))
    await bot.send_message(tg_id,
        "Спасибо, что приняли участие в нашем опросе! Это поможет нам сделать институт лучше. До встречи в следующих опросах.",
    )
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    cursor.execute(f'exec add_answer_pps_bot {tg_id},{answer[0]},{answer[1]}')
    cursor.commit()


# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    asyncio.run(main())