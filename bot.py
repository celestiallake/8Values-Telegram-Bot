import os
import re
import time
import sys
import threading
import random
import ssl
import math
import asyncio
from collections import namedtuple
import json
import psycopg2
from psycopg2.extras import RealDictCursor

from aiohttp import web

import telebot
from telebot import types
import logging

from config import *

phrases_herzen = [
'Никакой тест не нужен, чтобы сказать, что ты петух левацкий.',
'Сперва разбань Мартынова',
'Яблоко зелёное, спелое, садовое',
'Яблоко от яблони не далеко яблонётся, зачем тут тест?']

bot = telebot.TeleBot(API_TOKEN)

logger = telebot.logger
logger.setLevel(logging.ERROR)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = web.Application()

con = init_db()
con.set_session(autocommit=True)
cur = con.cursor(cursor_factory=RealDictCursor)


async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)

app.router.add_post('/{token}/', handle)


class Poll:
    def __init__(self, question_id = 0, stat = None, msgid = 0):
        self.answers = []
        self.question_id = question_id
        self.stat = stat
        self.msgid = msgid

Question = namedtuple('Question', ['question', 'effect'])
Ideology = namedtuple('Ideology', ['name', 'stats'])

questions = []
active_polls = {}

with open('questions.json') as data_file:
    data = json.load(data_file)
questions = [Question(**x) for x in data["questions"]]

with open('ideologies.json') as data_file:
    data = json.load(data_file)
ideologies = [Ideology(**x) for x in data["ideologies"]]

max_econ = max_dipl = max_govt = max_scty = 0
for q in questions:
    max_econ += abs(q.effect['econ'])
    max_dipl += abs(q.effect['dipl'])
    max_govt += abs(q.effect['govt'])
    max_scty += abs(q.effect['scty'])


kb = types.InlineKeyboardMarkup()
kb.add(types.InlineKeyboardButton(text="Согласен", callback_data='1'))
kb.add(types.InlineKeyboardButton(text="Скорее согласен", callback_data='0.5'))
kb.add(types.InlineKeyboardButton(text="Не знаю/Не уверен", callback_data='0'))
kb.add(types.InlineKeyboardButton(text="Скорее не согласен", callback_data='-0.5'))
kb.add(types.InlineKeyboardButton(text="Не согласен", callback_data='-1'))
kb.add(types.InlineKeyboardButton(text="Предыдущий вопрос", callback_data="Back"))

stat_file = open("anon_ids_stat.txt", 'a')

counted_stats = ['']*len(questions)

def parse_results():
    for i in range(len(questions)):
        with open('./results/{}.txt'.format(str(i+1)), 'r') as file:
            counted_stats[i] = file.read()


@bot.message_handler(commands=['getresults'])
def on_getresults(m):
    if len(m.text.split()) < 2 or not m.text.split()[1].isdigit():
        #bot.send_message(m.chat.id, 'Использование:\n/getresults <номер вопроса>')
        q = 1
    else:
        q = int(m.text.split()[1])

    if q > len(questions) or q < 1:
        bot.send_message(m.chat.id, 'Есть всего {} вопросов!'.format(len(questions)))
    else:
        kbnp = types.InlineKeyboardMarkup()
        if q < len(questions):
            kbnp.add(types.InlineKeyboardButton(text='Следующий', callback_data='next {}'.format(q-1)))
        if q > 1:
            kbnp.add(types.InlineKeyboardButton(text='Предыдующий', callback_data='prev {}'.format(q-1)))
        bot.send_message(m.chat.id, counted_stats[q-1], reply_markup=kbnp)


@bot.message_handler(func=lambda m: m.chat.type == "private", commands=['start'])
def on_start(m):
    bot.send_message(m.chat.id, 'Привет! Я могу устроить опрос, который поможет определить ваши политические взгляды (за основу взят 8values).\n\nВведите /help, чтобы получить помощь.\n\n\nОтдельное спасибо @hairysparx за крутую аву :)\nПо всем вопросам насчёт бота обращаться к @realMastAKK.')


@bot.message_handler(func=lambda m: m.chat.type == "private", commands=['help'])
def on_help(m):
    bot.send_message(m.chat.id, 'Чтобы начать опрос введите команду /startpoll\nЕсли опрос уже идёт - сперва закончите его!\n'
                                'Проходить можно сколько угодно раз, но статистика сохраняется только для последнего сохраненного.\n\n\nЭтот тест является переводом оригинального [8Values](https://8values.github.io)\n'
                                'Если хотите узнать статистику по тому или иному вопросу, введите /getresults <номер вопроса>. Помните, что есть всего 70 вопросов!\n\n\n\n', parse_mode='Markdown')
    r = random.randint(0, 2)
    if r == 0:
        bot.send_message(m.chat.id, '_*реклама*_\nПотерял доступ к своим правам и свободам на территории РФ? Не надо добавлять цифру 7 после joycasino!\n'
                                    'Просто подпишись на канал @nedimonmskinf и заходи в их чат @nedimon\_msk, следи за движухой и присоединяйся к ней!\n\n'
                                    '_Интересный факт: в этом чате обитает создатель данного бота - @realMastAKK_', parse_mode='Markdown')
    elif r == 1:
        bot.send_message(m.chat.id, '_*реклама*_\nМне частно говорят: мастакк, как нам поднять права?\n'
                                    'Я отвечаю: заходи в @nedimon\_msk!\n'
                                    'Доначу и не плачу, чтоб не затух их движ\n'
                                    'Мы оппозиция, никак иначе, мы не молчим\n\n(а ещё есть телеграм канал @nedimonmskinf)', parse_mode='Markdown')
    elif r == 2:
        bot.send_message(m.chat.id, '_*реклама*_\nЯ из госдепа к вам прибыть\n'
                                    'Инвайт в @nedimonmskinf вам приносить!\n'
                                    'Страну там помогать лечить\n'
                                    'Без пыни жить мечтают,\n'
                                    'Что в их силах сотворяют\n\n(а ещё есть телеграм чат @nedimon\_msk)', parse_mode='Markdown')


@bot.message_handler(func=lambda m: m.chat.type == "private", commands=['startpoll'])
def on_startpoll(m):
    if m.from_user.id in [171970483]:
        bot.send_message(m.chat.id, phrases_herzen[random.randint(0, 3)])
        return
    if m.chat.id not in active_polls:
        cur.execute('INSERT INTO polls(uid) VALUES ({})'.format(m.chat.id))
        active_polls[m.chat.id] =  Poll()
        bot.send_message(m.chat.id, 'Сперва скажите, согласны ли вы на сбор анонимной статистики для составления инфографики (решение можно менять в процессе теста)\n/agree - согласен\n/disagree - не согласен')
    else:
        bot.send_message(m.chat.id, 'Вероятно, вы уже начинали тест. Начните заново командой /restartpoll')

@bot.message_handler(func=lambda m: m.chat.type == "private", commands=['restartpoll'])
def on_restartpoll(m):
    bot.send_message(m.chat.id, 'Начинаем заново')
    active_polls.pop(m.chat.id, None)
    cur.execute('DELETE FROM polls WHERE uid={}'.format(m.chat.id))
    on_startpoll(m)


@bot.message_handler(func=lambda m:m.chat.type == 'private', commands=['stat'])
def on_stat(m):
    fin = open('./ideologies_count.txt', 'r')
    text = fin.read()
    bot.send_message(m.chat.id, text)


def get_question_text(id):
    if id in active_polls and active_polls[id].question_id < len(questions):
        return 'Вопрос {} из {}\n'.format(active_polls[id].question_id + 1, len(questions)) + questions[active_polls[id].question_id].question
    else:
        return 'Это был последний вопрос.'


@bot.message_handler(func=lambda m: m.chat.type == "private", commands=["agree"])
def on_agreement(m):
    if m.chat.id in active_polls:
        cur.execute('UPDATE polls SET agree=TRUE WHERE uid={}'.format(m.chat.id))
        active_polls[m.chat.id].stat = True
        active_polls[m.chat.id].msgid = m.message_id
        bot.send_message(m.chat.id, 'Хорошо, я вас понял!')
        bot.send_message(m.chat.id, get_question_text(m.chat.id), reply_markup=kb)


@bot.message_handler(func=lambda m: m.chat.type == "private", commands=["disagree"])
def on_agreement(m):
    if m.chat.id in active_polls:
        cur.execute('UPDATE polls SET agree=FALSE WHERE uid={}'.format(m.chat.id))
        active_polls[m.chat.id].stat = False
        active_polls[m.chat.id].msgid = m.message_id
        bot.send_message(m.chat.id, 'Хорошо, я вас понял!')
        bot.send_message(m.chat.id, get_question_text(m.chat.id), reply_markup=kb)


def calc_score(score, max):
    return round(100*(max+score)/(2*max), 1)


econArray = ["Коммунистическая", "Социалистическая", "Социальная", "Центристская", "Рыночная", "Капиталистическая", "Laissez-Faire"]
diplArray = ["Космополитическая", "Интернациональная", "Мирная", "Сбалансированная", "Патриотическая", "Националистическая", "Шовинистская"]
govtArray = ["Анархистская", "Либертарная", "Либеральная", "Умеренная", "Этатистская", "Авторитарная", "Тоталитарная"]
sctyArray = ["Революционная", "Крайне прогрессивная", "Прогрессивная", "Нейтральная", "Традиционная", "Крайне традиционная", "Реакционная"]


def get_name(ary, val):
    if val > 100:
        return ""
    if val > 90:
        return ary[0]
    if val > 75:
        return ary[1]
    if val > 60:
        return ary[2]
    if val >= 40:
        return ary[3]
    if val >= 25:
        return ary[4]
    if val >= 10:
        return ary[5]
    if val >= 0:
        return ary[6]
    return ""


def send_results(id, username):
    econ = 0.0
    dipl = 0.0
    govt = 0.0
    scty = 0.0

    for i in range(len(active_polls[id].answers)):
        econ += active_polls[id].answers[i] * questions[i].effect['econ']
        dipl += active_polls[id].answers[i] * questions[i].effect['dipl']
        govt += active_polls[id].answers[i] * questions[i].effect['govt']
        scty += active_polls[id].answers[i] * questions[i].effect['scty']

    econ = calc_score(econ, max_econ)
    dipl = calc_score(dipl, max_dipl)
    govt = calc_score(govt, max_govt)
    scty = calc_score(scty, max_scty)

    result_text = 'Экономическая ось: {}\nРавенство {}% - {}% Рынок\n\n'.format(get_name(econArray, econ), econ, round(100-econ, 1))
    result_text += 'Дипломатическая ось: {}\nНация {}% - {}% Мир\n\n'.format(get_name(diplArray, dipl), round(100-dipl, 1), dipl)
    result_text += 'Гражданская ось: {}\nСвобода {}% - {}% Авторитарность\n\n'.format(get_name(govtArray, govt), govt, round(100-govt, 1))
    result_text += 'Социальная ось: {}\nТрадиции {}% - {}% Прогресс\n\n\n'.format(get_name(sctyArray, scty), round(100-scty, 1), scty)

    ideology = ""
    ideodist = math.inf
    for i in ideologies:
        dist = 0
        dist += pow(abs(i.stats['econ'] - econ), 2)
        dist += pow(abs(i.stats['govt'] - govt), 2)
        dist += pow(abs(i.stats['dipl'] - dipl), 1.73856063)
        dist += pow(abs(i.stats['scty'] - scty), 1.73856063)
        if dist < ideodist:
            ideology = i.name
            ideodist = dist
    result_text += 'Ближайшее совпадение: {}'.format(ideology)
    bot.send_message(id, result_text)
    bot.send_message(id, 'Кстати, у бота есть свой чатик, где можно обсудить результаты и пообщаться на тему различных идеологий\n@eightvalues. \n\nА у автора перевода и самого этого бота есть свой канал, там бывают всякие интересности про политику, IT, творчество и т.п. Заглядывайте! @dzcreativity')
    if active_polls[id].stat == True:
        #print('Writing anon_stat.txt')
        stat_file.write('{}:'.format(id))
        stat_file.write(','.join(str(x) for x in active_polls[id].answers))
        stat_file.write('\n\n')
        stat_file.flush()
    bot.send_photo(id, "http://bot.rtmp.ru/new_bots/8values_image.php?e={}&d={}&g={}&s={}".format(econ, dipl, govt, scty))

    active_polls.pop(id, None)
    cur.execute('DELETE FROM polls WHERE uid={}'.format(id))


sending = False
@bot.message_handler(func=lambda m: m.chat.type == "private", commands=["notifyaboutchat"])
def onnotifychat(m):
    if m.text.split(' ')[1] == "mastamasta321" and not sending:
        with open('part_ids.txt', 'r') as f:
            content = f.readlines()
        ids = [x.strip() for x in content]
        ids = ids[450:1099]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        print("starting coroutine")
        print(len(ids))
        loop.run_until_complete(sendinvite(ids))


async def sendinvite(ids):
    print("coroutine started")
    sending = True
    textinv = 'Привет.\n Я создал беседу, где можно будет обсудить результат теста, задать вопросы про различные идеологии. Так сказать, дискуссионный клуб.\n'
    textinv += 'Там же можно будет пообщаться со мной (переводчиком теста и разработчиком бота), указать на неточности в переводе... Ну и всё в таком духе :)\n'
    textinv += 'Присоединяйся!\nhttps://t.me/joinchat/ForjZ0paTZugCHK1ntBjvw\n\nP.S. за рекламу и спам бот будет изгонять вас ;)'
    print(len(ids))
    i = 0
    while i < len(ids):
        for j in range(0, 20):
            if i + j < len(ids):
                try:
                    bot.send_message(ids[i + j], textinv)
                except Exception as ex:
                    print(ex)
        i += 20
        await asyncio.sleep(1.0)
        print("20 messages sent, total {}".format(i))
    sending = False


@bot.callback_query_handler(func = lambda c: 1)
def on_callback_query(call):
    if call.data.split()[0] == 'next':
        q = int(call.data.split()[1]) + 1
        kbnp = types.InlineKeyboardMarkup()
        if q < len(questions)-1:
            kbnp.add(types.InlineKeyboardButton(text='Следующий', callback_data='next {}'.format(q)))
        if q > 0:
            kbnp.add(types.InlineKeyboardButton(text='Предыдущий', callback_data='prev {}'.format(q)))
        if q < len(questions):
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=counted_stats[q], reply_markup=kbnp)
        bot.answer_callback_query(callback_query_id=call.id)
        return
    elif call.data.split()[0] == 'prev':
        q = int(call.data.split()[1]) - 1
        kbnp = types.InlineKeyboardMarkup()
        if q < len(questions)-1:
            kbnp.add(types.InlineKeyboardButton(text='Следующий', callback_data='next {}'.format(q)))
        if q > 0:
            kbnp.add(types.InlineKeyboardButton(text='Предыдущий', callback_data='prev {}'.format(q)))
        if q < len(questions):
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=counted_stats[q], reply_markup=kbnp)
        bot.answer_callback_query(callback_query_id=call.id)
        return

    if call.message.chat.type != "private":
        return
    if call.message.chat.id not in active_polls:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Начните тест, введя команду /startpoll')
        return
    if call.data == "Back":
        if active_polls[call.message.chat.id].question_id > 0:
            active_polls[call.message.chat.id].answers.pop()
            active_polls[call.message.chat.id].question_id -= 1
            cur.execute('UPDATE polls SET question_id={} WHERE uid={}'.format(active_polls[call.message.chat.id].question_id, call.message.chat.id))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_question_text(call.message.chat.id), reply_markup=kb)
    elif active_polls[call.message.chat.id].question_id < len(questions):
        active_polls[call.message.chat.id].answers.append(float(call.data))
        active_polls[call.message.chat.id].question_id += 1
        qid = active_polls[call.message.chat.id].question_id
        cur.execute('UPDATE polls SET answers[{}]={}, question_id={} WHERE uid={}'.format(qid, float(call.data), qid, call.message.chat.id))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_question_text(call.message.chat.id), reply_markup=kb)

    if len(active_polls[call.message.chat.id].answers) == len(questions):
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Сейчас я сообщу результаты!')
        send_results(call.message.chat.id, call.message.chat.username)
    bot.answer_callback_query(callback_query_id=call.id)


cur.execute('SELECT * FROM polls')
db_polls = cur.fetchall()
for p in db_polls:
    uid = int(p['uid'])
    active_polls[uid] = Poll(int(p['question_id']), p['agree'])
    if p['answers'] != None:
        for ans in list(p['answers']):
            active_polls[uid].answers.append(float(ans))


parse_results()

bot.remove_webhook()
time.sleep(2)
bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH,
                certificate=open(WEBHOOK_SSL_CERT, 'r'))

context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

web.run_app(
    app,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    ssl_context=context,
)
