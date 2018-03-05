import asyncio

from collections import namedtuple

import json
import logging

from math import cos, floor, inf, pi

import random
import ssl
import time
import telebot

from psycopg2.extras import RealDictCursor
from aiohttp import web
from __config import *

PHRASES_HERZEN = [
    'Никакой тест не нужен, чтобы сказать, что ты петух левацкий.',
    'Сперва разбань Мартынова',
    'Яблоко зелёное, спелое, садовое',
    'Яблоко от яблони не далеко яблонётся, зачем тут тест?'
]

BOT = telebot.TeleBot(API_TOKEN)

LOGGER = telebot.logger
LOGGER.setLevel(logging.ERROR)

W_LOG = logging.getLogger('werkzeug')
W_LOG.setLevel(logging.ERROR)

APP = web.Application()

CON = init_db()
CON.set_session(autocommit=True)
CUR = CON.cursor(cursor_factory=RealDictCursor)


async def handle(request):
    """
    Handles requests.
    """
    if request.match_info.get('token') == BOT.token:
        request_body_json = await request.json()
        update = telebot.types.Update.de_json(request_body_json)
        BOT.process_new_updates([update])
        return web.Response()
    return web.Response(status=403)

APP.router.add_post('/{token}/', handle)


class Poll:
    """
    Data class describing a single poll
    """

    def __init__(self, question_id=0, stat=None, msgid=0):
        self.answers = []
        self.question_id = question_id
        self.stat = stat
        self.msgid = msgid


Question = namedtuple('Question', ['question', 'effect'])
Ideology = namedtuple('Ideology', ['name', 'stats'])

QUESTIONS = []
ACTIVE_POLLS = {}

with open('questions.json') as data_file:
    DATA = json.load(data_file)
QUESTIONS = [Question(**x) for x in DATA["questions"]]

with open('ideologies.json') as data_file:
    DATA = json.load(data_file)
IDEOLOGIES = [Ideology(**x) for x in DATA["IDEOLOGIES"]]

MAX_ECON = MAX_DIPL = MAX_GOVT = MAX_SCTY = 0
for question in QUESTIONS:
    MAX_ECON += abs(question.effect['econ'])
    MAX_DIPL += abs(question.effect['dipl'])
    MAX_GOVT += abs(question.effect['govt'])
    MAX_SCTY += abs(question.effect['scty'])


KB = telebot.types.InlineKeyboardMarkup()
tuple(map(
    lambda x: KB.add(telebot.types.InlineKeyboardButton(
        text=x[0], callback_data=x[1])),
    (("Согласен", "1"), ("Скорее согласен", "0.5"), ("Не знаю/Не уверен", "0"),
     ("Скорее не согласен", "-0.5"), ("Не согласен", "-1"), ("Предыдущий вопрос", "Back"))
))

STAT_FILE = open("anon_ids_stat.txt", 'a')

COUNTED_STATS = ['']*len(QUESTIONS)


def parse_results():
    """
    Handles result processing.
    """
    for i in range(len(QUESTIONS)):
        with open('./results/{}.txt'.format(str(i+1)), 'r') as file:
            COUNTED_STATS[i] = file.read()


@BOT.message_handler(commands=['getresults'])
def on_getresults(msg):
    """
    Listens for results.
    """
    if len(msg.text.split()) < 2 or not msg.text.split()[1].isdigit():  # You don't even read it!
        #BOT.send_message(msg.chat.id, 'Использование:\n/getresults <номер вопроса>')
        q_id = 1
    else:
        q_id = int(msg.text.split()[1])

    if q_id > len(QUESTIONS) or q_id < 1:
        BOT.send_message(
            msg.chat.id, 'Есть всего {} вопросов!'.format(len(QUESTIONS))
        )
    else:
        kbnp = telebot.types.InlineKeyboardMarkup()
        if q_id < len(QUESTIONS):
            kbnp.add(telebot.types.InlineKeyboardButton(
                text='Следующий', callback_data='next {}'.format(q_id-1)))
        if q_id > 1:
            kbnp.add(telebot.types.InlineKeyboardButton(
                text='Предыдующий', callback_data='prev {}'.format(q_id-1)))
        BOT.send_message(msg.chat.id, COUNTED_STATS[q_id-1], reply_markup=kbnp)


@BOT.message_handler(func=lambda msg: msg.chat.type == "private", commands=['start'])
def on_start(msg):
    """
    Handles /start
    """
    BOT.send_message(
        msg.chat.id,
        'Привет! Я могу устроить опрос, который поможет определить ваши политические взгляды '
        '(за основу взят 8values).\n\nВведите /help, чтобы получить помощь.\n\n\nОтдельное '
        'спасибо @hairysparx за крутую аву :)\nПо всем вопросам насчёт бота обращаться к '
        '@realMastAKK.'
    )


@BOT.message_handler(func=lambda msg: msg.chat.type == "private", commands=['help'])
def on_help(msg):
    """
    Handles /help and throws some ads in your face
    """
    BOT.send_message(
        msg.chat.id,
        'Чтобы начать опрос введите команду /startpoll\nЕсли опрос уже идёт - сперва '
        'закончите его!\nПроходить можно сколько угодно раз, но статистика сохраняется '
        'только для последнего сохраненного.\n\n\nЭтот тест является переводом '
        'оригинального [8Values](https://8values.github.io)\nЕсли хотите узнать '
        'статистику по тому или иному вопросу, введите /getresults <номер вопроса>. '
        'Помните, что есть всего 70 вопросов!\n\n\n\n',
        parse_mode='Markdown'
    )

    BOT.send_message(
        msg.chat.id,
        random.choice(
            [
                '_*реклама*_\nПотерял доступ к своим правам и свободам на территории РФ? Не надо'
                ' добавлять цифру 7 после joycasino!\nПросто подпишись на канал @nedimonmskinf '
                'и заходи в их чат @nedimon\\_msk, следи за движухой и присоединяйся к ней!\n\n'
                '_Интересный факт: в этом чате обитает создатель данного бота - @realMastAKK_',

                '_*реклама*_\nМне часто говорят: мастакк, как нам поднять права?\n'
                'Я отвечаю: заходи в @nedimon\\_msk!\n'
                'Доначу и не плачу, чтоб не затух их движ\n'
                'Мы оппозиция, никак иначе, мы не молчим\n\n(а ещё '
                'есть телеграм канал @nedimonmskinf)',

                '_*реклама*_\nЯ из госдепа к вам прибыть\n'
                'Инвайт в @nedimonmskinf вам приносить!\n'
                'Страну там помогать лечить\n'
                'Без пыни жить мечтают,\n'
                'Что в их силах сотворяют\n\n(а ещё есть телеграм чат @nedimon\\_msk)'
            ]
        ),
        parse_mode='Markdown'
    )


@BOT.message_handler(func=lambda msg: msg.chat.type == "private", commands=['startpoll'])
def on_startpoll(msg):
    """
    Handles /startpoll
    """
    if msg.from_user.id in [171970483]:
        BOT.send_message(msg.chat.id, random.choice(PHRASES_HERZEN))
        return
    if msg.chat.id not in ACTIVE_POLLS:
        CUR.execute('INSERT INTO polls(id) VALUES ({})'.format(msg.chat.id))
        ACTIVE_POLLS[msg.chat.id] = Poll()
        BOT.send_message(
            msg.chat.id,
            'Сперва скажите, согласны ли вы на сбор анонимной статистики для составления '
            'инфографики (решение можно менять в процессе теста)\n/agree - '
            'согласен\n/disagree - не согласен'
        )
    else:
        BOT.send_message(
            msg.chat.id,
            'Вероятно, вы уже начинали тест. Начните заново командой /restartpoll'
        )


@BOT.message_handler(func=lambda msg: msg.chat.type == "private", commands=['restartpoll'])
def on_restartpoll(msg):
    """
    Handles /restartpoll
    """
    BOT.send_message(msg.chat.id, 'Начинаем заново')
    ACTIVE_POLLS.pop(msg.chat.id, None)
    CUR.execute('DELETE FROM polls WHERE id={}'.format(msg.chat.id))
    on_startpoll(msg)


@BOT.message_handler(func=lambda msg: msg.chat.type == 'private', commands=['stat'])
def on_stat(msg):
    """
    Handles /stat
    """
    fin = open('./ideologies_count.txt', 'r')
    text = fin.read()
    BOT.send_message(msg.chat.id, text)
    # Шанс 1 к 1001, что юзер прочитает пасхалку.
    if random.randint(0, 1000)/1000 == 1:
        BOT.send_message(
            msg.chat.id, "Всюду, всюду леваки! Вы только гляньте!")


def get_question_text(uid):
    """
    Gets question text
    """
    if uid in ACTIVE_POLLS and ACTIVE_POLLS[uid].question_id < len(QUESTIONS):
        return 'Вопрос {} из {}\n'.format(
            ACTIVE_POLLS[uid].question_id + 1,
            len(QUESTIONS)
        ) + QUESTIONS[ACTIVE_POLLS[uid].question_id].question
    return 'Это был последний вопрос.'


@BOT.message_handler(func=lambda msg: msg.chat.type == "private", commands=["agree"])
def on_agreement(msg):
    """
    Handles /agree on prompt about storing result in anonymous stats
    """
    if msg.chat.id in ACTIVE_POLLS:
        CUR.execute(
            'UPDATE polls SET agree=TRUE WHERE id={}'.format(msg.chat.id)
        )
        ACTIVE_POLLS[msg.chat.id].stat = True
        ACTIVE_POLLS[msg.chat.id].msgid = msg.message_id
        BOT.send_message(msg.chat.id, 'Хорошо, я вас понял!')
        BOT.send_message(
            msg.chat.id,
            get_question_text(msg.chat.id),
            reply_markup=KB
        )


@BOT.message_handler(func=lambda msg: msg.chat.type == "private", commands=["disagree"])
def on_disagreement(msg):
    """
    Handles /disagree on prompt about storing result in anonymous stats
    """
    if msg.chat.id in ACTIVE_POLLS:
        CUR.execute(
            'UPDATE polls SET agree=FALSE WHERE id={}'.format(msg.chat.id)
        )
        ACTIVE_POLLS[msg.chat.id].stat = False
        ACTIVE_POLLS[msg.chat.id].msgid = msg.message_id
        BOT.send_message(msg.chat.id, 'Хорошо, я вас понял!')
        BOT.send_message(
            msg.chat.id,
            get_question_text(msg.chat.id),
            reply_markup=KB
        )


def calc_score(score, limit):
    """
    Magically counts score
    """
    return round(100*(limit+score)/(2*limit), 1)


ECON_ARRAY = [
    "Коммунистическая",
    "Социалистическая",
    "Социальная",
    "Центристская",
    "Рыночная",
    "Капиталистическая",
    "Laissez-Faire"
]
DIPL_ARRAY = [
    "Космополитическая",
    "Интернациональная",
    "Мирная",
    "Сбалансированная",
    "Патриотическая",
    "Националистическая",
    "Шовинистская"
]
GOVT_ARRAY = [
    "Анархистская",
    "Либертарная",
    "Либеральная",
    "Умеренная",
    "Этатистская",
    "Авторитарная",
    "Тоталитарная"
]
SCTY_ARRAY = [
    "Революционная",
    "Крайне прогрессивная",
    "Прогрессивная",
    "Нейтральная",
    "Традиционная",
    "Крайне традиционная",
    "Реакционная"
]

# Magically gets entry from given array in 0/10/25/40/60/75/90/100 ranges.
# With power of math, of course.
# FIXME: I'm too fabulous to be alive.
GET_NAME = (
    lambda a, v: a[6 - (lambda x: floor(cos(x/pi/10)*1.2+x/11.1-1.2))(v)] if v <= 100 else "")


def send_results(uid):
    """
    Sends results.
    """
    econ = dipl = govt = scty = 0.0

    for i in range(len(ACTIVE_POLLS[uid].answers)):
        econ, dipl, govt, scty = map(
            lambda vector, label, n: vector +
            ACTIVE_POLLS[uid].answers[n] * QUESTIONS[n].effect[label],
            (econ, dipl, govt, scty),
            ("econ", "dipl", "govt", "scty"),
            i
        )

    econ, dipl, govt, scty = map(
        calc_score,
        (econ, dipl, govt, scty),
        (MAX_ECON, MAX_DIPL, MAX_GOVT, MAX_SCTY)
    )

    result_text = 'Экономическая ось: {}\nРавенство {}% - {}% Рынок\n\n'.format(
        GET_NAME(ECON_ARRAY, econ),
        econ,
        round(100-econ, 1)
    )
    result_text += 'Дипломатическая ось: {}\nНация {}% - {}% Мир\n\n'.format(
        GET_NAME(DIPL_ARRAY, dipl),
        round(100-dipl, 1),
        dipl
    )
    result_text += 'Гражданская ось: {}\nСвобода {}% - {}% Авторитарность\n\n'.format(
        GET_NAME(GOVT_ARRAY, govt),
        govt,
        round(100-govt, 1)
    )
    result_text += 'Социальная ось: {}\nТрадиции {}% - {}% Прогресс\n\n\n'.format(
        GET_NAME(SCTY_ARRAY, scty),
        round(100-scty, 1),
        scty
    )

    ideology = ""
    ideodist = inf
    for i in IDEOLOGIES:
        dist = 0
        dist += pow(abs(i.stats['econ'] - econ), 2)
        dist += pow(abs(i.stats['govt'] - govt), 2)
        dist += pow(abs(i.stats['dipl'] - dipl), 1.73856063)
        dist += pow(abs(i.stats['scty'] - scty), 1.73856063)
        if dist < ideodist:
            ideology = i.name
            ideodist = dist
    result_text += 'Ближайшее совпадение: {}'.format(ideology)
    BOT.send_message(uid, result_text)
    BOT.send_message(
        uid,
        'Кстати, у бота есть свой чатик, где можно обсудить результаты и пообщаться на '
        'тему различных идеологий\n@eightvalues. \n\nА у автора перевода и самого этого '
        'бота есть свой канал, там бывают всякие интересности про политику, IT, творчество '
        'и т.п. Заглядывайте! @dzcreativity'
    )
    if ACTIVE_POLLS[uid].stat:
        #print('Writing anon_stat.txt')
        STAT_FILE.write('{}:'.format(uid))
        STAT_FILE.write(','.join(str(x) for x in ACTIVE_POLLS[uid].answers))
        STAT_FILE.write('\n\n')
        STAT_FILE.flush()
    BOT.send_photo(
        uid,
        "http://bot.rtmp.ru/new_bots/8values_image.php?e={}&d={}&g={}&s={}".format(
            econ,
            dipl,
            govt,
            scty
        )
    )

    ACTIVE_POLLS.pop(uid, None)
    CUR.execute('DELETE FROM polls WHERE uid={}'.format(uid))


SENDING = False


@BOT.message_handler(func=lambda msg: msg.chat.type == "private", commands=["notifyaboutchat"])
def onnotifychat(msg):
    """
    Some notifications. Didn't manage to produce meaningful docstring.
    """
    if msg.text.split(' ')[1] == "mastamasta321" and not SENDING:
        with open('part_ids.txt', 'r') as file:
            content = file.readlines()
        ids = [x.strip() for x in content]
        ids = ids[450:1099]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        print("starting coroutine")
        print(len(ids))
        loop.run_until_complete(sendinvite(ids))


async def sendinvite(ids):
    """
    Sends invites. Takes IDs iterable as input.
    """
    print("coroutine started")
    nonlocal SENDING
    SENDING = True  # NOTE: Unused
    textinv = "".join([
        'Привет.\n Я создал беседу, где можно будет обсудить результат теста, ',
        'задать вопросы про различные идеологии. Так сказать, дискуссионный клуб.\n',
        'Там же можно будет пообщаться со мной (переводчиком теста и разработчиком бота), ',
        'указать на неточности в переводе... Ну и всё в таком духе :)\n',
        'Присоединяйся!\nhttps://t.me/joinchat/ForjZ0paTZugCHK1ntBjvw\n\nP.S. за рекламу ',
        'и спам бот будет изгонять вас ;)'])
    print(len(ids))
    i = 0
    while i < len(ids):
        for j in range(0, 20):
            if i + j < len(ids):
                try:
                    BOT.send_message(ids[i + j], textinv)
                except Exception as ex:
                    print(ex)
        i += 20
        await asyncio.sleep(1.0)
        print("20 messages sent, total {}".format(i))
    SENDING = False  # NOTE: Unused


@BOT.callback_query_handler(func=lambda c: 1)
def on_callback_query(call):
    """
    Handles callbacks
    """
    if call.data.split()[0] == 'next':
        q_id = int(call.data.split()[1]) + 1
        kbnp = telebot.types.InlineKeyboardMarkup()
        if q_id < len(QUESTIONS)-1:
            kbnp.add(
                telebot.types.InlineKeyboardButton(
                    text='Следующий',
                    callback_data='next {}'.format(q_id)
                )
            )
        if q_id > 0:
            kbnp.add(
                telebot.types.InlineKeyboardButton(
                    text='Предыдущий',
                    callback_data='prev {}'.format(q_id)
                )
            )
        if q_id < len(QUESTIONS):
            BOT.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=COUNTED_STATS[q_id],
                reply_markup=kbnp
            )
        BOT.answer_callback_query(callback_query_id=call.id)
        return
    elif call.data.split()[0] == 'prev':
        q_id = int(call.data.split()[1]) - 1
        kbnp = telebot.types.InlineKeyboardMarkup()
        if q_id < len(QUESTIONS)-1:
            kbnp.add(telebot.types.InlineKeyboardButton(
                text='Следующий', callback_data='next {}'.format(q_id)))
        if q_id > 0:
            kbnp.add(telebot.types.InlineKeyboardButton(
                text='Предыдущий', callback_data='prev {}'.format(q_id)))
        if q_id < len(QUESTIONS):
            BOT.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=COUNTED_STATS[q_id],
                reply_markup=kbnp
            )
        BOT.answer_callback_query(callback_query_id=call.id)
        return

    if call.message.chat.type != "private":
        return
    if call.message.chat.id not in ACTIVE_POLLS:
        BOT.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text='Начните тест, введя команду /startpoll')
        return
    if call.data == "Back":
        if ACTIVE_POLLS[call.message.chat.id].question_id > 0:
            ACTIVE_POLLS[call.message.chat.id].answers.pop()
            ACTIVE_POLLS[call.message.chat.id].question_id -= 1
            CUR.execute(
                'UPDATE polls SET question_id={} WHERE uid={}'.format(
                    ACTIVE_POLLS[call.message.chat.id].question_id,
                    call.message.chat.id
                )
            )
            BOT.edit_message_text(
                chat_id=call.message.chat.id, message_id=call.message.message_id,
                text=get_question_text(call.message.chat.id),
                reply_markup=KB
            )
    elif ACTIVE_POLLS[call.message.chat.id].question_id < len(QUESTIONS):
        ACTIVE_POLLS[call.message.chat.id].answers.append(float(call.data))
        ACTIVE_POLLS[call.message.chat.id].question_id += 1
        qid = ACTIVE_POLLS[call.message.chat.id].question_id
        CUR.execute(
            'UPDATE polls SET answers[{}]={}, question_id={} WHERE uid={}'.format(
                qid,
                float(call.data),
                qid,
                call.message.chat.id
            )
        )
        BOT.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_question_text(call.message.chat.id),
            reply_markup=KB
        )

    if len(ACTIVE_POLLS[call.message.chat.id].answers) == len(QUESTIONS):
        BOT.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text='Сейчас я сообщу результаты!'
        )
        send_results(call.message.chat.id)

    BOT.answer_callback_query(callback_query_id=call.id)


CUR.execute('SELECT * FROM polls')
DB_POLLS = CUR.fetchall()
for p in DB_POLLS:
    uid = int(p['uid'])
    ACTIVE_POLLS[uid] = Poll(int(p['question_id']), p['agree'])
    if p['answers'] != None:
        for ans in list(p['answers']):
            ACTIVE_POLLS[uid].answers.append(float(ans))

parse_results()

BOT.remove_webhook()
time.sleep(2)
BOT.set_webhook(
    url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH,
    certificate=open(WEBHOOK_SSL_CERT, 'r')
)

CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
CONTEXT.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

web.run_app(
    APP,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    ssl_context=CONTEXT,
)
